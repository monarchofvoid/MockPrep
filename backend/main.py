"""
MockPrep — FastAPI Backend
All 5 modules wired together:
  A. Question Bank loader
  B. Mock Test Engine (session start)
  C. Response Tracking (data in)
  D. Evaluation Engine (scoring)
  E. Analytics/Dashboard (data out)
"""

import json
import os
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import models
import schemas
from database import engine, get_db
from services.evaluation import evaluate
from services.analytics import get_user_analytics

# ─── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="MockPrep API",
    description="Mock test platform — question banks, test sessions, evaluation, analytics",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://mock-prep-three.vercel.app",   # ← add your real Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all tables on startup
models.Base.metadata.create_all(bind=engine)

# Question bank root (can be overridden via env var)
QB_ROOT = Path(os.getenv("QB_ROOT", "../question_bank"))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_question_json(file_path: str) -> dict:
    """Load and parse a question bank JSON file."""
    path = QB_ROOT / file_path
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question bank file not found: {file_path}",
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_mock_tests(db: Session):
    """
    Auto-seed MockTest metadata from JSON files in question_bank/.
    In production, replace this with a proper admin panel or migration.
    """
    registry = [
        {
            "id": "dbms_pyq_2021",
            "exam": "GATE",
            "subject": "Database Management Systems",
            "year": "PYQ 2021",
            "duration_minutes": 30,
            "total_marks": 15.0,
            "question_count": 10,
            "json_file_path": "dbms/pyq_2021.json",
        },
        {
            "id": "os_pyq_2022",
            "exam": "GATE",
            "subject": "Operating Systems",
            "year": "PYQ 2022",
            "duration_minutes": 30,
            "total_marks": 15.0,
            "question_count": 10,
            "json_file_path": "os/pyq_2022.json",
        },
    ]
    for entry in registry:
        if not db.query(models.MockTest).filter_by(id=entry["id"]).first():
            db.add(models.MockTest(**entry))
    db.commit()


@app.on_event("startup")
def startup_event():
    db = next(get_db())
    seed_mock_tests(db)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ─── Module A — Question Bank / Paper Catalogue ───────────────────────────────

@app.get("/mocks", response_model=List[schemas.MockTestOut], tags=["Papers"])
def list_mocks(db: Session = Depends(get_db)):
    """Return all available papers/mock tests."""
    return db.query(models.MockTest).all()


@app.get("/mocks/{mock_id}", response_model=schemas.MockTestOut, tags=["Papers"])
def get_mock(mock_id: str, db: Session = Depends(get_db)):
    """Return metadata for a single mock test."""
    mock = db.query(models.MockTest).filter_by(id=mock_id).first()
    if not mock:
        raise HTTPException(status_code=404, detail="Mock test not found")
    return mock


# ─── Module B — Mock Test Engine: start a session ─────────────────────────────

