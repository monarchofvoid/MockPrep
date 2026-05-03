"""
VYAS — Virtual Yield Assessment System
FastAPI Backend — All 5 modules wired together:
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

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

import models
import schemas
from database import engine, get_db
from services.evaluation import evaluate
from services.analytics import get_user_analytics
from auth import get_current_user, hash_password, verify_password, create_access_token
from routers.password_reset import router as password_reset_router
from routers.contact import router as contact_router
# Phase 1: Tutor router (proficiency endpoint; Phase 2A adds explain/rate)
from routers.tutor import router as tutor_router
# Phase 1: Proficiency background task
from services.proficiency import update_user_proficiency
# Phase 2A: question bank loader extracted to its own module (avoids circular import)
from services.question_bank import load_question_json, QB_ROOT, _QB_CACHE, load_ai_mock_questions
# Phase 2B: AI Mock router
from routers.ai_mock import router as ai_mock_router
# Phase 3: Recommendation engine
from services.recommendations import get_recommendations

# ─── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="VYAS API",
    description="Virtual Yield Assessment System — question banks, test sessions, evaluation, analytics",
    version="2.0.0",
)

# Parse allowed origins from env (comma-separated) or use defaults
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
)
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all tables on startup
models.Base.metadata.create_all(bind=engine)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(password_reset_router)
app.include_router(contact_router)
app.include_router(tutor_router)   # Phase 1: /tutor/proficiency; Phase 2A: /tutor/explain, /tutor/rate
app.include_router(ai_mock_router) # Phase 2B: /ai-mock/generate, /ai-mock/history

# Phase 2A: QB_ROOT, _QB_CACHE, and load_question_json are now in
# services/question_bank.py. Imported at top of file.


def _make_mock_id(relative_path: Path) -> str:
    parts = list(relative_path.with_suffix("").parts)
    return "_".join(parts)


def seed_mock_tests(db: Session):
    """
    Auto-discover every JSON file in question_bank/ and upsert into mock_tests.
    Mirrors the standalone seed.py logic so both routes work identically.
    """
    if not QB_ROOT.exists():
        return

    for json_path in sorted(QB_ROOT.rglob("*.json")):
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
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
        else:
            changed = any(str(getattr(existing, k)) != str(v) for k, v in entry.items() if k != "id")
            if changed:
                for k, v in entry.items():
                    setattr(existing, k, v)

    db.commit()


@app.on_event("startup")
def startup_event():
    from database import SessionLocal
    db = SessionLocal()
    try:
        seed_mock_tests(db)
    finally:
        db.close()


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0", "app": "VYAS"}


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/auth/signup", response_model=schemas.TokenResponse, status_code=201, tags=["Auth"])
def signup(body: schemas.SignupRequest, db: Session = Depends(get_db)):
    """Register a new user and return a JWT token immediately."""
    if db.query(models.User).filter_by(email=body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return schemas.TokenResponse(access_token=token, user=user)


@app.post("/auth/login", response_model=schemas.TokenResponse, tags=["Auth"])
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email + password. Returns JWT token."""
    user = db.query(models.User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    token = create_access_token({"sub": str(user.id)})
    return schemas.TokenResponse(access_token=token, user=user)


@app.get("/auth/me", response_model=schemas.UserOut, tags=["Auth"])
def get_me(current_user: models.User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


# ─── Module A — Question Bank / Paper Catalogue ───────────────────────────────

@app.get("/mocks", response_model=List[schemas.MockTestOut], tags=["Papers"])
def list_mocks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return all available papers/mock tests. Requires authentication."""
    return db.query(models.MockTest).all()


@app.get("/mocks/{mock_id}", response_model=schemas.MockTestOut, tags=["Papers"])
def get_mock(
    mock_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return metadata for a single mock test."""
    mock = db.query(models.MockTest).filter_by(id=mock_id).first()
    if not mock:
        raise HTTPException(status_code=404, detail="Mock test not found")
    return mock


# ─── Module B — Mock Test Engine: start a session ─────────────────────────────

@app.post("/start-attempt", response_model=schemas.StartAttemptResponse, tags=["Test Engine"])
def start_attempt(
    body: schemas.StartAttemptRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    User selects a paper → create an Attempt row → return questions (without answers).
    user_id is always taken from the verified JWT — never from request body.
    """
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
    )   # Phase 2B: AI mocks load from DB; regular mocks load from disk
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


# ─── Module C + D — Submit, track, evaluate ──────────────────────────────────

@app.post("/submit-attempt", response_model=schemas.ResultsResponse, tags=["Test Engine"])
def submit_attempt(
    body: schemas.SubmitAttemptRequest,
    background_tasks: BackgroundTasks,          # Phase 1: proficiency update trigger
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Receive full question states from frontend → evaluate → persist → return results.
    Validates that the attempt belongs to the requesting user.
    """
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
    )   # Phase 2B: AI mocks load from DB; regular mocks load from disk

    # ── Module D: Run evaluation ──────────────────────────────────────────────
    result = evaluate(
        attempt_id=attempt.id,
        mock_data=mock_data,
        question_states=body.question_states,
        time_taken_seconds=body.time_taken_seconds,
    )

    # ── Persist attempt summary ───────────────────────────────────────────────
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

    # ── Persist per-question responses (Module C) ─────────────────────────────
    # Phase 0: build a lookup from question_id → raw question dict so we can
    # pull subtopic, question_category, estimated_time_sec for enriched storage.
    q_raw_map = {q["id"]: q for q in mock_data["questions"]}

    state_map = {qs.question_id: qs for qs in body.question_states}
    for qr in result["question_reviews"]:
        qs  = state_map.get(qr["question_id"])
        raw_q = q_raw_map.get(qr["question_id"], {})

        # ── Phase 0: compute time efficiency ratio ────────────────────────────
        estimated = raw_q.get("estimated_time_sec")         # may be None
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
            # ── Phase 0 new columns ───────────────────────────────────────────
            subtopic=raw_q.get("subtopic"),
            question_category=raw_q.get("question_category"),
            estimated_time_sec=estimated,
            time_efficiency_ratio=time_eff,
        )
        db.add(response_row)

    db.commit()
    db.refresh(attempt)

    # ── Phase 1: Trigger proficiency update (non-blocking) ───────────────────
    # Runs AFTER the response is sent — never delays the user.
    # Creates its own session internally; safe even if the main session closes.
    background_tasks.add_task(update_user_proficiency, current_user.id, attempt.id)

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
            schemas.QuestionReview(**qr)
            for qr in result["question_reviews"]
        ],
    )


