"""
VYAS Phase 1 — Proficiency Engine
===================================
Implements an ELO-like per-topic proficiency model with:
  - Difficulty-weighted ELO updates
  - Adaptive K-factor (32 early, 16 after 50 questions)
  - Per-difficulty running accuracy
  - Time efficiency tracking (from Phase 0 enhanced responses)

Public API:
  update_user_proficiency(user_id, attempt_id) → None
    Called as a FastAPI BackgroundTask after every submit-attempt.
    Creates its own DB session — safe for background execution.

  get_proficiency_level(score) → str
    Maps a numeric score to Beginner/Intermediate/Advanced/Expert.
"""

import traceback
from datetime import datetime, timezone
from sqlalchemy.orm import Session

import models

# ── ELO configuration ─────────────────────────────────────────────────────────

# Each difficulty tier maps to a representative "question rating" in ELO space.
# Calibrated so the 400.0 default lands a user at ~50% win rate vs medium.
DIFFICULTY_RATING: dict[str, float] = {
    "easy":   300.0,
    "medium": 500.0,
    "hard":   700.0,
}

# K-factor: how much a single question shifts the score.
# 32 while learning (< 50 questions), 16 once stable.
K_INITIAL: float = 32.0
K_STABLE:  float = 16.0
K_THRESHOLD: int = 50        # questions seen before switching to stable K

ELO_SCALE: float    = 400.0  # Standard ELO denominator
MIN_SCORE: float    =   0.0
MAX_SCORE: float    = 1000.0
DEFAULT_SCORE: float = 400.0

# Proficiency bands (upper-bound exclusive, checked in descending order)
_PROFICIENCY_LEVELS = [
    (800.0, "Expert"),
    (600.0, "Advanced"),
    (300.0, "Intermediate"),
    (0.0,   "Beginner"),
]


# ── Public helpers ─────────────────────────────────────────────────────────────

def get_proficiency_level(score: float) -> str:
    """Map a numeric ELO score to a human-readable level string."""
    for threshold, label in _PROFICIENCY_LEVELS:
        if score >= threshold:
            return label
    return "Beginner"


# ── Core ELO math ──────────────────────────────────────────────────────────────

def _expected_score(user_rating: float, question_rating: float) -> float:
    """Standard ELO expected score formula."""
    return 1.0 / (1.0 + 10.0 ** ((question_rating - user_rating) / ELO_SCALE))


def _k_factor(total_count: int) -> float:
    return K_INITIAL if total_count < K_THRESHOLD else K_STABLE


def _clamp(value: float) -> float:
    return max(MIN_SCORE, min(MAX_SCORE, value))


# ── Incremental running average ────────────────────────────────────────────────

def _running_avg(current_avg: float, new_value: float, n: int) -> float:
    """
    Update a running average incrementally.
    n is the NEW total count (after including new_value).
    """
    if n <= 0:
        return new_value
    return current_avg + (new_value - current_avg) / n


# ── Row upsert logic ───────────────────────────────────────────────────────────

def _upsert_proficiency(
    db: Session,
    user_id: int,
    exam: str,
    subject: str,
    topic: str,
    subtopic: str | None,
    difficulty: str,
    is_correct: bool,
    time_efficiency_ratio: float | None,
) -> None:
    """
    Find or create the user_proficiency row for this (user, exam, subject, topic)
    and apply a single ELO update for one question response.
    """
    row = (
        db.query(models.UserProficiency)
        .filter_by(user_id=user_id, exam=exam, subject=subject, topic=topic)
        .first()
    )

    if not row:
        row = models.UserProficiency(
            user_id=user_id,
            exam=exam,
            subject=subject,
            topic=topic,
            subtopic=subtopic,
            proficiency=DEFAULT_SCORE,
            accuracy_rate=0.0,
            attempt_rate=0.0,
            avg_time_efficiency=1.0,
            correct_count=0,
            total_count=0,
            difficulty_easy_acc=0.0,
            difficulty_med_acc=0.0,
            difficulty_hard_acc=0.0,
        )
        db.add(row)
        db.flush()  # get the row into session without committing

    # ── ELO update ────────────────────────────────────────────────────────────
    diff_norm     = difficulty if difficulty in DIFFICULTY_RATING else "medium"
    q_rating      = DIFFICULTY_RATING[diff_norm]
    k             = _k_factor(row.total_count)
    expected      = _expected_score(row.proficiency, q_rating)
    actual        = 1.0 if is_correct else 0.0
    delta         = k * (actual - expected)
    row.proficiency = _clamp(row.proficiency + delta)

    # ── Count update ──────────────────────────────────────────────────────────
    row.total_count   += 1
    row.correct_count += (1 if is_correct else 0)
    new_n              = row.total_count

    # ── Overall accuracy rate ─────────────────────────────────────────────────
    row.accuracy_rate = round(row.correct_count / new_n, 4)

    # ── Per-difficulty running accuracy ───────────────────────────────────────
    # Uses global total_count as the weight denominator (approximation).
    # Accurate enough for our analytics purpose; avoids needing per-diff counters.
    correct_val = 1.0 if is_correct else 0.0
    if diff_norm == "easy":
        row.difficulty_easy_acc = round(_running_avg(row.difficulty_easy_acc, correct_val, new_n), 4)
    elif diff_norm == "medium":
        row.difficulty_med_acc  = round(_running_avg(row.difficulty_med_acc,  correct_val, new_n), 4)
    else:  # hard
        row.difficulty_hard_acc = round(_running_avg(row.difficulty_hard_acc, correct_val, new_n), 4)

    # ── Time efficiency (if Phase 0 data present) ─────────────────────────────
    if time_efficiency_ratio is not None:
        row.avg_time_efficiency = round(
            _running_avg(row.avg_time_efficiency, time_efficiency_ratio, new_n), 4
        )

    # ── Backfill subtopic if not yet captured ──────────────────────────────────
    if subtopic and not row.subtopic:
        row.subtopic = subtopic

    row.last_updated = datetime.now(timezone.utc)


# ── Background task entry point ────────────────────────────────────────────────

def update_user_proficiency(user_id: int, attempt_id: int) -> None:
    """
    FastAPI BackgroundTask entry point.

    Fired by submit-attempt after the response has been sent to the client.
    Creates its own DB session — the route handler's session is already
    closed by the time this runs.

    Any exception is caught, logged, and swallowed so a proficiency update
    failure never surfaces as an error to the user.
    """
    from database import SessionLocal  # local import to avoid circular dependency

    db = SessionLocal()
    try:
        _run_update(db, user_id, attempt_id)
    except Exception:
        db.rollback()
        traceback.print_exc()  # visible in server logs; never crashes the task
    finally:
        db.close()


def _run_update(db: Session, user_id: int, attempt_id: int) -> None:
    """Internal: runs inside an already-open session."""
    attempt = db.query(models.Attempt).filter_by(id=attempt_id).first()
    if not attempt:
        return

    mock = attempt.mock_test
    if not mock:
        return

    exam    = mock.exam
    subject = mock.subject

    for response in attempt.responses:
        topic      = response.topic or "General"
        difficulty = (response.difficulty or "medium").lower()
        subtopic   = getattr(response, "subtopic", None)   # Phase 0 column
        time_eff   = getattr(response, "time_efficiency_ratio", None)  # Phase 0 column
        is_correct = bool(response.is_correct)

        _upsert_proficiency(
            db=db,
            user_id=user_id,
            exam=exam,
            subject=subject,
            topic=topic,
            subtopic=subtopic,
            difficulty=difficulty,
            is_correct=is_correct,
            time_efficiency_ratio=time_eff,
        )

    db.commit()
