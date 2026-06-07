"""
VYAS v2.0 — Attempts Router
==============================
GET /users/me/attempts — list of the current user's submitted attempts,
shaped to match what Dashboard.jsx expects.
"""
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

import models
from database import get_db
from auth import get_current_user
from services.evaluation import evaluate
from services.proficiency import update_user_proficiency
from services.question_bank import load_ai_mock_questions, load_question_json

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Attempts"])


def _load_mock_payload(db: Session, mock: models.MockTest) -> dict:
    if mock.is_ai_generated:
        return load_ai_mock_questions(db, mock.id)
    if not mock.json_file_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mock test is missing its question bank file path.",
        )
    return load_question_json(mock.json_file_path)


def _get_owned_attempt(db: Session, attempt_id: int, user_id: int) -> models.Attempt:
    attempt = (
        db.query(models.Attempt)
        .options(joinedload(models.Attempt.mock_test))
        .filter(models.Attempt.id == attempt_id, models.Attempt.user_id == user_id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")
    return attempt


def _state_objects(raw_answers: list[dict]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            question_id=int(answer.get("question_id")),
            selected_option=answer.get("selected_option"),
            time_spent_seconds=int(answer.get("time_spent_seconds") or 0),
            visit_count=int(answer.get("visit_count") or 0),
            answer_changed_count=int(answer.get("answer_changed_count") or 0),
            was_marked_for_review=bool(answer.get("was_marked_for_review") or False),
        )
        for answer in raw_answers
        if answer.get("question_id") is not None
    ]


@router.get("/users/me/attempts")
def get_my_attempts(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempts = (
        db.query(models.Attempt)
        .options(joinedload(models.Attempt.mock_test))
        .filter(
            models.Attempt.user_id == current_user.id,
            models.Attempt.submitted_at.isnot(None),
        )
        .order_by(models.Attempt.submitted_at.desc())
        .all()
    )

    result = []
    for a in attempts:
        mock = a.mock_test
        score_pct = None
        if a.score is not None and a.total_marks and a.total_marks > 0:
            score_pct = round(a.score / a.total_marks * 100, 1)

        result.append({
            "attempt_id":        a.id,
            "score":             score_pct,
            "accuracy":          round(a.accuracy, 1) if a.accuracy is not None else None,
            "subject":           mock.subject if mock else None,
            "year":              mock.year if mock else None,
            "submitted":         a.submitted_at.isoformat() if a.submitted_at else None,
            "time_taken_seconds": a.time_taken_seconds,
            "total_marks":       a.total_marks,
            "is_ai_generated":   mock.is_ai_generated if mock else False,
        })

    return result


@router.post("/attempts", status_code=201)
def start_attempt(
    body: dict = Body(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mock_id = str(body.get("mock_id") or "").strip()
    if not mock_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="mock_id is required.")

    mock = db.query(models.MockTest).filter_by(id=mock_id).first()
    if not mock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock test not found.")

    mock_payload = _load_mock_payload(db, mock)
    attempt = models.Attempt(user_id=current_user.id, mock_id=mock.id)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "mock_id": mock.id,
        "duration_minutes": mock.duration_minutes,
        "total_marks": mock.total_marks,
        "questions": mock_payload.get("questions", []),
    }


@router.get("/attempts/{attempt_id}")
def get_attempt(
    attempt_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempt = _get_owned_attempt(db, attempt_id, current_user.id)
    mock_payload = _load_mock_payload(db, attempt.mock_test)
    return {
        "attempt_id": attempt.id,
        "mock_id": attempt.mock_id,
        "duration_minutes": attempt.mock_test.duration_minutes,
        "total_marks": attempt.mock_test.total_marks,
        "submitted": attempt.submitted_at is not None,
        "questions": mock_payload.get("questions", []),
    }


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(
    attempt_id: int,
    background_tasks: BackgroundTasks,
    body: dict = Body(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempt = _get_owned_attempt(db, attempt_id, current_user.id)
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt is already submitted.")

    answers = body.get("answers") or []
    if not isinstance(answers, list):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="answers must be a list.")

    states = _state_objects(answers)
    time_taken = int(body.get("time_taken_seconds") or sum(s.time_spent_seconds for s in states))
    mock_payload = _load_mock_payload(db, attempt.mock_test)
    evaluated = evaluate(attempt.id, mock_payload, states, time_taken)

    attempt.score = evaluated["_db_score"]
    attempt.total_marks = evaluated["_db_total_marks"]
    attempt.correct_count = evaluated["_db_correct"]
    attempt.wrong_count = evaluated["_db_wrong"]
    attempt.skipped_count = evaluated["_db_skipped"]
    attempt.accuracy = evaluated["_db_accuracy"]
    attempt.attempt_rate = evaluated["_db_attempt_rate"]
    attempt.time_taken_seconds = evaluated["_db_time"]
    attempt.avg_time_per_question = evaluated["_db_avg_time"]
    attempt.submitted_at = datetime.now(timezone.utc)

    for review in evaluated["question_reviews"]:
        db.add(models.Response(
            attempt_id=attempt.id,
            question_id=review["question_id"],
            selected_option=review["selected_option"],
            is_correct=review["is_correct"],
            marks_awarded=review["marks_awarded"],
            time_spent_seconds=review["time_spent_seconds"],
            visit_count=review["visit_count"],
            answer_changed_count=review["answer_changed_count"],
            was_marked_for_review=review["was_marked_for_review"],
            topic=review["topic"],
            difficulty=review["difficulty"],
        ))

    db.commit()
    background_tasks.add_task(update_user_proficiency, current_user.id, attempt.id)

    return {"attempt_id": attempt.id, **_result_payload(attempt, evaluated)}


@router.get("/attempts/{attempt_id}/result")
def get_attempt_result(
    attempt_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attempt = _get_owned_attempt(db, attempt_id, current_user.id)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt has not been submitted yet.")

    states = [
        SimpleNamespace(
            question_id=response.question_id,
            selected_option=response.selected_option,
            time_spent_seconds=response.time_spent_seconds,
            visit_count=response.visit_count,
            answer_changed_count=response.answer_changed_count,
            was_marked_for_review=response.was_marked_for_review,
        )
        for response in attempt.responses
    ]
    mock_payload = _load_mock_payload(db, attempt.mock_test)
    evaluated = evaluate(attempt.id, mock_payload, states, attempt.time_taken_seconds or 0)

    return _result_payload(attempt, evaluated)


def _result_payload(attempt: models.Attempt, evaluated: dict) -> dict:
    mock = attempt.mock_test
    return {
        "attempt_id": attempt.id,
        "mock_id": attempt.mock_id,
        "subject": mock.subject if mock else "",
        "year": mock.year if mock else "",
        "is_ai_generated": mock.is_ai_generated if mock else False,
        **{key: value for key, value in evaluated.items() if not key.startswith("_db_")},
    }
