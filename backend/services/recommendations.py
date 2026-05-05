"""
VYAS v0.6 — Recommendation Engine
====================================
Fixes applied vs v0.5:
  D1: Exam becomes a HARD FILTER (not a scoring bonus).
      Recommendations now only surface mocks matching the user's preparing_exam
      from their UserProfile. Falls back to all exams if no profile exists.

Algorithm:
  1. Pull user proficiency rows
  2. Read user's preparing_exam from UserProfile (HARD FILTER)
  3. Identify weak subjects (avg proficiency < 450) and strong (> 600)
  4. Pull static mocks NOT yet attempted, filtered by preparing_exam
  5. Score each mock:
       +30 if mock.subject is in weak_subjects
       +20 if mock.subject already has some attempts (continuation)
       -10 if mock.subject is in strong_subjects
  6. Return top 5 ranked mocks
  7. Weak topics list for Dashboard
  8. AI mock suggestion: weakest subject + proficiency-derived difficulty
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

import models

logger = logging.getLogger(__name__)


def _subject_proficiency_map(prof_rows: list) -> dict[str, float]:
    subs: dict[str, list[float]] = {}
    for r in prof_rows:
        subs.setdefault(r.subject, []).append(r.proficiency)
    return {s: sum(v) / len(v) for s, v in subs.items()}


def _attempted_mock_ids(db: Session, user_id: int) -> set[str]:
    rows = (
        db.query(models.Attempt.mock_id)
        .filter(
            models.Attempt.user_id == user_id,
            models.Attempt.submitted_at.isnot(None),
        )
        .distinct()
        .all()
    )
    return {r.mock_id for r in rows}


def _score_mock(
    mock: "models.MockTest",
    weak_subjects: set[str],
    strong_subjects: set[str],
    subject_attempt_counts: dict[str, int],
) -> float:
    """
    D1 Fix: Exam is now a HARD FILTER (applied before scoring),
    so we no longer add exam-familiarity bonus here.
    """
    score = 0.0

    if mock.subject in weak_subjects:
        score += 30.0
    elif mock.subject in strong_subjects:
        score -= 10.0

    if subject_attempt_counts.get(mock.subject, 0) > 0:
        score += 20.0   # already in the user's groove for this subject

    return score


def get_recommendations(db: Session, user_id: int) -> dict:
    """
    Compute the full recommendation payload for a user.
    Returns a plain dict matching the RecommendationResponse schema.
    """
    # ── Step 1: Pull proficiency data ─────────────────────────────────────────
    prof_rows = (
        db.query(models.UserProficiency)
        .filter_by(user_id=user_id)
        .all()
    )

    subject_prof = _subject_proficiency_map(prof_rows)

    # ── Step 2: Classify subjects ─────────────────────────────────────────────
    weak_subjects   = {s for s, score in subject_prof.items() if score < 450}
    strong_subjects = {s for s, score in subject_prof.items() if score > 600}

    # ── Step 3: Overall proficiency summary ───────────────────────────────────
    overall_score = (
        round(sum(r.proficiency for r in prof_rows) / len(prof_rows), 1)
        if prof_rows else 400.0
    )
    overall_level = _level_from_score(overall_score)

    # ── Step 4: Weak topics (for Dashboard + AI Mock targeting) ───────────────
    weak_topic_rows = sorted(
        [r for r in prof_rows if r.accuracy_rate < 0.50 and r.total_count >= 3],
        key=lambda r: r.accuracy_rate,
    )[:5]

    weak_topics = [
        {
            "subject":      r.subject,
            "topic":        r.topic,
            "proficiency":  round(r.proficiency, 1),
            "accuracy_rate": round(r.accuracy_rate * 100, 1),
            "total_count":  r.total_count,
        }
        for r in weak_topic_rows
    ]

    # ── Step 5: D1 — Read exam preference (HARD FILTER) ──────────────────────
    profile = (
        db.query(models.UserProfile)
        .filter_by(user_id=user_id)
        .first()
    )
    preparing_exam: Optional[str] = profile.preparing_exam if profile else None

    if preparing_exam:
        logger.debug(
            "Recommendations hard-filtered by preparing_exam=%s for user=%s",
            preparing_exam, user_id,
        )

    # ── Step 6: Static mock recommendations ───────────────────────────────────
    attempted_ids = _attempted_mock_ids(db, user_id)

    all_attempts = (
        db.query(models.Attempt, models.MockTest)
        .join(models.MockTest, models.MockTest.id == models.Attempt.mock_id)
        .filter(models.Attempt.user_id == user_id)
        .all()
    )
    subject_attempt_counts: dict[str, int] = {}
    for att, mock in all_attempts:
        subject_attempt_counts[mock.subject] = subject_attempt_counts.get(mock.subject, 0) + 1

    # Build base query
    candidate_query = db.query(models.MockTest).filter(
        models.MockTest.is_ai_generated == False,
    )
    if attempted_ids:
        candidate_query = candidate_query.filter(
            models.MockTest.id.notin_(attempted_ids)
        )

    # D1 HARD FILTER: only show mocks for the exam the user is preparing for
    if preparing_exam:
        candidate_query = candidate_query.filter(
            models.MockTest.exam == preparing_exam
        )

    candidates = candidate_query.all()

    scored = sorted(
        candidates,
        key=lambda m: _score_mock(m, weak_subjects, strong_subjects, subject_attempt_counts),
        reverse=True,
    )

    recommended_mocks = [
        {
            "mock_id":          m.id,
            "exam":             m.exam,
            "subject":          m.subject,
            "year":             m.year,
            "duration_minutes": m.duration_minutes,
            "total_marks":      m.total_marks,
            "question_count":   m.question_count,
            "reason":           _reason(m, weak_subjects, strong_subjects, preparing_exam),
        }
        for m in scored[:5]
    ]

    # ── Step 7: AI mock suggestion ────────────────────────────────────────────
    ai_suggestion = None
    if weak_topic_rows:
        worst      = weak_topic_rows[0]
        prof_score = worst.proficiency
        if prof_score < 300:
            suggested_diff = "easy"
        elif prof_score < 600:
            suggested_diff = "medium"
        else:
            suggested_diff = "hard"

        ai_suggestion = {
            "exam":       worst.exam,
            "subject":    worst.subject,
            "topic":      worst.topic,
            "difficulty": suggested_diff,
            "reason": (
                f"{worst.topic} accuracy is {round(worst.accuracy_rate * 100)}% — "
                f"practice {suggested_diff} questions to build confidence."
            ),
        }

    return {
        "overall_level":        overall_level,
        "overall_score":        overall_score,
        "weak_topics":          weak_topics,
        "recommended_mocks":    recommended_mocks,
        "ai_mock_suggestion":   ai_suggestion,
        "has_proficiency_data": len(prof_rows) > 0,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _level_from_score(score: float) -> str:
    if score >= 800: return "Expert"
    if score >= 600: return "Advanced"
    if score >= 300: return "Intermediate"
    return "Beginner"


def _reason(
    mock: "models.MockTest",
    weak_subjects: set[str],
    strong_subjects: set[str],
    preparing_exam: Optional[str],
) -> str:
    if mock.subject in weak_subjects:
        return f"Your {mock.subject} proficiency is low — this paper will help you improve."
    if mock.subject in strong_subjects:
        return f"You're strong here — use this to maintain your {mock.subject} edge."
    if preparing_exam:
        return f"Untried {preparing_exam} paper — expanding your coverage for this exam."
    return "Untried paper — expanding your coverage builds well-rounded preparation."
