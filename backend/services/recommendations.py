"""
VYAS — Intelligent Recommendation Engine (v2)
================================================
Changes vs v1:
  - total_signals: exposed as the real count of questions processed into proficiency
  - ELO level: "Unranked" returned when signal count < MIN_SIGNALS_FOR_LEVEL
  - weak_topics filter: min_count dropped to 2 and accuracy threshold raised to 60%
  - onboarding_card: shown when exam has no papers or all papers are attempted
  - overall_score: signal-weighted when proficiency data exists; neutral 400 otherwise
  - Recommendation scoring: enriched with cold-start boost and subject-familiarity
  - Cold-start AI suggestion: always shown even with zero proficiency signals
"""

import logging
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

import models

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

MIN_SIGNALS_FOR_LEVEL: int = 10
MIN_TOPIC_QUESTIONS: int = 2

# Maps profile preparing_exam values (short codes) to the prefixes used in
# mock_tests.exam column (seeded from JSON files).
# e.g. user saves "CUET" but JSON files have "CUET (UG)"
EXAM_ALIAS: dict = {
    "CUET":  "CUET",   # matches "CUET", "CUET (UG)", "CUET (PG)"
    "GATE":  "GATE",
    "JEE":   "JEE",
    "UPSC":  "UPSC",
    "NEET":  "NEET",
    "CAT":   "CAT",
    "OTHER": None,     # no filter — show all exams
}


def _exam_filter(query, exam_code: Optional[str]):
    """
    Apply a LIKE-based exam filter so 'CUET' matches 'CUET (UG)', 'CUET (PG)', etc.
    Returns the query unchanged if exam_code is None or maps to None.
    """
    if not exam_code:
        return query
    prefix = EXAM_ALIAS.get(exam_code, exam_code)
    if not prefix:
        return query
    return query.filter(models.MockTest.exam.ilike(f"{prefix}%"))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _subject_proficiency_map(prof_rows: list) -> dict:
    subs: dict = {}
    for r in prof_rows:
        subs.setdefault(r.subject, []).append(r.proficiency)
    return {s: sum(v) / len(v) for s, v in subs.items()}


def _attempted_mock_ids(db: Session, user_id: int) -> set:
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


def _score_mock(mock, weak_subjects, strong_subjects, subject_attempt_counts, total_signals):
    score = 0.0
    if mock.subject in weak_subjects:
        score += 35.0
    elif mock.subject in strong_subjects:
        score -= 10.0
    if subject_attempt_counts.get(mock.subject, 0) > 0:
        score += 15.0
    if total_signals == 0:
        score += 5.0  # cold-start variety boost
    return score


def _level_from_score(score: float, total_signals: int) -> str:
    if total_signals < MIN_SIGNALS_FOR_LEVEL:
        return "Unranked"
    if score >= 800: return "Expert"
    if score >= 600: return "Advanced"
    if score >= 450: return "Intermediate"
    if score >= 300: return "Developing"
    return "Beginner"


def _reason(mock, weak_subjects, strong_subjects, preparing_exam, total_signals) -> str:
    if mock.subject in weak_subjects:
        return (
            f"Your {mock.subject} proficiency needs work — "
            "this paper targets your most improvable area."
        )
    if mock.subject in strong_subjects:
        return f"You're already strong in {mock.subject} — use this to maintain your edge."
    if total_signals == 0 and preparing_exam:
        return (
            f"Start building your {preparing_exam} foundation — "
            "first attempts unlock your personalised profile."
        )
    if preparing_exam:
        return f"Untried {preparing_exam} paper — broadening your coverage builds exam readiness."
    return "Untried paper — covering more ground improves your overall profile."


# ── Main entry point ───────────────────────────────────────────────────────────

