"""
VYAS — Question Bank Loader
============================
Extracted from main.py in Phase 2A so that routers (tutor.py) can
import load_question_json without a circular import.

Phase 0 cache is preserved here — same _QB_CACHE dict, same behaviour.
main.py now imports from here instead of defining locally.
"""

import json
import os
from pathlib import Path

from fastapi import HTTPException, status

QB_ROOT = Path(os.getenv("QB_ROOT", "../question_bank"))

# ── Phase 0: In-memory question bank cache ────────────────────────────────────
# Eliminates repeated disk reads on every start-attempt and get-results call.
# Key: relative file path string → Value: parsed + normalised question dict.
_QB_CACHE: dict[str, dict] = {}


def load_question_json(file_path: str) -> dict:
    """
    Load and parse a question bank JSON file.
    Results are cached in _QB_CACHE after first load.

    Handles two formats:
      1. Flat: { "questions": [...], "exam": ..., ... }
      2. Nested meta: { "meta": { "exam": ... }, "questions": [...] }

    Also resolves passage references:
      If questions reference a passage via parent_passage_id, the passage
      text is embedded directly into each question object.
    """
    if file_path in _QB_CACHE:
        return _QB_CACHE[file_path]

    path = QB_ROOT / file_path
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question bank file not found: {file_path}",
        )

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Step 1 — hoist 'meta' wrapper if present
    if "meta" in raw and isinstance(raw["meta"], dict):
        raw = {**raw["meta"], **raw}
        raw.pop("meta", None)

    # Step 2 — embed passage text into each question via parent_passage_id
    passages = raw.get("passages", [])
    if passages:
        passage_map = {
            p["passage_id"]: p
            for p in passages
            if isinstance(p, dict) and "passage_id" in p
        }
        for q in raw.get("questions", []):
            if q.get("passage"):
                continue
            pid = q.get("parent_passage_id")
            if pid is not None and pid in passage_map:
                p = passage_map[pid]
                title = p.get("passage_title", "").strip()
                body  = p.get("passage", "").strip()
                q["passage"]       = body
                q["passage_title"] = title if title else None

    _QB_CACHE[file_path] = raw
    return raw


# ── Phase 2B: AI mock question loader ─────────────────────────────────────────

def load_ai_mock_questions(db, mock_id: str) -> dict:
    """
    Load questions for an AI-generated mock from the ai_mock_questions table.
    Returns a dict in the same shape as load_question_json() — callers see
    no difference. Questions are ordered by position (1-based).

    Args:
        db:      SQLAlchemy session
        mock_id: The mock_tests.id string (e.g. "ai_CUET_Economics_1718023400")

    Raises:
        HTTPException 404 if no rows found for mock_id.
    """
    import models  # local import to avoid circular dep at module level

    rows = (
        db.query(models.AIMockQuestion)
        .filter_by(mock_id=mock_id)
        .order_by(models.AIMockQuestion.position)
        .all()
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI mock questions not found for mock_id: {mock_id}",
        )

    questions = [row.question_data for row in rows]

    mock = db.query(models.MockTest).filter_by(id=mock_id).first()
    return {
        "questions": questions,
        "exam":    mock.exam    if mock else "",
        "subject": mock.subject if mock else "",
        "year":    mock.year    if mock else "",
    }