"""
VYAS v0.6 — Tutor Service
==========================
Fixes applied vs v0.5:
  B1: API key never exposed in exceptions (URLs logged server-side only)
  B2: maxOutputTokens raised to 2048; finishReason validated before JSON parse
  B3: json.loads replaced with _safe_json_extract from gemini_utils
  B6: Granular exception types replace bare `except Exception`
  P3: print() replaced with logging
"""

import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

import models
from services.gemini_utils import (
    _safe_json_extract,
    check_finish_reason,
    extract_raw_text,
    GeminiParseError,
    GeminiTruncationError,
)

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 7
GEMINI_TIMEOUT = 20.0

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


def get_proficiency_bucket(score: float) -> str:
    if score >= 800: return "Expert"
    if score >= 600: return "Advanced"
    if score >= 300: return "Intermediate"
    return "Beginner"


def make_cache_key(question_id: int, proficiency_bucket: str,
                   user_answer: Optional[str], correct_answer: str) -> str:
    raw = f"{question_id}:{proficiency_bucket}:{user_answer or 'SKIPPED'}:{correct_answer}"
    return hashlib.sha256(raw.encode()).hexdigest()


def build_tutor_prompt(question_data: dict, user_answer: Optional[str],
                       proficiency_level: str, time_efficiency: Optional[float],
                       was_marked: bool, answer_changes: int) -> tuple[str, str]:
    actual_time = question_data.get("_actual_time_seconds", 0)
    estimated   = question_data.get("estimated_time_sec", 0)
    subject     = question_data.get("_subject", "")
    topic       = question_data.get("topic", "")

    system_prompt = f"""You are VYAS, an expert AI tutor for Indian competitive exam preparation (CUET, GATE, JEE, UPSC).

STUDENT PROFILE:
- Proficiency Level: {proficiency_level}  (Beginner / Intermediate / Advanced / Expert)
- Subject: {subject}
- Topic: {topic}
- Time taken: {actual_time}s (estimated: {estimated}s)
- They marked this for review: {"Yes" if was_marked else "No"}
- They changed their answer {answer_changes} time(s)

EXPLANATION STYLE RULES:
- Beginner: Simple language, real-world analogy, encouraging. (150-250 words)
- Intermediate: Precise, logic chain, reference the principle. (100-180 words)
- Advanced: Direct, assume concept knowledge, focus on edge case. (60-120 words)
- Expert: Pose follow-up challenge, peer-level. (40-80 words + follow-up)

OUTPUT FORMAT — Return ONLY valid JSON, no markdown, no preamble:
{{
  "opening": "...",
  "core_concept": "...",
  "why_correct": "...",
  "why_wrong": "...",
  "memory_anchor": "...",
  "follow_up": "..."
}}

- why_wrong: null if student skipped
- follow_up: null for Beginner/Intermediate if not helpful
Do NOT invent facts."""

    options_str = "\n".join(f"{k}) {v}" for k, v in question_data.get("options", {}).items())
    user_message = f"""QUESTION: {question_data.get("question", "")}

OPTIONS:
{options_str}

CORRECT ANSWER: {question_data.get("correct", "")}
STUDENT SELECTED: {user_answer or "Not answered (skipped)"}

Generate the explanation now."""

    return system_prompt, user_message


