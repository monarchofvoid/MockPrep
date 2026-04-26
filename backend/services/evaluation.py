"""
Module D — Evaluation Engine
Computes score, accuracy, topic-wise performance, and per-question review
given the submitted responses and the loaded question bank JSON.
"""
from typing import List, Dict, Any
from schemas import (
    QuestionStateIn, TopicPerformance,
    QuestionReview, ResultsResponse
)


def evaluate(
    attempt_id: int,
    mock_data: Dict[str, Any],
    question_states: List[QuestionStateIn],
    time_taken_seconds: int,
) -> Dict[str, Any]:
    """
    Core evaluation function.

    Args:
        attempt_id:           DB attempt ID
        mock_data:            Parsed question bank JSON (includes correct answers)
        question_states:      List of per-question tracking data from the frontend
        time_taken_seconds:   Total time the user spent on the test

    Returns:
        Dict ready to construct a ResultsResponse and persist to DB.
    """
    questions = mock_data["questions"]
    total_marks = mock_data.get("total_marks", sum(q["marks"] for q in questions))

    # Build a lookup from question_id → state submitted
    state_map: Dict[int, QuestionStateIn] = {qs.question_id: qs for qs in question_states}

    score = 0.0
    correct_count = 0
    wrong_count = 0
    skipped_count = 0
    attempted_count = 0

    topic_map: Dict[str, Dict[str, int]] = {}   # topic → {correct, total}
    question_reviews: List[Dict] = []

    for q in questions:
        qid = q["id"]
        qs = state_map.get(qid)

        topic = q.get("topic", "General")
        difficulty = q.get("difficulty", "medium")

        if topic not in topic_map:
            topic_map[topic] = {"correct": 0, "total": 0}
        topic_map[topic]["total"] += 1

        selected = qs.selected_option if qs else None
        is_correct = False
        marks_awarded = 0.0

        if selected is None:
            skipped_count += 1
        else:
            attempted_count += 1
            if selected == q["correct"]:
                is_correct = True
                correct_count += 1
                marks_awarded = q["marks"]
                score += marks_awarded
                topic_map[topic]["correct"] += 1
            else:
                wrong_count += 1
                marks_awarded = -q.get("negative_marking", 0)
                score += marks_awarded   # score decreases

        question_reviews.append({
            "question_id": qid,
            "question_text": q["question"],
            "options": q["options"],
            "selected_option": selected,
            "correct_option": q["correct"],
            "is_correct": is_correct,
            "marks_awarded": round(marks_awarded, 2),
            "explanation": q.get("explanation", ""),
            "time_spent_seconds": qs.time_spent_seconds if qs else 0,
            "visit_count": qs.visit_count if qs else 0,
            "answer_changed_count": qs.answer_changed_count if qs else 0,
            "was_marked_for_review": qs.was_marked_for_review if qs else False,
            "difficulty": difficulty,
            "topic": topic,
            "is_correct_flag": is_correct,
            "selected": selected,
        })

    score = max(0.0, round(score, 2))   # floor at 0

    accuracy = round(correct_count / attempted_count * 100, 1) if attempted_count else 0.0
    attempt_rate = round(attempted_count / len(questions) * 100, 1) if questions else 0.0
    score_pct = round(score / total_marks * 100, 1) if total_marks else 0.0
    avg_time = round(time_taken_seconds / attempted_count, 1) if attempted_count else 0.0

    # Build topic performance list
    topic_performance = [
        {
            "topic": t,
            "correct": v["correct"],
            "total": v["total"],
            "accuracy": round(v["correct"] / v["total"] * 100, 1),
        }
        for t, v in topic_map.items()
    ]
    topic_performance.sort(key=lambda x: x["accuracy"])   # weakest first

    return {
        "score": score,
        "total_marks": total_marks,
        "score_percentage": score_pct,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "skipped_count": skipped_count,
        "accuracy": accuracy,
        "attempt_rate": attempt_rate,
        "time_taken_seconds": time_taken_seconds,
        "avg_time_per_question": avg_time,
        "topic_performance": topic_performance,
        "question_reviews": question_reviews,
        # Flat fields for DB columns
        "_db_score": score,
        "_db_total_marks": total_marks,
        "_db_correct": correct_count,
        "_db_wrong": wrong_count,
        "_db_skipped": skipped_count,
        "_db_accuracy": accuracy,
        "_db_attempt_rate": attempt_rate,
        "_db_time": time_taken_seconds,
        "_db_avg_time": avg_time,
    }
