"""
VYAS v2.0 — Analytics Router
==============================
GET /analytics/me — aggregate stats across the user's submitted attempts.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

import models
from database import get_db
from auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/me")
def get_my_analytics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempts = (
        db.query(models.Attempt)
        .filter(
            models.Attempt.user_id == current_user.id,
            models.Attempt.submitted_at.isnot(None),
        )
        .all()
    )

    total = len(attempts)
    avg_score = 0.0
    avg_accuracy = 0.0

    if total > 0:
        scores = [
            (a.score / a.total_marks * 100)
            for a in attempts
            if a.score is not None and a.total_marks and a.total_marks > 0
        ]
        accuracies = [a.accuracy for a in attempts if a.accuracy is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0

    return {
        "total_attempts": total,
        "avg_score_percentage": round(avg_score, 2),
        "avg_accuracy": round(avg_accuracy, 2),
        "topic_mastery": [],   # populated in a future phase
    }