"""
VYAS v2.0 — AI Mock Generation Service
=========================================
UNCHANGED core logic from v0.11 with one addition:
  - `progress_callback` parameter to report batch progress to Celery task
  - asyncio.sleep() is now truly non-blocking (runs inside Celery's event loop)

The heavy lifting (Groq API calls, batch delays) runs inside the Celery worker,
not inside FastAPI request handlers. This resolves the critical P0 blocking issue.

v0.11 TPM fixes are preserved:
  - Dynamic max_tokens per batch
  - AI_BATCH_DELAY = 22s (TPM pacing)
  - Pre-flight token budget check
"""

import asyncio
import logging
import math
from typing import Callable, Optional

import httpx

from core.config import get_settings
from services.gemini_utils import (
    GeminiParseError,
    GeminiTruncationError,
    _safe_json_extract,
    check_finish_reason_groq,
    extract_raw_text_groq,
)

logger = logging.getLogger(__name__)
settings = get_settings()


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


def _slice_counts(full_counts: dict, batch_size: int, batch_idx: int, n_batches: int) -> dict:
    result = {}
    for diff, total in full_counts.items():
        base = total // n_batches
        remainder = total % n_batches
        extra = remainder if batch_idx == n_batches - 1 else 0
        result[diff] = base + extra
    return result


def _compute_dynamic_max_tokens(batch_count: int) -> int:
    tpq      = settings.AI_TOKENS_PER_QUESTION
    overhead = settings.AI_OUTPUT_TOKEN_OVERHEAD
    cap      = settings.AI_MAX_TOKENS_MOCK
    dynamic  = int(batch_count * tpq * overhead)
    return min(dynamic, cap)


def _check_token_budget(batch_count: int, dynamic_max_tokens: int) -> None:
    prompt_est   = settings.AI_PROMPT_TOKEN_ESTIMATE
    tpm_limit    = settings.GROQ_TPM_LIMIT
    safety       = settings.AI_TOKEN_SAFETY_MARGIN
    total_tokens = prompt_est + dynamic_max_tokens
    safe_budget  = int(tpm_limit * safety)
    if total_tokens > safe_budget:
        logger.warning(
            "Token budget WARNING: batch_count=%d total=%d safe_budget=%d",
            batch_count, total_tokens, safe_budget,
        )


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
        raise ValueError(f"Question {index + 1}: correct='{raw['correct']}' not in options keys")
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


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_generation_prompt(
    exam: str, subject: str, difficulty: str, count: int,
    dist: dict, weak_topics: list[str],
) -> tuple[str, str]:
    topic_hint = ""
    if weak_topics:
        top3 = ", ".join(weak_topics[:3])
        topic_hint = f"\nWEAK TOPICS (weight heavily): {top3}"

    if difficulty == "auto":
        diff_instruction = (
            f"Mix: {dist['easy']} easy, {dist['medium']} medium, {dist['hard']} hard."
        )
    else:
        diff_instruction = f"All {count} questions: {difficulty} difficulty."

    system_prompt = (
        f"You are an expert MCQ setter for {exam} ({subject}).\n"
        f"Generate exactly {count} original questions. {diff_instruction}\n"
        f"Rules: 4 options (A-D); correct must be A/B/C/D and actually correct; "
        f"plausible distractors; no answer hints in question text; "
        f"explanation 2-4 sentences (why correct answer is right); "
        f"topic = sub-topic within {subject}.{topic_hint}\n\n"
        f"Return ONLY a JSON array — no markdown, no preamble, no trailing text.\n"
        f"Schema per element: "
        f'{{\"id\":int,\"type\":\"mcq\",\"question\":str,\"options\":{{\"A\":str,\"B\":str,\"C\":str,\"D\":str}},'
        f'\"correct\":\"A|B|C|D\",\"explanation\":str,\"difficulty\":\"easy|medium|hard\",'
        f'\"topic\":str,\"marks\":4,\"negative_marking\":1}}'
    )
    user_message = f"Generate {count} {exam} {subject} MCQ questions now. Output ONLY the JSON array."
    return system_prompt, user_message


# ── Groq API call ─────────────────────────────────────────────────────────────

