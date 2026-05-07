"""
VYAS v0.7 — AI Mock Generator Service
======================================
Fixes applied vs v0.6:
  ROOT CAUSE FIX: Removed `responseMimeType: "application/json"` from the
    Gemini payload. In Gemini API 2025+, using JSON mode without a
    `responseSchema` causes HTTP 400. _safe_json_extract() handles all
    extraction patterns robustly, so JSON mode is not needed.
  Model default updated to gemini-2.0-flash-001 (stable pinned version).
  Added exponential-backoff retry (2 attempts) for transient 5xx/429 errors.
  Enhanced error logging: full Gemini error body logged up to 2000 chars.
"""

import asyncio
import logging
import os
from typing import Optional

import httpx

from services.gemini_utils import (
    _safe_json_extract,
    check_finish_reason,
    extract_raw_text,
    GeminiParseError,
    GeminiTruncationError,
)

logger = logging.getLogger(__name__)

GEMINI_TIMEOUT = 50.0
GEMINI_RETRY_ATTEMPTS = 2
GEMINI_RETRY_DELAY = 2.0  # seconds

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


# ── Difficulty distributions ───────────────────────────────────────────────────

def get_difficulty_distribution(proficiency_score: float) -> dict:
    if proficiency_score < 300:
        return {"easy": 0.60, "medium": 0.35, "hard": 0.05}
    elif proficiency_score < 600:
        return {"easy": 0.20, "medium": 0.55, "hard": 0.25}
    elif proficiency_score < 800:
        return {"easy": 0.05, "medium": 0.35, "hard": 0.60}
    else:
        return {"easy": 0.00, "medium": 0.20, "hard": 0.80}


def counts_from_distribution(total: int, dist: dict) -> dict:
    easy   = round(total * dist["easy"])
    hard   = round(total * dist["hard"])
    medium = total - easy - hard
    return {"easy": max(0, easy), "medium": max(0, medium), "hard": max(0, hard)}


# ── Question validation ────────────────────────────────────────────────────────

def validate_ai_question(raw: dict, index: int) -> dict:
    required = ["question", "options", "correct", "explanation", "difficulty", "topic"]
    for field in required:
        if field not in raw or not raw[field]:
            raise ValueError(f"Question {index + 1}: missing required field '{field}'")

    if not isinstance(raw["options"], dict):
        raise ValueError(f"Question {index + 1}: 'options' must be a dict")

    if len(raw["options"]) != 4:
        raise ValueError(f"Question {index + 1}: must have exactly 4 options, got {len(raw['options'])}")

    for key in raw["options"]:
        if key not in ("A", "B", "C", "D"):
            raise ValueError(f"Question {index + 1}: option keys must be A/B/C/D, got '{key}'")

    if raw["correct"] not in raw["options"]:
        raise ValueError(
            f"Question {index + 1}: correct='{raw['correct']}' not in options keys"
        )

    if raw["difficulty"] not in ("easy", "medium", "hard"):
        raw["difficulty"] = "medium"

    raw.setdefault("id",               index + 1)
    raw.setdefault("type",             "mcq")
    raw.setdefault("marks",            4)
    raw.setdefault("negative_marking", 1)
    raw.setdefault("passage",          None)
    raw.setdefault("passage_title",    None)
    raw.setdefault("subtopic",         None)
    raw.setdefault("estimated_time_sec", None)
    raw["id"] = index + 1

    return raw


# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_generation_prompt(
    exam: str, subject: str, difficulty: str, count: int,
    dist: dict, weak_topics: list[str],
) -> tuple[str, str]:
    topic_hint = ""
    if weak_topics:
        top3 = ", ".join(weak_topics[:3])
        topic_hint = f"\nPRIORITY TOPICS (student's weak areas — weight these heavily): {top3}"

    if difficulty == "auto":
        diff_instruction = (
            f"Generate exactly {dist['easy']} easy, {dist['medium']} medium, "
            f"and {dist['hard']} hard questions."
        )
    else:
        diff_instruction = f"All {count} questions must be {difficulty} difficulty."

    system_prompt = f"""You are an expert question setter for Indian competitive exams ({exam}).
Generate high-quality, original MCQ questions for the subject: {subject}.

RULES:
1. Generate exactly {count} questions. No more, no less.
2. {diff_instruction}
3. Each question must have exactly 4 options labeled A, B, C, D.
4. The 'correct' field must be one of: A, B, C, or D — and must actually be correct.
5. All distractors must be plausible — not obviously wrong.
6. 'explanation' must be 2-4 sentences explaining WHY the correct answer is right.
7. Each question must have a 'topic' field (the sub-topic within {subject}).
8. Do NOT repeat questions or use trivial true/false phrasing.
9. Questions must be suitable for {exam} level.
10. Do NOT include any answer hints in the question text itself.{topic_hint}

OUTPUT FORMAT — Return ONLY a valid JSON array, no markdown, no preamble:
[
  {{
    "id": 1,
    "type": "mcq",
    "question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct": "B",
    "explanation": "...",
    "difficulty": "easy|medium|hard",
    "topic": "...",
    "marks": 4,
    "negative_marking": 1
  }}
]"""

    user_message = (
        f"Generate {count} {exam} {subject} MCQ questions now. "
        f"Output ONLY the JSON array — nothing else."
    )

    return system_prompt, user_message


