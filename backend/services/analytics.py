"""
VYAS Analytics Engine — Module E
Aggregates user performance data for the dashboard.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
import models
import schemas


def get_user_analytics(db: Session, user_id: int) -> schemas.UserAnalytics:
    """
    Aggregate all submitted attempts for a user into a summary.
    Returns UserAnalytics schema.
    """
    # All submitted attempts
    attempts = (
        db.query(models.Attempt)
        .filter_by(user_id=user_id)
        .filter(models.Attempt.submitted_at.isnot(None))
        .order_by(models.Attempt.submitted_at.desc())
        .all()
    )

    total_attempts = len(attempts)

    if total_attempts == 0:
        return schemas.UserAnalytics(
            user_id=user_id,
            total_attempts=0,
            avg_score_percentage=0.0,
            avg_accuracy=0.0,
            strongest_topic=None,
            weakest_topic=None,
            recent_attempts=[],
        )

    # Score + accuracy averages
    score_pcts = [
        (a.score / a.total_marks * 100)
        for a in attempts
        if a.total_marks and a.total_marks > 0 and a.score is not None
    ]
    accuracies = [a.accuracy for a in attempts if a.accuracy is not None]

    avg_score_pct = round(sum(score_pcts) / len(score_pcts), 1) if score_pcts else 0.0
    avg_accuracy  = round(sum(accuracies) / len(accuracies), 1) if accuracies else 0.0

    # Topic aggregation across all responses
    topic_stats: dict[str, dict] = {}
    for attempt in attempts:
        for resp in attempt.responses:
            t = resp.topic or "General"
            if t not in topic_stats:
                topic_stats[t] = {"correct": 0, "total": 0}
            topic_stats[t]["total"] += 1
            if resp.is_correct:
                topic_stats[t]["correct"] += 1

    strongest_topic = None
    weakest_topic   = None

    if topic_stats:
        sorted_topics = sorted(
            topic_stats.items(),
            key=lambda kv: kv[1]["correct"] / kv[1]["total"] if kv[1]["total"] else 0,
        )
        weakest_topic   = sorted_topics[0][0]  if sorted_topics else None
        strongest_topic = sorted_topics[-1][0] if sorted_topics else None

    # Recent attempts (max 10)
    recent = []
    for a in attempts[:10]:
        mt = a.mock_test
        recent.append(
            schemas.AttemptSummary(
                attempt_id=a.id,
                mock_id=a.mock_id,
                subject=mt.subject if mt else "—",
                year=mt.year if mt else "—",
                score=a.score,
                total_marks=a.total_marks,
                accuracy=a.accuracy,
                time_taken_seconds=a.time_taken_seconds,
                started_at=a.started_at,
            )
        )

    return schemas.UserAnalytics(
        user_id=user_id,
        total_attempts=total_attempts,
        avg_score_percentage=avg_score_pct,
        avg_accuracy=avg_accuracy,
        strongest_topic=strongest_topic,
        weakest_topic=weakest_topic,
        recent_attempts=recent,
    )