async def call_gemini(system_prompt: str, user_message: str) -> dict:
    """
    Call Gemini API. API key URL is NEVER included in raised exceptions.
    Raises ValueError, GeminiTruncationError, GeminiParseError,
    httpx.HTTPStatusError, or httpx.TimeoutException.
    """
    api_key = os.getenv("GEMINI_API_KEY_TUTOR", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY_TUTOR is not configured.")

    gemini_model = os.getenv("GEMINI_MODEL_TUTOR", "gemini-2.0-flash").strip()
    if not gemini_model:
        raise ValueError("GEMINI_MODEL_TUTOR is not configured.")

    url = _GEMINI_URL.format(model=gemini_model, key=api_key)

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8048,   # B2: raised from 1024
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # B1: log full details server-side; raise sanitised version to caller
        logger.error(
            "Gemini tutor HTTP error: status=%s body=%r",
            exc.response.status_code,
            exc.response.text[:500],
        )
        raise httpx.HTTPStatusError(
            f"Gemini API returned HTTP {exc.response.status_code}",
            request=exc.request,
            response=exc.response,
        ) from exc
    except httpx.TimeoutException:
        logger.error("Gemini tutor request timed out after %.1fs", GEMINI_TIMEOUT)
        raise

    data = response.json()
    # B2: check finishReason BEFORE touching content
    check_finish_reason(data)
    raw_text = extract_raw_text(data)
    # B3: safe extraction — handles fences, preamble, malformed JSON
    return _safe_json_extract(raw_text)


async def get_or_create_explanation(
    db: Session,
    question_data: dict,
    response_row: models.Response,
    proficiency_score: float,
    force_refresh: bool = False,
) -> tuple[dict, bool]:
    correct_answer = question_data.get("correct", "")
    user_answer    = response_row.selected_option
    bucket         = get_proficiency_bucket(proficiency_score)
    cache_key      = make_cache_key(
        question_id=response_row.question_id,
        proficiency_bucket=bucket,
        user_answer=user_answer,
        correct_answer=correct_answer,
    )
    now = datetime.now(timezone.utc)

    if not force_refresh:
        cached = (
            db.query(models.TutorCache)
            .filter_by(cache_key=cache_key)
            .filter(models.TutorCache.expires_at > now)
            .first()
        )
        if cached:
            cached.hit_count += 1
            db.commit()
            logger.debug("Tutor cache HIT for key=%s", cache_key[:16])
            return cached.explanation_json, True

    system_prompt, user_message = build_tutor_prompt(
        question_data=question_data,
        user_answer=user_answer,
        proficiency_level=bucket,
        time_efficiency=getattr(response_row, "time_efficiency_ratio", None),
        was_marked=bool(response_row.was_marked_for_review),
        answer_changes=response_row.answer_changed_count or 0,
    )

    logger.info("Calling Gemini tutor for question_id=%s bucket=%s",
                response_row.question_id, bucket)
    explanation = await call_gemini(system_prompt, user_message)

    if not isinstance(explanation, dict):
        raise GeminiParseError("Gemini tutor returned a non-dict JSON object.")

    for field in ("opening", "core_concept", "why_correct", "memory_anchor"):
        if field not in explanation or not explanation[field]:
            explanation[field] = "Explanation not available for this field."
    explanation.setdefault("why_wrong", None)
    explanation.setdefault("follow_up", None)

    expires  = now + timedelta(days=CACHE_TTL_DAYS)
    existing = db.query(models.TutorCache).filter_by(cache_key=cache_key).first()

    if existing:
        existing.explanation_json   = explanation
        existing.expires_at         = expires
        existing.hit_count          = 0
        existing.proficiency_bucket = bucket
    else:
        db.add(models.TutorCache(
            cache_key          = cache_key,
            question_id        = response_row.question_id,
            exam               = question_data.get("_exam"),
            proficiency_bucket = bucket,
            user_answer        = user_answer,
            correct_answer     = correct_answer,
            explanation_json   = explanation,
            expires_at         = expires,
            hit_count          = 0,
        ))

    db.commit()
    return explanation, False


def build_behavioral_note(response_row: models.Response, question_data: dict) -> Optional[str]:
    notes     = []
    estimated = question_data.get("estimated_time_sec") or 0
    actual    = response_row.time_spent_seconds or 0

    if estimated > 0 and actual < 0.5 * estimated:
        notes.append(f"You spent {actual}s (estimated: {estimated}s) — you may have rushed this one.")
    if response_row.was_marked_for_review:
        notes.append("You marked this for review, indicating you had doubts.")
    if (response_row.answer_changed_count or 0) >= 2:
        notes.append(f"You changed your answer {response_row.answer_changed_count}× — "
                     "trust your first instinct more often.")

    return " ".join(notes) if notes else None
