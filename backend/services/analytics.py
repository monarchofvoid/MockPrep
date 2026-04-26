"""
Module E (partial) — Analytics Service
Aggregates across all of a user's attempts to surface progress trends,
weak topics, and improvement over time.
"""
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func
import models


def get_user_analytics(db: Session, user_id: int) -> Dict:
    """Return aggregated performance data across all of a user's attempts."""

    attempts = (
        db.query(models.Attempt)
        .filter(
            models.Attempt.user_id == user_id,
            models.Attempt.submitted_at.isnot(None),
        )
        .order_by(models.Attempt.submitted_at.desc())
        .all()
    )

    if not attempts:
        return {
            "user_id": user_id,
            "total_attempts": 0,
            "avg_score_percentage": 0.0,
            "avg_accuracy": 0.0,
            "strongest_topic": None,
            "weakest_topic": None,
            "recent_attempts": [],
        }

    # Aggregate across attempts
    total = len(attempts)
    avg_score_pct = (
        sum((a.score / a.total_marks * 100) for a in attempts if a.total_marks)
        / total
    )
    avg_acc = sum(a.accuracy or 0 for a in attempts) / total

    # Topic aggregation from Response rows
    topic_stats: Dict[str, Dict[str, int]] = {}
    for attempt in attempts:
        for resp in attempt.responses:
            t = resp.topic or "General"
            if t not in topic_stats:
                topic_stats[t] = {"correct": 0, "total": 0}
            topic_stats[t]["total"] += 1
            if resp.is_correct:
                topic_stats[t]["correct"] += 1

    strongest: Optional[str] = None
    weakest: Optional[str] = None
    if topic_stats:
        sorted_topics = sorted(
            topic_stats.items(),
            key=lambda x: x[1]["correct"] / max(x[1]["total"], 1),
        )
        weakest = sorted_topics[0][0]
        strongest = sorted_topics[-1][0]

    recent_attempts = []
    for a in attempts[:10]:
        mt = a.mock_test
        recent_attempts.append({
            "attempt_id": a.id,
            "mock_id": a.mock_id,
            "subject": mt.subject if mt else "—",
            "year": mt.year if mt else "—",
            "score": a.score,
            "total_marks": a.total_marks,
            "accuracy": a.accuracy,
            "time_taken_seconds": a.time_taken_seconds,
            "started_at": a.started_at,
        })

    return {
        "user_id": user_id,
        "total_attempts": total,
        "avg_score_percentage": round(avg_score_pct, 1),
        "avg_accuracy": round(avg_acc, 1),
        "strongest_topic": strongest,
        "weakest_topic": weakest,
        "recent_attempts": recent_attempts,
    }