# ─── Module E — Results & Analytics ──────────────────────────────────────────

@app.get("/results/{attempt_id}", response_model=schemas.ResultsResponse, tags=["Analytics"])
def get_results(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Retrieve persisted results for a completed attempt. Must own the attempt."""
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
    )   # Phase 2B: AI mocks load from DB; regular mocks load from disk
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


# ─── Phase 5 — Convenience "me" routes ───────────────────────────────────────

@app.get("/analytics/me", response_model=schemas.UserAnalytics, tags=["Analytics"])
def my_analytics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return aggregated performance data for the authenticated user."""
    return get_user_analytics(db, current_user.id)


@app.get("/recommendations", response_model=schemas.RecommendationResponse, tags=["Analytics"])
def my_recommendations(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Phase 3: Return personalised mock recommendations based on proficiency data.

    Algorithm (pure computation — no AI calls):
      - Weak subjects (ELO < 450) → surface untried mocks in that subject
      - Top exam familiarity → prefer same exam series
      - Already strong subjects (ELO > 600) → deprioritised
      - AI mock suggestion → weakest topic + difficulty matching proficiency level

    Safe for new users: returns empty lists and 'no proficiency data' flag.
    Response is fast (<50ms) — no external calls.
    """
    return get_recommendations(db, current_user.id)


@app.get("/users/me/attempts", tags=["Users"])
def my_attempts(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all attempts for the authenticated user with summary stats."""
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
            "mock_id": a.mock_id,
            "subject": mt.subject if mt else "—",
            "year": mt.year if mt else "—",
            "score": a.score,
            "total_marks": a.total_marks,
            "accuracy": a.accuracy,
            "time_taken_seconds": a.time_taken_seconds,
            "submitted": a.submitted_at is not None,
            "started_at": a.started_at,
            "is_ai_generated": mt.is_ai_generated if mt else False,  # Phase 3
        })
    return result


# ─── Legacy user endpoints (kept for backwards compatibility) ─────────────────

@app.get("/analytics/{user_id}", response_model=schemas.UserAnalytics, tags=["Analytics"])
def user_analytics(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return aggregated performance data for a user. Must be own data."""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return get_user_analytics(db, user_id)


@app.get("/users/me", response_model=schemas.UserOut, tags=["Users"])
def get_current_user_profile(current_user: models.User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user