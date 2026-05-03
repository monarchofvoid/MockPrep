"""
VYAS — Tutor Router
====================
Phase 1: GET /tutor/proficiency
Phase 2A (to be added): POST /tutor/explain, POST /tutor/rate
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import get_current_user
from services.proficiency import get_proficiency_level

router = APIRouter(prefix="/tutor", tags=["Tutor"])


@router.get("/proficiency", response_model=schemas.UserProficiencyResponse)
def get_proficiency(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the authenticated user's full proficiency profile.

    One entry per (exam, subject, topic) triplet they have attempted.
    Includes ELO score, accuracy breakdown by difficulty, and time efficiency.

    Requires at least one submitted attempt — returns empty topics list
    for new users (this is correct; proficiency is earned, not assumed).
    """
    rows = (
        db.query(models.UserProficiency)
        .filter_by(user_id=current_user.id)
        .order_by(
            models.UserProficiency.subject,
            models.UserProficiency.topic,
        )
        .all()
    )

    # ── Compute overall score as mean across all tracked topics ───────────────
    if rows:
        overall_score = round(sum(r.proficiency for r in rows) / len(rows), 2)
    else:
        overall_score = 400.0   # default: Intermediate boundary

    overall_level = get_proficiency_level(overall_score)

    # ── Build per-topic list ──────────────────────────────────────────────────
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
