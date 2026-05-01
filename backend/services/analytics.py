"""
VYAS Analytics Engine — Module E
Aggregates user performance data for the dashboard.
"""

from sqlalchemy.orm import Session
import models
import schemas


def get_user_analytics(db: Session, user_id: int) -> schemas.UserAnalytics:
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
            topic_mastery=[],
            recent_attempts=[],
        )

    score_pcts = [
        (a.score / a.total_marks * 100)
        for a in attempts
        if a.total_marks and a.total_marks > 0 and a.score is not None
    ]
    accuracies = [a.accuracy for a in attempts if a.accuracy is not None]

    avg_score_pct = round(sum(score_pcts) / len(score_pcts), 1) if score_pcts else 0.0
    avg_accuracy  = round(sum(accuracies) / len(accuracies), 1) if accuracies else 0.0

    # ── Per-topic aggregation across ALL responses ────────────────────────────
    # Structure: { topic -> { subject -> { correct, total, attempts_seen } } }
    topic_data: dict[str, dict] = {}

    for attempt in attempts:
        mt = attempt.mock_test
        subject = mt.subject if mt else "General"
        for resp in attempt.responses:
            t = resp.topic or "General"
            key = t  # topic name is global key; subject is metadata
            if key not in topic_data:
                topic_data[key] = {
                    "topic":    t,
                    "subject":  subject,
                    "correct":  0,
                    "total":    0,
                    "attempts": 0,
                }
            topic_data[key]["total"]   += 1
            topic_data[key]["attempts"] = len(set(
                r.attempt_id for a in attempts for r in a.responses
                if (r.topic or "General") == t
            ))
            if resp.is_correct:
                topic_data[key]["correct"] += 1

    # Build topic_mastery list with accuracy + strength classification
    topic_mastery = []
    for td in topic_data.values():
        acc = round(td["correct"] / td["total"] * 100, 1) if td["total"] else 0.0
        # Only include topics with at least 2 questions seen (avoid noise)
        if td["total"] < 2:
            continue
        strength = (
            "strong"  if acc >= 70 else
            "average" if acc >= 40 else
            "weak"
        )
        topic_mastery.append(schemas.TopicMastery(
            topic=td["topic"],
            subject=td["subject"],
            accuracy=acc,
            correct=td["correct"],
            total=td["total"],
            strength=strength,
        ))

    # Sort: strong first by accuracy desc, then weak by accuracy asc
    topic_mastery.sort(key=lambda x: x.accuracy, reverse=True)

    # Legacy single-value fields (kept for backward compat)
    strongest_topic = topic_mastery[0].topic  if topic_mastery else None
    weakest_topic   = topic_mastery[-1].topic if topic_mastery else None

    recent = []
    for a in attempts[:10]:
        mt = a.mock_test
        recent.append(schemas.AttemptSummary(
            attempt_id=a.id,
            mock_id=a.mock_id,
            subject=mt.subject if mt else "—",
            year=mt.year if mt else "—",
            score=a.score,
            total_marks=a.total_marks,
            accuracy=a.accuracy,
            time_taken_seconds=a.time_taken_seconds,
            started_at=a.started_at,
        ))

    return schemas.UserAnalytics(
        user_id=user_id,
        total_attempts=total_attempts,
        avg_score_percentage=avg_score_pct,
        avg_accuracy=avg_accuracy,
        strongest_topic=strongest_topic,
        weakest_topic=weakest_topic,
        topic_mastery=topic_mastery,
        recent_attempts=recent,
    )