# ── Gemini API call ────────────────────────────────────────────────────────────

async def call_gemini_generate(system_prompt: str, user_message: str) -> list[dict]:
    """
    Call Gemini to generate questions.

    ROOT CAUSE FIX (v0.7):
      `responseMimeType: "application/json"` REMOVED from payload.
      In Gemini API 2025+, JSON mode without `responseSchema` returns HTTP 400.
      _safe_json_extract() handles all JSON patterns robustly — no JSON mode needed.

    API key URL is NEVER included in raised exceptions.
    """
    api_key = os.getenv("GEMINI_API_KEY_MOCK", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY_MOCK is not configured.")

    # v0.7: default is stable pinned version, not floating alias
    gemini_model = os.getenv("GEMINI_MODEL_MOCK", "gemini-2.0-flash-001").strip()
    if not gemini_model:
        raise ValueError("GEMINI_MODEL_MOCK is not configured.")

    url = _GEMINI_URL.format(model=gemini_model, key=api_key)

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {
            "temperature":     0.5,
            "maxOutputTokens": 8192,
            # responseMimeType intentionally OMITTED — causes HTTP 400 in
            # Gemini API 2025+ when used without responseSchema.
            # _safe_json_extract() handles all extraction patterns.
        },
    }

    last_exc: Optional[httpx.HTTPStatusError] = None
    timed_out = False

    for attempt in range(GEMINI_RETRY_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            last_exc = None
            timed_out = False
            break  # success
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            logger.error(
                "Gemini mock HTTP error (attempt %d/%d): status=%s body=%r model=%s",
                attempt + 1, GEMINI_RETRY_ATTEMPTS,
                exc.response.status_code,
                exc.response.text[:2000],
                gemini_model,
            )
            # 400 = bad request — no retry benefit; fail immediately
            if exc.response.status_code == 400:
                raise httpx.HTTPStatusError(
                    f"Gemini API returned HTTP {exc.response.status_code}",
                    request=exc.request,
                    response=exc.response,
                ) from exc
            if attempt < GEMINI_RETRY_ATTEMPTS - 1:
                await asyncio.sleep(GEMINI_RETRY_DELAY * (attempt + 1))
        except httpx.TimeoutException:
            timed_out = True
            logger.error(
                "Gemini mock timeout (attempt %d/%d) after %.1fs",
                attempt + 1, GEMINI_RETRY_ATTEMPTS, GEMINI_TIMEOUT,
            )
            if attempt < GEMINI_RETRY_ATTEMPTS - 1:
                await asyncio.sleep(GEMINI_RETRY_DELAY)
    else:
        # Exhausted all retries
        if timed_out:
            raise httpx.TimeoutException(
                f"Gemini mock timed out after {GEMINI_RETRY_ATTEMPTS} attempts."
            )
        if last_exc is not None:
            raise httpx.HTTPStatusError(
                f"Gemini API returned HTTP {last_exc.response.status_code}",
                request=last_exc.request,
                response=last_exc.response,
            ) from last_exc

    data = response.json()

    # B5: check finishReason BEFORE touching content
    check_finish_reason(data)
    raw_text = extract_raw_text(data)

    # B3: safe JSON extraction
    parsed = _safe_json_extract(raw_text)

    if not isinstance(parsed, list):
        raise GeminiParseError(f"Expected a JSON array, got {type(parsed).__name__}")

    return parsed


# ── Main generation entry point ────────────────────────────────────────────────

async def generate_questions(
    exam: str,
    subject: str,
    difficulty: str,
    count: int,
    proficiency_score: float = 400.0,
    weak_topics: Optional[list[str]] = None,
) -> list[dict]:
    count       = min(count, 20)
    weak_topics = weak_topics or []

    dist   = get_difficulty_distribution(proficiency_score)
    counts = counts_from_distribution(count, dist)

    system_prompt, user_message = build_generation_prompt(
        exam=exam, subject=subject, difficulty=difficulty,
        count=count, dist=counts, weak_topics=weak_topics,
    )

    logger.info(
        "Generating AI mock: exam=%s subject=%s difficulty=%s count=%d model=%s",
        exam, subject, difficulty, count,
        os.getenv("GEMINI_MODEL_MOCK", "gemini-2.0-flash-001"),
    )
    raw_questions = await call_gemini_generate(system_prompt, user_message)

    validated = []
    errors    = []
    for i, raw in enumerate(raw_questions[:count]):
        try:
            validated.append(validate_ai_question(raw, i))
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        # P3: use logger instead of print
        logger.warning(
            "AI mock validation errors (%d/%d): %s",
            len(errors), len(raw_questions),
            "; ".join(errors[:5]),
        )

    if len(validated) < max(1, count // 2):
        raise ValueError(
            f"Too few valid questions generated ({len(validated)}/{count}). "
            f"Errors: {'; '.join(errors[:3])}"
        )

    return validated