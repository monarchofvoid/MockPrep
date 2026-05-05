"""
VYAS v0.6 — Question Bank Loader
==================================
Fixes applied vs v0.5:
  B4: QB_ROOT resolved via __file__ fallback (not fragile CWD-relative path)
  B7: OSError and JSONDecodeError caught in load_question_json
  D3: Cache documented; safe loading on error
  P3: print() replaced with logging
"""

import json
import logging
import os
from pathlib import Path

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# ── B4 Fix: Deterministic QB_ROOT resolution ──────────────────────────────────
# 1. QB_ROOT env var (absolute path preferred for production)
# 2. Fallback: two directories up from this file (works regardless of CWD)
_env_qb_root = os.getenv("QB_ROOT", "").strip()
if _env_qb_root:
    QB_ROOT = Path(_env_qb_root)
else:
    # __file__ = backend/services/question_bank.py
    # .parent   = backend/services/
    # .parent   = backend/
    # .parent   = project root
    QB_ROOT = Path(__file__).parent.parent.parent / "question_bank"

logger.info("QB_ROOT resolved to: %s (exists=%s)", QB_ROOT, QB_ROOT.exists())

# ── In-memory question bank cache ─────────────────────────────────────────────
# D3: Cache is intentionally not invalidated at runtime (server must restart to
# pick up new JSON files). This is acceptable because question bank files are
# static assets, not user data. Hot-reloading would add complexity without benefit.
# Limitation: new JSON files deployed without a server restart will NOT appear.
_QB_CACHE: dict[str, dict] = {}


def load_question_json(file_path: str) -> dict:
    """
    Load and parse a question bank JSON file.
    Results are cached in _QB_CACHE after first load.

    B7 Fix: Catches OSError and JSONDecodeError with safe HTTP errors.
    B4 Fix: Uses the deterministic QB_ROOT (not CWD-relative).

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

    # B7: Catch file-not-found cleanly
    if not path.exists():
        logger.error("Question bank file not found: %s (QB_ROOT=%s)", file_path, QB_ROOT)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question bank file not found: {file_path}",
        )

    # B7: Catch OS errors (permissions, etc.) and JSON decode errors
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except OSError as exc:
        logger.error("OS error reading question bank %s: %s", file_path, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not read question bank file due to a server error.",
        ) from exc
    except json.JSONDecodeError as exc:
        logger.error("JSON decode error in question bank %s: %s", file_path, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Question bank file contains invalid JSON — please contact support.",
        ) from exc

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
    logger.debug("Loaded and cached question bank: %s (%d questions)",
                 file_path, len(raw.get("questions", [])))
    return raw


# ── AI mock question loader ────────────────────────────────────────────────────

def load_ai_mock_questions(db, mock_id: str) -> dict:
    """
    Load questions for an AI-generated mock from the ai_mock_questions table.
    Returns a dict in the same shape as load_question_json() — callers see
    no difference. Questions are ordered by position (1-based).
    """
    import models  # local import to avoid circular dep at module level

    rows = (
        db.query(models.AIMockQuestion)
        .filter_by(mock_id=mock_id)
        .order_by(models.AIMockQuestion.position)
        .all()
    )

    if not rows:
        logger.error("AI mock questions not found for mock_id=%s", mock_id)
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
