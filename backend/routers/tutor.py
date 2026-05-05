"""
VYAS v0.6 — Tutor Router
=========================
Fixes applied vs v0.5:
  B1: Generic Exception in handler replaced with specific types
  B6: No bare `except Exception` — granular handling
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import get_current_user
from services.proficiency import get_proficiency_level
from services.question_bank import load_question_json
from services.gemini_utils import GeminiParseError, GeminiTruncationError
from services.tutor import (
    get_proficiency_bucket,
    get_or_create_explanation,
    build_behavioral_note,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tutor", tags=["Tutor"])


# ── GET /tutor/proficiency ─────────────────────────────────────────────────────

@router.get("/proficiency", response_model=schemas.UserProficiencyResponse)
def get_proficiency(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.UserProficiency)
        .filter_by(user_id=current_user.id)
        .order_by(
            models.UserProficiency.subject,
            models.UserProficiency.topic,
        )
        .all()
    )

    overall_score = round(sum(r.proficiency for r in rows) / len(rows), 2) if rows else 400.0
    overall_level = get_proficiency_level(overall_score)

    topics = [
        schemas.TopicProficiency(
            exam=r.exam,
            subject=r.subject,
            topic=r.topic,
            subtopic=r.subtopic,
            proficiency=round(r.proficiency, 2),
            level=get_proficiency_level(r.proficiency),
            accuracy_rate=r.accuracy_rate,
            total_count=r.total_count,
            correct_count=r.correct_count,
            difficulty_profile=schemas.DifficultyProfile(
                easy=r.difficulty_easy_acc,
                medium=r.difficulty_med_acc,
                hard=r.difficulty_hard_acc,
            ),
            avg_time_efficiency=r.avg_time_efficiency,
            last_updated=r.last_updated,
        )
        for r in rows
    ]

    return schemas.UserProficiencyResponse(
        user_id=current_user.id,
        overall_level=overall_level,
        overall_score=overall_score,
        topic_count=len(rows),
        topics=topics,
    )


# ── POST /tutor/explain ────────────────────────────────────────────────────────

@router.post("/explain", response_model=schemas.TutorExplainResponse)
async def tutor_explain(
    body: schemas.TutorExplainRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    B1 Fix: Generic Exception replaced with specific types.
    API key is never exposed in error responses.
    """
    # ── Validate attempt ownership ────────────────────────────────────────────
    attempt = db.query(models.Attempt).filter_by(id=body.attempt_id).first()
    if not attempt or attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    response_row = (
        db.query(models.Response)
        .filter_by(attempt_id=body.attempt_id, question_id=body.question_id)
        .first()
    )
    if not response_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found for this attempt/question combination.",
        )
    if response_row.is_correct:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VYAS Tutor is only available for wrong or skipped answers.",
        )

    mock = attempt.mock_test
    if not mock or not mock.json_file_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mock test question bank file path not found.",
        )

    try:
        mock_data = load_question_json(mock.json_file_path)
    except HTTPException:
        raise

    question_data = next(
        (q for q in mock_data.get("questions", []) if q.get("id") == body.question_id),
        None,
    )
    if not question_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {body.question_id} not found in question bank.",
        )

    question_data = dict(question_data)
    question_data["_actual_time_seconds"] = response_row.time_spent_seconds or 0
    question_data["_subject"]             = mock.subject or ""
    question_data["_exam"]                = mock.exam or ""

    topic    = response_row.topic or question_data.get("topic", "General")
    prof_row = (
        db.query(models.UserProficiency)
        .filter_by(user_id=current_user.id, topic=topic)
        .first()
    )
    prof_score = prof_row.proficiency if prof_row else 400.0
    prof_level = get_proficiency_bucket(prof_score)

    # B1 + B6 Fix: Granular exception handling — never expose API key/URLs
    try:
        explanation_dict, was_cache_hit = await get_or_create_explanation(
            db=db,
            question_data=question_data,
            response_row=response_row,
            proficiency_score=prof_score,
            force_refresh=body.force_refresh,
        )
    except ValueError as exc:
        # Missing API key or model — safe to surface
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except GeminiTruncationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except GeminiParseError as exc:
        logger.error("Tutor parse error for question_id=%s: %s", body.question_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service returned an invalid response. Please retry.",
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Tutor HTTP error: status=%s", exc.response.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service error (HTTP {exc.response.status_code}). Please retry.",
        )
    except httpx.TimeoutException:
        logger.error("Tutor request timed out for question_id=%s", body.question_id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI service timed out. Please retry in a moment.",
        )

    interaction = models.TutorInteraction(
        user_id             = current_user.id,
        attempt_id          = body.attempt_id,
        question_id         = body.question_id,
        proficiency_at_time = prof_score,
        was_cache_hit       = was_cache_hit,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    behavioral_note = build_behavioral_note(response_row, question_data)

    return schemas.TutorExplainResponse(
        interaction_id    = interaction.id,
        question_id       = body.question_id,
        proficiency_level = prof_level,
        proficiency_score = round(prof_score, 1),
        was_cache_hit     = was_cache_hit,
        behavioral_note   = behavioral_note,
        explanation       = schemas.TutorExplanation(**explanation_dict),
    )


# ── POST /tutor/rate ───────────────────────────────────────────────────────────

@router.post("/rate", response_model=schemas.TutorRateResponse)
def rate_explanation(
    body: schemas.TutorRateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (1 <= body.rating <= 5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rating must be between 1 and 5.",
        )

    interaction = (
        db.query(models.TutorInteraction)
        .filter_by(id=body.interaction_id, user_id=current_user.id)
        .first()
    )
    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interaction not found.",
        )

    interaction.user_rating = body.rating
    db.commit()

    return schemas.TutorRateResponse(
        interaction_id = interaction.id,
        rating         = body.rating,
        message        = "Thank you for your feedback!",
    )
