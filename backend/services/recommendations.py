"""
VYAS Phase 3 — Recommendation Engine
======================================
Pure computation on existing tables (user_proficiency + attempts + mock_tests).
No AI calls. No new DB tables.

Public API:
  get_recommendations(db, user_id) → RecommendationPayload
    Returns:
      - ranked list of recommended static mocks (by subject match + not yet attempted)
      - weak_topics list (proficiency < 40% accuracy, sorted by severity)
      - next_ai_mock suggestion (subject + difficulty based on weakest area)
      - overall_level + overall_score from proficiency

Algorithm:
  1. Pull user proficiency rows (from Phase 1)
  2. Identify weak subjects (avg proficiency < 450) and strong (> 600)
  3. Pull all static mocks not yet attempted by the user
  4. Score each mock:
       +30 if mock.subject is in weak_subjects       (needs work)
       +20 if mock.subject already has some attempts  (continuation)
       +10 if mock.exam matches the most-attempted exam (familiarity)
       -10 if mock.subject is in strong_subjects      (already solid)
  5. Return top 5 ranked mocks
  6. Identify top 3 weak topics (lowest accuracy, min 3 attempts)
  7. Suggest next AI mock: weakest subject + proficiency-derived difficulty
"""

from typing import Optional
from sqlalchemy.orm import Session

import models


# ── Data structures (plain dicts — schemas are in schemas.py) ─────────────────

def _subject_proficiency_map(prof_rows: list) -> dict[str, float]:
    """Average ELO score per subject across all topic rows."""
    subs: dict[str, list[float]] = {}
    for r in prof_rows:
        subs.setdefault(r.subject, []).append(r.proficiency)
    return {s: sum(v) / len(v) for s, v in subs.items()}


def _attempted_mock_ids(db: Session, user_id: int) -> set[str]:
    """Return mock IDs the user has submitted at least one attempt for."""
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


def _most_attempted_exam(db: Session, user_id: int) -> Optional[str]:
    """Return the exam the user has attempted most frequently."""
    from sqlalchemy import func

    result = (
        db.query(models.MockTest.exam, func.count(models.Attempt.id).label("cnt"))
        .join(models.Attempt, models.Attempt.mock_id == models.MockTest.id)
        .filter(models.Attempt.user_id == user_id)
        .group_by(models.MockTest.exam)
        .order_by(func.count(models.Attempt.id).desc())
        .first()
    )
    return result.exam if result else None


def _score_mock(
    mock: "models.MockTest",
    weak_subjects: set[str],
    strong_subjects: set[str],
    subject_attempt_counts: dict[str, int],
    top_exam: Optional[str],
) -> float:
    """Heuristic relevance score for a single mock."""
    score = 0.0

    if mock.subject in weak_subjects:
        score += 30.0   # user needs work here
    elif mock.subject in strong_subjects:
        score -= 10.0   # user already solid here

    if subject_attempt_counts.get(mock.subject, 0) > 0:
        score += 20.0   # already in the user's groove for this subject

    if top_exam and mock.exam == top_exam:
        score += 10.0   # exam familiarity

    return score


# ── Main recommendation function ──────────────────────────────────────────────

def get_recommendations(db: Session, user_id: int) -> dict:
    """
    Compute the full recommendation payload for a user.
    Returns a plain dict matching the RecommendationResponse schema.
    Safe to call for new users (returns sane defaults when no proficiency data).
    """
    # ── Step 1: Pull proficiency data ─────────────────────────────────────────
    prof_rows = (
        db.query(models.UserProficiency)
        .filter_by(user_id=user_id)
        .all()
    )

    subject_prof = _subject_proficiency_map(prof_rows)

    # ── Step 2: Classify subjects ─────────────────────────────────────────────
    # Weak < 450 ELO, Strong > 600 ELO  (Intermediate boundary = 400)
    weak_subjects  = {s for s, score in subject_prof.items() if score < 450}
    strong_subjects = {s for s, score in subject_prof.items() if score > 600}

    # ── Step 3: Overall proficiency summary ───────────────────────────────────
    if prof_rows:
        overall_score = round(sum(r.proficiency for r in prof_rows) / len(prof_rows), 1)
    else:
        overall_score = 400.0

    overall_level = _level_from_score(overall_score)

    # ── Step 4: Weak topics (for Dashboard + AI Mock targeting) ───────────────
    weak_topic_rows = sorted(
        [r for r in prof_rows if r.accuracy_rate < 0.50 and r.total_count >= 3],
        key=lambda r: r.accuracy_rate,
    )[:5]   # top 5 weakest

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

    # ── Step 5: Static mock recommendations ──────────────────────────────────
    attempted_ids = _attempted_mock_ids(db, user_id)
    top_exam      = _most_attempted_exam(db, user_id)

    # Count how many times user has attempted each subject (any mock)
    all_attempts = (
        db.query(models.Attempt, models.MockTest)
        .join(models.MockTest, models.MockTest.id == models.Attempt.mock_id)
        .filter(models.Attempt.user_id == user_id)
        .all()
    )
    subject_attempt_counts: dict[str, int] = {}
    for att, mock in all_attempts:
        subject_attempt_counts[mock.subject] = subject_attempt_counts.get(mock.subject, 0) + 1

    # Candidate mocks: static, not yet submitted
    candidates = (
        db.query(models.MockTest)
        .filter(
            models.MockTest.is_ai_generated == False,
            models.MockTest.id.notin_(attempted_ids) if attempted_ids else True,
        )
        .all()
    )

    scored = sorted(
        candidates,
        key=lambda m: _score_mock(m, weak_subjects, strong_subjects,
                                   subject_attempt_counts, top_exam),
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
            "reason":           _reason(m, weak_subjects, strong_subjects, top_exam),
        }
        for m in scored[:5]
    ]

    # ── Step 6: AI mock suggestion ────────────────────────────────────────────
    # Suggest working on the weakest subject at difficulty matching their level
    ai_suggestion = None
    if weak_topic_rows:
        worst     = weak_topic_rows[0]
        prof_score = worst.proficiency
        if prof_score < 300:
            suggested_diff = "easy"
        elif prof_score < 600:
            suggested_diff = "medium"
        else:
            suggested_diff = "hard"

        ai_suggestion = {
            "exam":           worst.exam,
            "subject":        worst.subject,
            "topic":          worst.topic,
            "difficulty":     suggested_diff,
            "reason":         (
                f"{worst.topic} accuracy is {round(worst.accuracy_rate * 100)}% — "
                f"practice {suggested_diff} questions to build confidence."
            ),
        }
    elif not prof_rows:
        # Cold start — new user with no data yet
        ai_suggestion = None   # no suggestion until they have data

    return {
        "overall_level":      overall_level,
        "overall_score":      overall_score,
        "weak_topics":        weak_topics,
        "recommended_mocks":  recommended_mocks,
        "ai_mock_suggestion": ai_suggestion,
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
    top_exam: Optional[str],
) -> str:
    """Human-readable reason string for the recommendation."""
    if mock.subject in weak_subjects:
        return f"Your {mock.subject} proficiency is low — this paper will help you improve."
    if mock.exam == top_exam and mock.subject not in strong_subjects:
        return f"Matches your primary exam ({mock.exam}) — untried paper in this series."
    if mock.subject in strong_subjects:
        return f"You're strong here — use this to maintain your {mock.subject} edge."
    return "Untried paper — expanding your coverage builds well-rounded preparation."
