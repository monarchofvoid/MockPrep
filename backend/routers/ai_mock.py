"""
VYAS Phase 2B — AI Mock Router
================================
POST /ai-mock/generate  — Generate a personalized AI mock test
GET  /ai-mock/history   — List the user's AI mock history
"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import get_current_user
from services.ai_mock import generate_questions, get_difficulty_distribution

router = APIRouter(prefix="/ai-mock", tags=["AI Mock Generator"])

# Maximum questions per AI mock (prevent abuse + token overrun)
MAX_QUESTIONS = 20
MIN_QUESTIONS = 3

# Minutes per question (matches real exam pace ~2.5 min/q)
MINS_PER_QUESTION = 2.5


# ── POST /ai-mock/generate ─────────────────────────────────────────────────────

@router.post("/generate", response_model=schemas.StartAttemptResponse)
async def generate_ai_mock(
    body: schemas.GenerateAIMockRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a fresh AI-powered mock test and create an attempt for it.

    Returns a StartAttemptResponse — identical schema to /start-attempt.
    The frontend navigates to /test/{attempt_id} with no additional changes.

    If use_proficiency=True and the user has Phase 1 proficiency data:
      - Difficulty distribution adjusts to their ELO score
      - Weak topics are surfaced to Gemini for targeted question selection

    Question count is clamped to [{MIN_QUESTIONS}, {MAX_QUESTIONS}].
    """
    # ── Input validation ──────────────────────────────────────────────────────
    count = max(MIN_QUESTIONS, min(body.question_count, MAX_QUESTIONS))

    if body.difficulty not in ("auto", "easy", "medium", "hard"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"difficulty must be one of: auto, easy, medium, hard",
        )

    # ── Read proficiency for this subject (Phase 1) ───────────────────────────
    proficiency_score = 400.0   # Intermediate default if Phase 1 data absent
    weak_topics: list[str] = []

    if body.use_proficiency:
        prof_rows = (
            db.query(models.UserProficiency)
            .filter_by(user_id=current_user.id, subject=body.subject)
            .all()
        )
        if prof_rows:
            proficiency_score = sum(r.proficiency for r in prof_rows) / len(prof_rows)
            # Surface topics where accuracy < 50% as weak areas for targeting
            weak_topics = [
                r.topic for r in prof_rows
                if r.accuracy_rate < 0.50 and r.total_count >= 3
            ]

    # ── Generate questions via Gemini ─────────────────────────────────────────
    try:
        questions = await generate_questions(
            exam=body.exam,
            subject=body.subject,
            difficulty=body.difficulty,
            count=count,
            proficiency_score=proficiency_score,
            weak_topics=weak_topics,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI generation failed: {str(e)[:300]}",
        )

    actual_count = len(questions)

    # ── Create MockTest row (ephemeral, no json_file_path) ────────────────────
    timestamp = int(time.time())
    mock_id   = f"ai_{body.exam}_{body.subject}_{body.difficulty}_{timestamp}".replace(" ", "_")

    dist       = get_difficulty_distribution(proficiency_score)
    total_marks = float(actual_count * 4)   # 4 marks per question (CUET standard)
    duration   = max(5, round(actual_count * MINS_PER_QUESTION))

    mock = models.MockTest(
        id             = mock_id,
        exam           = body.exam,
        subject        = body.subject,
        year           = "AI Generated",
        duration_minutes = duration,
        total_marks    = total_marks,
        question_count = actual_count,
        json_file_path = None,            # no file — questions in DB
        is_ai_generated      = True,
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
    db.flush()   # get mock into session before adding questions

    # ── Store questions in ai_mock_questions ──────────────────────────────────
    for i, q in enumerate(questions, start=1):
        db.add(models.AIMockQuestion(
            mock_id       = mock_id,
            question_data = q,
            position      = i,
        ))

    # ── Create Attempt row ────────────────────────────────────────────────────
    attempt = models.Attempt(user_id=current_user.id, mock_id=mock_id)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    # ── Build questions_out (WITHOUT correct answers) ─────────────────────────
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


# ── GET /ai-mock/history ───────────────────────────────────────────────────────

@router.get("/history", response_model=schemas.AIMockHistoryResponse)
def get_ai_mock_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all AI-generated mocks for the authenticated user, newest first.
    Includes attempt score if the mock has been submitted.
    """
    rows = (
        db.query(models.MockTest, models.Attempt)
        .join(
            models.Attempt,
            (models.Attempt.mock_id  == models.MockTest.id) &
            (models.Attempt.user_id  == current_user.id),
            isouter=True,
        )
        .filter(
            models.MockTest.is_ai_generated == True,
            models.MockTest.ai_generation_params["generated_for_user"].astext.cast(
                db.bind.dialect.colspecs.get(type(models.MockTest.id), type(None))
                if hasattr(db, 'bind') else type(None)
            ) == str(current_user.id)
            if False else True,   # fallback: filter post-query (simpler for SQLite compat)
        )
        .order_by(models.MockTest.created_at.desc())
        .all()
    )

    # Post-filter: only mocks generated for this user (checks ai_generation_params)
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