def get_recommendations(db: Session, user_id: int) -> dict:
    # Step 1: Proficiency rows
    prof_rows = (
        db.query(models.UserProficiency)
        .filter_by(user_id=user_id)
        .all()
    )
    total_signals: int = sum(r.total_count for r in prof_rows)
    subject_prof = _subject_proficiency_map(prof_rows)

    # Step 2: Subject classification
    weak_subjects   = {s for s, sc in subject_prof.items() if sc < 450}
    strong_subjects = {s for s, sc in subject_prof.items() if sc > 600}

    # Step 3: Signal-weighted overall score
    if prof_rows and total_signals > 0:
        weighted_sum = sum(r.proficiency * r.total_count for r in prof_rows)
        overall_score = round(weighted_sum / total_signals, 1)
    else:
        overall_score = 400.0
    overall_level = _level_from_score(overall_score, total_signals)

    # Step 4: Weak topics (lower threshold so new users see actionable data)
    weak_topic_rows = sorted(
        [r for r in prof_rows if r.accuracy_rate < 0.60 and r.total_count >= MIN_TOPIC_QUESTIONS],
        key=lambda r: (r.accuracy_rate, -r.total_count),
    )[:5]
    weak_topics = [
        {
            "subject":       r.subject,
            "topic":         r.topic,
            "proficiency":   round(r.proficiency, 1),
            "accuracy_rate": round(r.accuracy_rate * 100, 1),
            "total_count":   r.total_count,
        }
        for r in weak_topic_rows
    ]

    # Step 5: Exam hard-filter
    profile = db.query(models.UserProfile).filter_by(user_id=user_id).first()
    preparing_exam: Optional[str] = profile.preparing_exam if profile else None

    # Step 6: Attempt history
    attempted_ids = _attempted_mock_ids(db, user_id)
    all_attempts = (
        db.query(models.Attempt, models.MockTest)
        .join(models.MockTest, models.MockTest.id == models.Attempt.mock_id)
        .filter(models.Attempt.user_id == user_id)
        .all()
    )
    subject_attempt_counts: dict = {}
    for att, mock in all_attempts:
        subject_attempt_counts[mock.subject] = subject_attempt_counts.get(mock.subject, 0) + 1

    # Step 7: Candidate mocks — include both static AND AI-generated papers
    # AI mocks are real papers the user can take; exclude only those already attempted
    candidate_query = db.query(models.MockTest)
    if attempted_ids:
        candidate_query = candidate_query.filter(models.MockTest.id.notin_(attempted_ids))
    candidate_query = _exam_filter(candidate_query, preparing_exam)
    candidates = candidate_query.all()

    # Step 8: Onboarding card — count ALL papers (static + AI) for this exam
    onboarding_card = None
    if preparing_exam:
        total_exam_q = _exam_filter(db.query(models.MockTest), preparing_exam)
        total_exam_papers = total_exam_q.count()
        if total_exam_papers == 0:
            onboarding_card = {
                "title":   f"{preparing_exam} papers coming soon",
                "message": (
                    f"We're adding {preparing_exam} question papers. "
                    "Meanwhile, our AI Mock Generator creates personalised practice sets "
                    "tailored to your exam syllabus right now."
                ),
                "cta":     "Generate AI Mock →",
                "cta_url": "/ai-mock",
            }
        elif not candidates and attempted_ids:
            onboarding_card = {
                "title":   "You've covered all available papers!",
                "message": (
                    f"Excellent — you've attempted every available {preparing_exam} paper. "
                    "Keep your momentum with AI-generated mocks that adapt to your weak areas."
                ),
                "cta":     "Generate AI Mock →",
                "cta_url": "/ai-mock",
            }

    # Step 9: Score and rank
    scored = sorted(
        candidates,
        key=lambda m: _score_mock(m, weak_subjects, strong_subjects, subject_attempt_counts, total_signals),
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
            "is_ai_generated":  m.is_ai_generated,
            "reason":           _reason(m, weak_subjects, strong_subjects, preparing_exam, total_signals),
        }
        for m in scored[:5]
    ]

    # Step 10: AI suggestion
    ai_suggestion = None
    if weak_topic_rows:
        worst = weak_topic_rows[0]
        prof_score = worst.proficiency
        suggested_diff = "easy" if prof_score < 300 else ("medium" if prof_score < 500 else "hard")
        ai_suggestion = {
            "exam":       worst.exam,
            "subject":    worst.subject,
            "topic":      worst.topic,
            "difficulty": suggested_diff,
            "reason": (
                f"{worst.topic} accuracy is {round(worst.accuracy_rate * 100)}% — "
                f"a focused {suggested_diff} AI mock will target this gap directly."
            ),
        }
    elif preparing_exam:
        # Cold start — no proficiency data yet
        ai_suggestion = {
            "exam":       preparing_exam,
            "subject":    preparing_exam,
            "topic":      "General",
            "difficulty": "medium",
            "reason": (
                f"Start with a personalised {preparing_exam} AI mock to build "
                "your baseline profile and unlock smart recommendations."
            ),
        }

    return {
        "overall_level":        overall_level,
        "overall_score":        overall_score,
        "has_proficiency_data": len(prof_rows) > 0,
        "total_signals":        total_signals,
        "weak_topics":          weak_topics,
        "recommended_mocks":    recommended_mocks,
        "ai_mock_suggestion":   ai_suggestion,
        "onboarding_card":      onboarding_card,
    }