async def call_groq_generate(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
) -> list[dict]:
    """Single Groq API call. Handles retries with exponential backoff."""
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured.")

    model = settings.GROQ_MODEL
    base_url = settings.GROQ_BASE_URL.rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": settings.AI_TEMPERATURE_MOCK,
        "max_tokens": max_tokens,
    }

    last_exc = None
    for attempt in range(settings.AI_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=settings.AI_TIMEOUT) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            last_exc = None
            break
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status_code = exc.response.status_code
            if status_code == 429:
                wait = settings.AI_RATE_LIMIT_BACKOFF * (attempt + 1)
                logger.warning("Groq 429 (attempt %d). Backing off %.0fs", attempt + 1, wait)
                if attempt < settings.AI_MAX_RETRIES - 1:
                    await asyncio.sleep(wait)
                continue
            logger.error("Groq HTTP error %s (attempt %d)", status_code, attempt + 1)
            if status_code in (400, 401, 403):
                raise
            if attempt < settings.AI_MAX_RETRIES - 1:
                await asyncio.sleep(settings.AI_BATCH_DELAY * (attempt + 1))
        except httpx.TimeoutException:
            last_exc = httpx.TimeoutException("Groq timed out")
            logger.error("Groq timeout (attempt %d)", attempt + 1)
            if attempt < settings.AI_MAX_RETRIES - 1:
                await asyncio.sleep(settings.AI_BATCH_DELAY)
    else:
        if last_exc:
            raise last_exc

    data = response.json()
    check_finish_reason_groq(data)
    raw_text = extract_raw_text_groq(data)
    parsed = _safe_json_extract(raw_text)
    if not isinstance(parsed, list):
        raise GeminiParseError(f"Expected JSON array, got {type(parsed).__name__}")
    return parsed


# ── Main generation entry point ────────────────────────────────────────────────

async def generate_questions(
    exam: str,
    subject: str,
    difficulty: str,
    count: int,
    proficiency_score: float = 400.0,
    weak_topics: Optional[list[str]] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> list[dict]:
    """
    Generate AI mock questions in batches.

    v2.0: Added progress_callback parameter.
    This function now runs inside Celery workers (not in FastAPI request handlers),
    so asyncio.sleep() is genuinely non-blocking within the worker's event loop.

    Args:
        progress_callback: optional function(questions_generated: int) called after
                          each batch to update job progress in DB/Redis.
    """
    count       = min(count, 20)
    weak_topics = weak_topics or []
    batch_size  = settings.AI_MOCK_BATCH_SIZE
    batch_delay = settings.AI_BATCH_DELAY

    dist        = get_difficulty_distribution(proficiency_score)
    full_counts = counts_from_distribution(count, dist)
    n_batches   = math.ceil(count / batch_size)

    logger.info(
        "Generating AI mock: exam=%s subject=%s difficulty=%s count=%d "
        "model=%s batches=%d×%d delay=%.0fs",
        exam, subject, difficulty, count, settings.GROQ_MODEL,
        n_batches, batch_size, batch_delay,
    )

    all_raw: list[dict] = []

    for batch_idx in range(n_batches):
        batch_start = batch_idx * batch_size
        batch_end   = min(batch_start + batch_size, count)
        batch_count = batch_end - batch_start
        batch_dist  = _slice_counts(full_counts, batch_size, batch_idx, n_batches)

        dynamic_max_tokens = _compute_dynamic_max_tokens(batch_count)
        _check_token_budget(batch_count, dynamic_max_tokens)

        system_prompt, user_message = build_generation_prompt(
            exam=exam, subject=subject, difficulty=difficulty,
            count=batch_count, dist=batch_dist, weak_topics=weak_topics,
        )

        logger.info(
            "Batch %d/%d: count=%d max_tokens=%d",
            batch_idx + 1, n_batches, batch_count, dynamic_max_tokens,
        )

        batch_raw = await call_groq_generate(system_prompt, user_message, max_tokens=dynamic_max_tokens)
        all_raw.extend(batch_raw[:batch_count])

        # Report progress via callback (updates DB + Redis)
        if progress_callback:
            try:
                progress_callback(len(all_raw))
            except Exception:
                pass  # Progress reporting failure must not abort generation

        if batch_idx < n_batches - 1:
            logger.info(
                "Inter-batch delay %.0fs (batch %d/%d done, %d questions so far)",
                batch_delay, batch_idx + 1, n_batches, len(all_raw),
            )
            await asyncio.sleep(batch_delay)

    # Validate and re-index
    validated: list[dict] = []
    errors: list[str] = []
    for i, raw in enumerate(all_raw[:count]):
        try:
            validated.append(validate_ai_question(raw, i))
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        logger.warning("Validation errors (%d/%d): %s", len(errors), len(all_raw), "; ".join(errors[:5]))

    if len(validated) < max(1, count // 2):
        raise ValueError(
            f"Too few valid questions ({len(validated)}/{count}). Errors: {'; '.join(errors[:3])}"
        )

    return validated
