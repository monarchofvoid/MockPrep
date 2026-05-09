"""
VYAS v2.0 — FastAPI Backend
==============================
v2.0 architectural changes vs v0.6:
  - Auth endpoints moved to routers/auth.py (access + refresh token system)
  - SecurityHeadersMiddleware: adds X-Frame-Options, X-Content-Type-Options, etc.
  - RequestIDMiddleware: traces each request with a unique ID
  - CORS: credentials=True required for httpOnly cookie (refresh token)
  - Auth now uses auth.py shim → core/security.py + core/auth.py
  - /auth/signup, /auth/login, /auth/me, /auth/refresh, /auth/logout
    all handled by routers/auth.py — removed from this file
  - Legacy /users/me preserved for backward compat
  - DB tables auto-created include new RefreshToken + LoginAttempt models
"""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import models
import schemas
from config import AppConfig
from database import engine, get_db
from logging_config import configure_logging
from services.evaluation import evaluate
from services.analytics import get_user_analytics
from auth import get_current_user
from routers.auth import router as auth_router
from routers.password_reset import router as password_reset_router
from routers.contact import router as contact_router
from routers.tutor import router as tutor_router
from routers.ai_mock import router as ai_mock_router
from routers.profile import router as profile_router
from middleware.security_headers import SecurityHeadersMiddleware
from middleware.request_id import RequestIDMiddleware
from services.proficiency import update_user_proficiency
from services.question_bank import load_question_json, QB_ROOT, _QB_CACHE, load_ai_mock_questions
from services.recommendations import get_recommendations

configure_logging()
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("VYAS v2.0 starting up...")
    from database import SessionLocal
    db = SessionLocal()
    try:
        seed_mock_tests(db)
        logger.info("Mock test seeding complete. QB_ROOT=%s", QB_ROOT)
    finally:
        db.close()

    yield

    logger.info("VYAS v2.0 shutting down.")


# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="VYAS API",
    description="Virtual Yield Assessment System — v2.0",
    version="2.0.0",
    lifespan=lifespan,
)

# Middleware — order matters: outermost runs first on request, last on response
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# CORS — allow_credentials=True is REQUIRED for httpOnly cookies to be sent/received
app.add_middleware(
    CORSMiddleware,
    allow_origins=AppConfig.ALLOWED_ORIGINS,
    allow_credentials=True,   # v2.0: required for refresh token cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auto-create tables (includes new v2.0 models)
models.Base.metadata.create_all(bind=engine)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth_router)           # v2.0: new auth router (replaces inline endpoints)
app.include_router(password_reset_router)
app.include_router(contact_router)
app.include_router(tutor_router)
app.include_router(ai_mock_router)
app.include_router(profile_router)


# ── Seed helpers ───────────────────────────────────────────────────────────────

def _make_mock_id(relative_path: Path) -> str:
    parts = list(relative_path.with_suffix("").parts)
    return "_".join(parts)


def seed_mock_tests(db: Session):
    if not QB_ROOT.exists():
        logger.warning("QB_ROOT does not exist: %s — skipping seed", QB_ROOT)
        return

    seeded = 0
    errors = 0
    for json_path in sorted(QB_ROOT.rglob("*.json")):
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping %s: %s", json_path.name, exc)
            errors += 1
            continue

        relative    = json_path.relative_to(QB_ROOT)
        mock_id     = _make_mock_id(relative)
        duration    = data.get("duration_minutes") or data.get("duration") or 30
        total_marks = data.get("total_marks") or sum(
            q.get("marks", 1) for q in data.get("questions", [])
        )

        entry = {
            "id":               mock_id,
            "exam":             data.get("exam", "UNKNOWN"),
            "subject":          data.get("subject", relative.parts[0].upper()),
            "year":             str(data.get("year", "")),
            "duration_minutes": int(duration),
            "total_marks":      float(total_marks),
            "question_count":   len(data.get("questions", [])),
            "json_file_path":   str(relative),
        }

        existing = db.query(models.MockTest).filter_by(id=mock_id).first()
        if not existing:
            db.add(models.MockTest(**entry))
            seeded += 1
        else:
            changed = any(str(getattr(existing, k)) != str(v) for k, v in entry.items() if k != "id")
            if changed:
                for k, v in entry.items():
                    setattr(existing, k, v)

    db.commit()
    logger.info("Seed complete: %d mock tests processed, %d errors", seeded, errors)


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0", "app": "VYAS"}


# ── Mock Paper Catalogue ───────────────────────────────────────────────────────

@app.get("/mocks", response_model=List[schemas.MockTestOut], tags=["Papers"])
def list_mocks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.MockTest).all()


