"""
VYAS v0.8 — Tutor Service
==========================
v0.8 changes:
  PROVIDER MIGRATION: Replaced Gemini API with Groq (OpenAI-compatible).
  Root cause: Gemini API blocks Render server IPs with FAILED_PRECONDITION
  "User location is not supported". Groq uses OpenAI chat/completions format
  and does not geo-restrict cloud hosting providers.

  Preserved from v0.7:
    - Tutor prompt structure (build_tutor_prompt unchanged)
    - Proficiency bucket logic (get_proficiency_bucket unchanged)
    - Cache layer (get_or_create_explanation, CACHE_TTL_DAYS unchanged)
    - Cache key generation (make_cache_key unchanged)
    - Behavioral note builder (build_behavioral_note unchanged)
    - Retry behaviour (attempts, exponential backoff)
    - Async/await architecture
    - Error handling pattern
    - Logging format
    - Response schema (same explanation dict fields)

  Changed:
    - HTTP endpoint: Gemini generateContent → Groq /chat/completions
    - Auth: query-param key → Authorization: Bearer header
    - Payload: Gemini system_instruction/contents → OpenAI messages array
    - Response extraction: Gemini candidates[0] → Groq choices[0].message.content
    - Config source: os.getenv direct → AppConfig properties
    - API key env var: GEMINI_API_KEY_TUTOR → GROQ_API_KEY
    - Log messages: "Gemini tutor" → "Groq tutor"
"""

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

import models
from config import AppConfig
from services.gemini_utils import (
    _safe_json_extract,
    extract_raw_text_groq,
    check_finish_reason_groq,
    GeminiParseError,
    GeminiTruncationError,
)

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 7
_RETRY_DELAY   = 2.0  # seconds


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


async def call_groq(system_prompt: str, user_message: str) -> dict:
    """
    Call Groq API (OpenAI-compatible) for tutor explanations.

    Uses:
      - GROQ_API_KEY  — Bearer token auth
      - GROQ_MODEL    — model identifier
      - GROQ_BASE_URL — API base URL
      - AI_TIMEOUT, AI_MAX_RETRIES, AI_TEMPERATURE_TUTOR, AI_MAX_TOKENS_TUTOR

    API key is NEVER included in raised exceptions or log messages.
    """
    api_key = AppConfig.GROQ_API_KEY
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured.")

    model = AppConfig.GROQ_MODEL
    if not model:
        raise ValueError("GROQ_MODEL is not configured.")

    base_url    = AppConfig.GROQ_BASE_URL.rstrip("/")
    url         = f"{base_url}/chat/completions"
    timeout     = AppConfig.AI_TIMEOUT
    max_retries = AppConfig.AI_MAX_RETRIES
    temperature = AppConfig.AI_TEMPERATURE_TUTOR
    max_tokens  = AppConfig.AI_MAX_TOKENS_TUTOR

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens":  max_tokens,
    }

    last_exc: Optional[httpx.HTTPStatusError] = None
    timed_out = False
    response: Optional[httpx.Response] = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            last_exc  = None
            timed_out = False
            break  # success
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            logger.error(
                "Groq tutor HTTP error (attempt %d/%d): status=%s body=%r model=%s",
                attempt + 1, max_retries,
                exc.response.status_code,
                exc.response.text[:2000],
                model,
            )
            # 400 (bad request) or 401/403 (auth) — retrying won't help
            if exc.response.status_code in (400, 401, 403):
                raise httpx.HTTPStatusError(
                    f"Groq API returned HTTP {exc.response.status_code}",
                    request=exc.request,
                    response=exc.response,
                ) from exc
            if attempt < max_retries - 1:
                await asyncio.sleep(_RETRY_DELAY * (attempt + 1))
        except httpx.TimeoutException:
            timed_out = True
            logger.error(
                "Groq tutor timeout (attempt %d/%d) after %.1fs",
                attempt + 1, max_retries, timeout,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(_RETRY_DELAY)
    else:
        if timed_out:
            raise httpx.TimeoutException(
                f"Groq tutor timed out after {max_retries} attempts."
            )
        if last_exc is not None:
            raise httpx.HTTPStatusError(
                f"Groq API returned HTTP {last_exc.response.status_code}",
                request=last_exc.request,
                response=last_exc.response,
            ) from last_exc

    data = response.json()
    check_finish_reason_groq(data)
    raw_text = extract_raw_text_groq(data)
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

    logger.info("Calling Groq tutor for question_id=%s bucket=%s",
                response_row.question_id, bucket)
    explanation = await call_groq(system_prompt, user_message)

    if not isinstance(explanation, dict):
        raise GeminiParseError("Groq tutor returned a non-dict JSON object.")

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
