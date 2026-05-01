"""
VYAS Evaluation Engine — Module D
Scores a submitted attempt and builds the full results payload.
"""

from typing import List, Any


def evaluate(
    attempt_id: int,
    mock_data: dict,
    question_states: List[Any],  # list of QuestionStateIn-like objects
    time_taken_seconds: int,
) -> dict:
    """
    Pure scoring function — no DB access.
    Returns a flat dict containing:
      - All _db_* fields needed to persist on the Attempt row.
      - All fields needed to build the ResultsResponse.
    """
    questions   = {q["id"]: q for q in mock_data["questions"]}
    state_map   = {qs.question_id: qs for qs in question_states}

    total_marks   = sum(q["marks"] for q in mock_data["questions"])
    score         = 0.0
    correct       = 0
    wrong         = 0
    skipped       = 0
    topic_stats: dict[str, dict] = {}
    question_reviews = []

    for qid, q in questions.items():
        qs           = state_map.get(qid)
        selected     = qs.selected_option if qs else None
        correct_opt  = q["correct"]
        topic        = q.get("topic", "General")
        difficulty   = q.get("difficulty", "Medium")
        marks        = float(q.get("marks", 1.0))
        neg_marking  = float(q.get("negative_marking", 0.33))

        # Compute correctness and marks
        if selected is None:
            is_correct   = False
            marks_awarded = 0.0
            skipped      += 1
        elif selected == correct_opt:
            is_correct   = True
            marks_awarded = marks
            correct      += 1
            score        += marks
        else:
            is_correct   = False
            marks_awarded = -neg_marking
            wrong        += 1
            score        += marks_awarded

        # Topic tracking
        if topic not in topic_stats:
            topic_stats[topic] = {"correct": 0, "total": 0}
        topic_stats[topic]["total"] += 1
        if is_correct:
            topic_stats[topic]["correct"] += 1

        question_reviews.append({
            "question_id":          qid,
            "question_text":        q.get("question", ""),
            "passage":              q.get("passage"),
            "options":              q.get("options", {}),
            "selected_option":      selected,
            "correct_option":       correct_opt,
            "is_correct":           is_correct,
            "marks_awarded":        round(marks_awarded, 2),
            "explanation":          q.get("explanation", ""),
            "time_spent_seconds":   qs.time_spent_seconds if qs else 0,
            "visit_count":          qs.visit_count if qs else 0,
            "answer_changed_count": qs.answer_changed_count if qs else 0,
            "was_marked_for_review":qs.was_marked_for_review if qs else False,
            "difficulty":           difficulty,
            "topic":                topic,
        })

    total_q      = len(questions)
    attempted    = correct + wrong
    accuracy     = round((correct / attempted * 100), 1) if attempted else 0.0
    attempt_rate = round((attempted / total_q * 100), 1) if total_q else 0.0
    avg_time     = round(time_taken_seconds / total_q, 1) if total_q else 0.0
    score        = round(score, 2)
    score_pct    = round((score / total_marks * 100), 1) if total_marks else 0.0

    topic_performance = [
        {
            "topic":    t,
            "correct":  v["correct"],
            "total":    v["total"],
            "accuracy": round(v["correct"] / v["total"] * 100, 1),
        }
        for t, v in topic_stats.items()
    ]

    return {
        # ── Persist fields (prefixed _db_) ────────────────────────────────
        "_db_score":       score,
        "_db_total_marks": total_marks,
        "_db_correct":     correct,
        "_db_wrong":       wrong,
        "_db_skipped":     skipped,
        "_db_accuracy":    accuracy,
        "_db_attempt_rate":attempt_rate,
        "_db_time":        time_taken_seconds,
        "_db_avg_time":    avg_time,

        # ── Response fields ───────────────────────────────────────────────
        "score":               score,
        "total_marks":         total_marks,
        "score_percentage":    score_pct,
        "correct_count":       correct,
        "wrong_count":         wrong,
        "skipped_count":       skipped,
        "accuracy":            accuracy,
        "attempt_rate":        attempt_rate,
        "time_taken_seconds":  time_taken_seconds,
        "avg_time_per_question": avg_time,
        "topic_performance":   topic_performance,
        "question_reviews":    question_reviews,
    }