@app.get("/mocks/{mock_id}", response_model=schemas.MockTestOut, tags=["Papers"])
def get_mock(
    mock_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    mock = db.query(models.MockTest).filter_by(id=mock_id).first()
    if not mock:
        raise HTTPException(status_code=404, detail="Mock test not found")
    return mock


# ── Test Engine ────────────────────────────────────────────────────────────────

@app.post("/start-attempt", response_model=schemas.StartAttemptResponse, tags=["Test Engine"])
def start_attempt(
    body: schemas.StartAttemptRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    mock = db.query(models.MockTest).filter_by(id=body.mock_id).first()
    if not mock:
        raise HTTPException(status_code=404, detail="Mock test not found")

    attempt = models.Attempt(user_id=current_user.id, mock_id=body.mock_id)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    mock_data = (
        load_ai_mock_questions(db, mock.id)
        if mock.is_ai_generated
        else load_question_json(mock.json_file_path)
    )
    questions_out = [
        schemas.QuestionOut(
            id=q["id"],
            type=q["type"],
            question=q["question"],
            passage=q.get("passage"),
            passage_title=q.get("passage_title"),
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


@app.post("/submit-attempt", response_model=schemas.ResultsResponse, tags=["Test Engine"])
def submit_attempt(
    body: schemas.SubmitAttemptRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    attempt = db.query(models.Attempt).filter_by(id=body.attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your attempt")
    if attempt.submitted_at:
        raise HTTPException(status_code=400, detail="Attempt already submitted")

    mock = attempt.mock_test
    mock_data = (
        load_ai_mock_questions(db, mock.id)
        if mock.is_ai_generated
        else load_question_json(mock.json_file_path)
    )

    result = evaluate(
        attempt_id=attempt.id,
        mock_data=mock_data,
        question_states=body.question_states,
        time_taken_seconds=body.time_taken_seconds,
    )

    attempt.score                 = result["_db_score"]
    attempt.total_marks           = result["_db_total_marks"]
    attempt.correct_count         = result["_db_correct"]
    attempt.wrong_count           = result["_db_wrong"]
    attempt.skipped_count         = result["_db_skipped"]
    attempt.accuracy              = result["_db_accuracy"]
    attempt.attempt_rate          = result["_db_attempt_rate"]
    attempt.time_taken_seconds    = result["_db_time"]
    attempt.avg_time_per_question = result["_db_avg_time"]
    attempt.submitted_at          = datetime.now(timezone.utc)

    q_raw_map = {q["id"]: q for q in mock_data["questions"]}
    state_map = {qs.question_id: qs for qs in body.question_states}

    for qr in result["question_reviews"]:
        qs    = state_map.get(qr["question_id"])
        raw_q = q_raw_map.get(qr["question_id"], {})
        estimated = raw_q.get("estimated_time_sec")
        actual    = qs.time_spent_seconds if qs else 0
        time_eff  = round(actual / estimated, 3) if estimated and estimated > 0 else None

        response_row = models.Response(
            attempt_id=attempt.id,
            question_id=qr["question_id"],
            selected_option=qr["selected_option"],
            is_correct=qr["is_correct"],
            marks_awarded=qr["marks_awarded"],
            time_spent_seconds=actual,
            visit_count=qs.visit_count if qs else 0,
            answer_changed_count=qs.answer_changed_count if qs else 0,
            was_marked_for_review=qs.was_marked_for_review if qs else False,
            topic=qr["topic"],
            difficulty=qr["difficulty"],
            subtopic=raw_q.get("subtopic"),
            question_category=raw_q.get("question_category"),
            estimated_time_sec=estimated,
            time_efficiency_ratio=time_eff,
        )
        db.add(response_row)

    db.commit()
    db.refresh(attempt)

    background_tasks.add_task(update_user_proficiency, current_user.id, attempt.id)
    logger.info(
        "Attempt %s submitted by user %s: score=%.1f/%s",
        attempt.id, current_user.id, result["_db_score"], result["_db_total_marks"],
    )

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
        topic_performance=[schemas.TopicPerformance(**tp) for tp in result["topic_performance"]],
        question_reviews=[schemas.QuestionReview(**qr) for qr in result["question_reviews"]],
    )


# ── Results & Analytics ────────────────────────────────────────────────────────

@app.get("/results/{attempt_id}", response_model=schemas.ResultsResponse, tags=["Analytics"])
def get_results(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    attempt = db.query(models.Attempt).filter_by(id=attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your attempt")
    if not attempt.submitted_at:
        raise HTTPException(status_code=400, detail="Attempt not yet submitted")

    mock = attempt.mock_test
    mock_data = (
        load_ai_mock_questions(db, mock.id)
        if mock.is_ai_generated
        else load_question_json(mock.json_file_path)
    )
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
                passage=q.get("passage"),
                passage_title=q.get("passage_title"),
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
        score_percentage=round((attempt.score / attempt.total_marks) * 100, 1) if attempt.total_marks else 0.0,
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


@app.get("/analytics/me", response_model=schemas.UserAnalytics, tags=["Analytics"])
def my_analytics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_user_analytics(db, current_user.id)


@app.get("/recommendations", response_model=schemas.RecommendationResponse, tags=["Analytics"])
def my_recommendations(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_recommendations(db, current_user.id)


@app.get("/users/me/attempts", tags=["Users"])
def my_attempts(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempts = (
        db.query(models.Attempt)
        .filter_by(user_id=current_user.id)
        .order_by(models.Attempt.started_at.desc())
        .all()
    )
    result = []
    for a in attempts:
        mt = a.mock_test
        result.append({
            "attempt_id": a.id,
            "mock_id":    a.mock_id,
            "subject":    mt.subject if mt else "—",
            "year":       mt.year if mt else "—",
            "score":      a.score,
            "total_marks": a.total_marks,
            "accuracy":   a.accuracy,
            "time_taken_seconds": a.time_taken_seconds,
            "submitted":  a.submitted_at is not None,
            "started_at": a.started_at,
            "is_ai_generated": mt.is_ai_generated if mt else False,
        })
    return result


# ── Legacy endpoints (backward compat) ─────────────────────────────────────────

@app.get("/analytics/{user_id}", response_model=schemas.UserAnalytics, tags=["Analytics"])
def user_analytics(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return get_user_analytics(db, user_id)


@app.get("/users/me", response_model=schemas.UserOut, tags=["Users"])
def get_current_user_profile(current_user: models.User = Depends(get_current_user)):
    return current_user
