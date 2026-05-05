"""
VYAS v0.6 — AI Mock Router
============================
Fixes applied vs v0.5:
  B1: Granular exception handling — API key/URL never in responses
  B5: finishReason check delegated to service layer (gemini_utils)
  B6: No bare `except Exception`
"""

import logging
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import get_current_user
from services.ai_mock import generate_questions, get_difficulty_distribution
from services.gemini_utils import GeminiParseError, GeminiTruncationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-mock", tags=["AI Mock Generator"])

MAX_QUESTIONS   = 20
MIN_QUESTIONS   = 3
MINS_PER_QUESTION = 2.5


@router.post("/generate", response_model=schemas.StartAttemptResponse)
async def generate_ai_mock(
    body: schemas.GenerateAIMockRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    B1 Fix: Exception handling never exposes API keys or URLs.
    B6 Fix: Granular exception types (ValueError, GeminiTruncationError,
            GeminiParseError, httpx.HTTPStatusError, httpx.TimeoutException).
    """
    count = max(MIN_QUESTIONS, min(body.question_count, MAX_QUESTIONS))

    if body.difficulty not in ("auto", "easy", "medium", "hard"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="difficulty must be one of: auto, easy, medium, hard",
        )

    proficiency_score = 400.0
    weak_topics: list[str] = []

    if body.use_proficiency:
        prof_rows = (
            db.query(models.UserProficiency)
            .filter_by(user_id=current_user.id, subject=body.subject)
            .all()
        )
        if prof_rows:
            proficiency_score = sum(r.proficiency for r in prof_rows) / len(prof_rows)
            weak_topics = [
                r.topic for r in prof_rows
                if r.accuracy_rate < 0.50 and r.total_count >= 3
            ]

    # B1 + B6 Fix: Specific exception types, no URL/key in messages
    try:
        questions = await generate_questions(
            exam=body.exam,
            subject=body.subject,
            difficulty=body.difficulty,
            count=count,
            proficiency_score=proficiency_score,
            weak_topics=weak_topics,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except GeminiTruncationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except GeminiParseError as exc:
        logger.error("AI mock parse error for user=%s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service returned an invalid response. Please retry.",
        )
    except httpx.HTTPStatusError as exc:
        logger.error("AI mock HTTP error: status=%s user=%s",
                     exc.response.status_code, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service error (HTTP {exc.response.status_code}). Please retry.",
        )
    except httpx.TimeoutException:
        logger.error("AI mock request timed out for user=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI service timed out. Please retry in a moment.",
        )

    actual_count = len(questions)
    timestamp    = int(time.time())
    mock_id      = f"ai_{body.exam}_{body.subject}_{body.difficulty}_{timestamp}".replace(" ", "_")

    dist        = get_difficulty_distribution(proficiency_score)
    total_marks = float(actual_count * 4)
    duration    = max(5, round(actual_count * MINS_PER_QUESTION))

    mock = models.MockTest(
        id               = mock_id,
        exam             = body.exam,
        subject          = body.subject,
        year             = "AI Generated",
        duration_minutes = duration,
        total_marks      = total_marks,
        question_count   = actual_count,
        json_file_path   = None,
        is_ai_generated  = True,
        ai_generation_params = {
            "exam":               body.exam,
            "subject":            body.subject,
            "difficulty":         body.difficulty,
            "question_count":     count,
            "actual_count":       actual_count,
            "use_proficiency":    body.use_proficiency,
            "proficiency_score":  round(proficiency_score, 2),
            "weak_topics":        weak_topics,
            "difficulty_distribution": dist,
            "generated_at":       datetime.now(timezone.utc).isoformat(),
            "generated_for_user": current_user.id,
        },
    )
    db.add(mock)
    db.flush()

    for i, q in enumerate(questions, start=1):
        db.add(models.AIMockQuestion(
            mock_id       = mock_id,
            question_data = q,
            position      = i,
        ))

    attempt = models.Attempt(user_id=current_user.id, mock_id=mock_id)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    questions_out = [
        schemas.QuestionOut(
            id             = q["id"],
            type           = q.get("type", "mcq"),
            question       = q["question"],
            passage        = q.get("passage"),
            passage_title  = q.get("passage_title"),
            options        = q["options"],
            difficulty     = q["difficulty"],
            topic          = q["topic"],
            marks          = q.get("marks", 4),
            negative_marking = q.get("negative_marking", 1),
        )
        for q in questions
    ]

    return schemas.StartAttemptResponse(
        attempt_id       = attempt.id,
        mock_id          = mock_id,
        questions        = questions_out,
        duration_minutes = duration,
        total_marks      = total_marks,
    )


@router.get("/history", response_model=schemas.AIMockHistoryResponse)
def get_ai_mock_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.MockTest, models.Attempt)
        .join(
            models.Attempt,
            (models.Attempt.mock_id  == models.MockTest.id) &
            (models.Attempt.user_id  == current_user.id),
            isouter=True,
        )
        .filter(models.MockTest.is_ai_generated == True)
        .order_by(models.MockTest.created_at.desc())
        .all()
    )

    items = []
    for mock, attempt in rows:
        params = mock.ai_generation_params or {}
        if params.get("generated_for_user") != current_user.id:
            continue
        items.append(schemas.AIMockHistoryItem(
            mock_id        = mock.id,
            exam           = mock.exam,
            subject        = mock.subject,
            difficulty     = params.get("difficulty", "auto"),
            question_count = mock.question_count,
            attempt_id     = attempt.id if attempt else None,
            score          = attempt.score if attempt else None,
            total_marks    = mock.total_marks,
            created_at     = mock.created_at,
        ))

    return schemas.AIMockHistoryResponse(ai_mocks=items)