@app.post("/start-attempt", response_model=schemas.StartAttemptResponse, tags=["Test Engine"])
def start_attempt(body: schemas.StartAttemptRequest, db: Session = Depends(get_db)):
    """
    User selects a paper → create an Attempt row → return questions (without answers).
    """
    # Validate user
    user = db.query(models.User).filter_by(id=body.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate mock test
    mock = db.query(models.MockTest).filter_by(id=body.mock_id).first()
    if not mock:
        raise HTTPException(status_code=404, detail="Mock test not found")

    # Create attempt record
    attempt = models.Attempt(user_id=body.user_id, mock_id=body.mock_id)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    # Load question bank (strip correct answers before sending)
    mock_data = load_question_json(mock.json_file_path)
    questions_out = [
        schemas.QuestionOut(
            id=q["id"],
            type=q["type"],
            question=q["question"],
            options=q["options"],
            difficulty=q["difficulty"],
            topic=q["topic"],
            marks=q["marks"],
            negative_marking=q["negative_marking"],
        )
        for q in mock_data["questions"]
    ]

    return schemas.StartAttemptResponse(
        attempt_id=attempt.id,
        mock_id=mock.id,
        questions=questions_out,
        duration_minutes=mock.duration_minutes,
        total_marks=mock.total_marks,
    )


# ─── Module C + D — Submit, track, evaluate ──────────────────────────────────

@app.post("/submit-attempt", response_model=schemas.ResultsResponse, tags=["Test Engine"])
def submit_attempt(body: schemas.SubmitAttemptRequest, db: Session = Depends(get_db)):
    """
    Receive full question states from frontend → evaluate → persist → return results.
    """
    attempt = db.query(models.Attempt).filter_by(id=body.attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.submitted_at:
        raise HTTPException(status_code=400, detail="Attempt already submitted")

    mock = attempt.mock_test
    mock_data = load_question_json(mock.json_file_path)

    # ── Module D: Run evaluation ──────────────────────────────────────────────
    result = evaluate(
        attempt_id=attempt.id,
        mock_data=mock_data,
        question_states=body.question_states,
        time_taken_seconds=body.time_taken_seconds,
    )

    # ── Persist attempt summary ───────────────────────────────────────────────
    attempt.score = result["_db_score"]
    attempt.total_marks = result["_db_total_marks"]
    attempt.correct_count = result["_db_correct"]
    attempt.wrong_count = result["_db_wrong"]
    attempt.skipped_count = result["_db_skipped"]
    attempt.accuracy = result["_db_accuracy"]
    attempt.attempt_rate = result["_db_attempt_rate"]
    attempt.time_taken_seconds = result["_db_time"]
    attempt.avg_time_per_question = result["_db_avg_time"]
    attempt.submitted_at = datetime.now(timezone.utc)

    # ── Persist per-question responses (Module C) ─────────────────────────────
    state_map = {qs.question_id: qs for qs in body.question_states}
    for qr in result["question_reviews"]:
        qs = state_map.get(qr["question_id"])
        response_row = models.Response(
            attempt_id=attempt.id,
            question_id=qr["question_id"],
            selected_option=qr["selected_option"],
            is_correct=qr["is_correct"],
            marks_awarded=qr["marks_awarded"],
            time_spent_seconds=qs.time_spent_seconds if qs else 0,
            visit_count=qs.visit_count if qs else 0,
            answer_changed_count=qs.answer_changed_count if qs else 0,
            was_marked_for_review=qs.was_marked_for_review if qs else False,
            topic=qr["topic"],
            difficulty=qr["difficulty"],
        )
        db.add(response_row)

    db.commit()
    db.refresh(attempt)

    # ── Build and return full ResultsResponse ─────────────────────────────────
    return schemas.ResultsResponse(
        attempt_id=attempt.id,
        mock_id=mock.id,
        subject=mock.subject,
        year=mock.year,
        score=result["score"],
        total_marks=result["total_marks"],
        score_percentage=result["score_percentage"],
        correct_count=result["correct_count"],
        wrong_count=result["wrong_count"],
        skipped_count=result["skipped_count"],
        accuracy=result["accuracy"],
        attempt_rate=result["attempt_rate"],
        time_taken_seconds=result["time_taken_seconds"],
        avg_time_per_question=result["avg_time_per_question"],
        topic_performance=[
            schemas.TopicPerformance(**tp) for tp in result["topic_performance"]
        ],
        question_reviews=[
            schemas.QuestionReview(
                question_id=qr["question_id"],
                question_text=qr["question_text"],
                options=qr["options"],
                selected_option=qr["selected_option"],
                correct_option=qr["correct_option"],
                is_correct=qr["is_correct"],
                marks_awarded=qr["marks_awarded"],
                explanation=qr["explanation"],
                time_spent_seconds=qr["time_spent_seconds"],
                visit_count=qr["visit_count"],
                answer_changed_count=qr["answer_changed_count"],
                was_marked_for_review=qr["was_marked_for_review"],
                difficulty=qr["difficulty"],
                topic=qr["topic"],
            )
            for qr in result["question_reviews"]
        ],
    )


# ─── Module E — Results & Analytics ──────────────────────────────────────────

@app.get("/results/{attempt_id}", response_model=schemas.ResultsResponse, tags=["Analytics"])
def get_results(attempt_id: int, db: Session = Depends(get_db)):
    """Retrieve persisted results for a completed attempt."""
    attempt = db.query(models.Attempt).filter_by(id=attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if not attempt.submitted_at:
        raise HTTPException(status_code=400, detail="Attempt not yet submitted")

    mock = attempt.mock_test
    mock_data = load_question_json(mock.json_file_path)
    q_map = {q["id"]: q for q in mock_data["questions"]}

    topic_stats: dict = {}
    question_reviews = []

    for resp in attempt.responses:
        q = q_map.get(resp.question_id, {})
        t = resp.topic or "General"
        if t not in topic_stats:
            topic_stats[t] = {"correct": 0, "total": 0}
        topic_stats[t]["total"] += 1
        if resp.is_correct:
            topic_stats[t]["correct"] += 1

        question_reviews.append(
            schemas.QuestionReview(
                question_id=resp.question_id,
                question_text=q.get("question", ""),
                options=q.get("options", {}),
                selected_option=resp.selected_option,
                correct_option=q.get("correct", ""),
                is_correct=resp.is_correct or False,
                marks_awarded=resp.marks_awarded or 0,
                explanation=q.get("explanation", ""),
                time_spent_seconds=resp.time_spent_seconds or 0,
                visit_count=resp.visit_count or 0,
                answer_changed_count=resp.answer_changed_count or 0,
                was_marked_for_review=resp.was_marked_for_review or False,
                difficulty=resp.difficulty or "",
                topic=resp.topic or "",
            )
        )

    topic_performance = [
        schemas.TopicPerformance(
            topic=t,
            correct=v["correct"],
            total=v["total"],
            accuracy=round(v["correct"] / v["total"] * 100, 1),
        )
        for t, v in topic_stats.items()
    ]

    return schemas.ResultsResponse(
        attempt_id=attempt.id,
        mock_id=mock.id,
        subject=mock.subject,
        year=mock.year,
        score=attempt.score,
        total_marks=attempt.total_marks,
        score_percentage=round((attempt.score / attempt.total_marks) * 100, 1),
        correct_count=attempt.correct_count,
        wrong_count=attempt.wrong_count,
        skipped_count=attempt.skipped_count,
        accuracy=attempt.accuracy,
        attempt_rate=attempt.attempt_rate,
        time_taken_seconds=attempt.time_taken_seconds,
        avg_time_per_question=attempt.avg_time_per_question,
        topic_performance=topic_performance,
        question_reviews=question_reviews,
    )


@app.get("/analytics/{user_id}", response_model=schemas.UserAnalytics, tags=["Analytics"])
def user_analytics(user_id: int, db: Session = Depends(get_db)):
    """Return aggregated performance data across all of a user's attempts."""
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return get_user_analytics(db, user_id)


# ─── User management (minimal) ────────────────────────────────────────────────

@app.post("/users", response_model=schemas.UserOut, status_code=201, tags=["Users"])
def create_user(body: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(email=body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(name=body.name, email=body.email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users/{user_id}", response_model=schemas.UserOut, tags=["Users"])
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/{user_id}/attempts", tags=["Users"])
def user_attempts(user_id: int, db: Session = Depends(get_db)):
    """List all attempts by a user with summary stats."""
    attempts = (
        db.query(models.Attempt)
        .filter_by(user_id=user_id)
        .order_by(models.Attempt.started_at.desc())
        .all()
    )
    result = []
    for a in attempts:
        mt = a.mock_test
        result.append({
            "attempt_id": a.id,
            "mock_id": a.mock_id,
            "subject": mt.subject if mt else "—",
            "year": mt.year if mt else "—",
            "score": a.score,
            "total_marks": a.total_marks,
            "accuracy": a.accuracy,
            "time_taken_seconds": a.time_taken_seconds,
            "submitted": a.submitted_at is not None,
            "started_at": a.started_at,
        })
    return result
