"""
VYAS v2.0 — Mock Tests Router
================================
GET /mocks — list available mock tests for the current user:
  - All standard (non-AI) papers
  - AI mocks generated specifically for this user

BUG FIX (v2.0.4):
  Previous fix used db.bind.dialect.name which is removed in SQLAlchemy 2.0,
  and used JSONB field access syntax that crashed on PostgreSQL with psycopg3.

  New approach: two clean queries, no JSON field access needed.
    1. Fetch all standard papers (is_ai_generated = False)
    2. Fetch AI mocks via AIJob.user_id join
       AND via ai_generation_params text search as a fallback
       (handles mocks whose AIJob row was cleaned up)
  Results are merged in Python and deduplicated by id.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Mock Tests"])


@router.get("/mocks")
def list_mocks(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns all standard papers + AI mocks owned by the current user.
    Deduplicates by mock id so no paper appears twice.
    """
    user_id = str(current_user.id)

    # ── 1. Standard papers (always visible to everyone) ──────────────────────
    standard = (
        db.query(models.MockTest)
        .filter(models.MockTest.is_ai_generated.is_(False))
        .order_by(
            models.MockTest.exam,
            models.MockTest.subject,
            models.MockTest.year.desc(),
        )
        .all()
    )

    # ── 2. AI mocks via AIJob join ────────────────────────────────────────────
    ai_via_job = (
        db.query(models.MockTest)
        .join(models.AIJob, models.MockTest.ai_job_id == models.AIJob.id)
        .filter(
            models.MockTest.is_ai_generated.is_(True),
            models.AIJob.user_id == current_user.id,
        )
        .order_by(
            models.MockTest.exam,
            models.MockTest.subject,
        )
        .all()
    )

    # ── 3. AI mocks via JSONB field (fallback for cleaned-up AIJob rows) ──────
    # Uses a raw PostgreSQL cast to safely extract from the JSON column.
    # This catches mocks where the AIJob row was deleted but the MockTest
    # and its ai_generation_params->generated_for_user field still exist.
    ai_via_params = []
    try:
        ai_via_params = (
            db.query(models.MockTest)
            .filter(
                models.MockTest.is_ai_generated.is_(True),
                text(
                    "ai_generation_params->>'generated_for_user' = :uid"
                ).bindparams(uid=user_id),
            )
            .order_by(
                models.MockTest.exam,
                models.MockTest.subject,
            )
            .all()
        )
    except Exception as exc:
        # Non-fatal: log and continue — ai_via_job already covers most cases
        logger.warning("ai_via_params fallback query failed (non-fatal): %s", exc)

    # ── Merge and deduplicate ─────────────────────────────────────────────────
    seen: set[str] = set()
    result: list[models.MockTest] = []

    for mock in [*standard, *ai_via_job, *ai_via_params]:
        if mock.id not in seen:
            seen.add(mock.id)
            result.append(mock)

    logger.info(
        "list_mocks: user_id=%s standard=%d ai_job=%d ai_params=%d total=%d",
        user_id, len(standard), len(ai_via_job), len(ai_via_params), len(result),
    )

    return [
        {
            "id":               m.id,
            "exam":             m.exam,
            "subject":          m.subject,
            "year":             m.year,
            "duration_minutes": m.duration_minutes,
            "total_marks":      m.total_marks,
            "question_count":   m.question_count,
            "is_ai_generated":  m.is_ai_generated,
        }
        for m in result
    ]