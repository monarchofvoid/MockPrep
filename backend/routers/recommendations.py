"""
VYAS v2.0 — Recommendations Router
=====================================
GET /recommendations — returns onboarding card and proficiency-based
recommendations for Dashboard.jsx.

This implementation returns a valid response shape at all times.
When the user has no attempt history, an onboarding card is shown.
When proficiency data exists, weak topics and suggested mocks are included.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Recommendations"])


@router.get("/recommendations")
def get_recommendations(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check if the user has any proficiency signals
    proficiency_rows = (
        db.query(models.UserProficiency)
        .filter_by(user_id=current_user.id)
        .all()
    )
    has_proficiency = len(proficiency_rows) > 0

    overall_score = 400.0
    overall_level = "Beginner"
    weak_topics = []

    if has_proficiency:
        scores = [r.proficiency for r in proficiency_rows]
        overall_score = round(sum(scores) / len(scores), 1)

        # Simple ELO → level mapping
        if overall_score >= 700:
            overall_level = "Expert"
        elif overall_score >= 600:
            overall_level = "Advanced"
        elif overall_score >= 500:
            overall_level = "Intermediate"
        else:
            overall_level = "Beginner"

        # Weak topics = lowest 3 proficiency rows
        sorted_rows = sorted(proficiency_rows, key=lambda r: r.proficiency)
        weak_topics = [
            {
                "topic":       r.topic,
                "subject":     r.subject,
                "proficiency": round(r.proficiency, 1),
                "level":       overall_level,
            }
            for r in sorted_rows[:3]
        ]

    # Onboarding card shown until user has attempts
    submitted_count = (
        db.query(models.Attempt)
        .filter(
            models.Attempt.user_id == current_user.id,
            models.Attempt.submitted_at.isnot(None),
        )
        .count()
    )

    onboarding_card = None
    if submitted_count == 0:
        onboarding_card = {
            "title":   "Take your first mock test",
            "message": "Complete a test to unlock your personalised performance dashboard.",
            "cta":     "Browse mock tests",
            "cta_url": "/mocks",
        }

    return {
        "has_proficiency_data": has_proficiency,
        "overall_level":        overall_level,
        "overall_score":        overall_score,
        "total_signals":        len(proficiency_rows),
        "weak_topics":          weak_topics,
        "recommended_mocks":    [],       # populated in a future phase
        "ai_mock_suggestion":   None,
        "onboarding_card":      onboarding_card,
    }