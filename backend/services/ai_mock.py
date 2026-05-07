"""
VYAS v0.9 — AI Mock Generator Service
======================================
v0.9 changes (truncation fix):
  ROOT CAUSE: Generating 20 JEE Math/Physics questions in one API call produces
  ~12,000-16,000 output tokens. With AI_MAX_TOKENS_MOCK previously set to 8192,
  the model hit finish_reason=length and raised GeminiTruncationError → HTTP 422.

  FIX 1 — Request batching (primary fix):
    generate_questions() now splits any request larger than AI_MOCK_BATCH_SIZE
    (default: 10) into sequential batches. Each batch calls the Groq API
    independently then results are merged and re-indexed. This guarantees no
    single call ever exceeds the safe token budget regardless of subject.

  FIX 2 — Higher token ceiling (defence-in-depth):
    AI_MAX_TOKENS_MOCK default raised from 8192 → 16384 so even a slightly
    over-sized single batch never truncates on edge-case subjects.

  FIX 3 — Difficulty distribution preserved across batches:
    counts_from_distribution() is sliced fairly across batches so the
    overall easy/medium/hard ratio matches the proficiency-based target.

  Preserved from v0.8:
    - All prompts (system_prompt + user_message structure unchanged)
    - Question validation logic (validate_ai_question)
    - Difficulty distribution logic (get_difficulty_distribution)
    - Groq API call mechanics (call_groq_generate unchanged)
    - Retry behaviour, async architecture, error handling pattern
    - Logging format
    - Response schema
"""

import asyncio
import logging
import math
from typing import Optional

import httpx

from config import AppConfig
from services.gemini_utils import (
    _safe_json_extract,
    extract_raw_text_groq,
    check_finish_reason_groq,
    GeminiParseError,
    GeminiTruncationError,
)

logger = logging.getLogger(__name__)

_RETRY_DELAY = 2.0  # seconds between retry attempts


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
    """
    Distribute easy/medium/hard counts fairly across batches.

    Each batch gets floor(count/n_batches). The last batch absorbs any remainder
    so the total always sums to the original request count.

    Example:
        full_counts = {easy:4, medium:11, hard:5}, batch_size=10, n_batches=2
        batch 0 → {easy:2, medium:5, hard:2}   (floor of half)
        batch 1 → {easy:2, medium:6, hard:3}   (remainder goes to last batch)
    """
    result = {}
    for diff, total in full_counts.items():
        base = total // n_batches
        remainder = total % n_batches
        # Give one extra to the *last* batch so totals always add up
        extra = remainder if batch_idx == n_batches - 1 else 0
        result[diff] = base + extra
    return result


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
    raw["id"] = index + 1   # Always overwrite to ensure sequential IDs

    return raw


# ── Prompt builder (unchanged from v0.7/v0.8) ─────────────────────────────────

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


# ── Groq API call (single batch) ──────────────────────────────────────────────

async def call_groq_generate(system_prompt: str, user_message: str) -> list[dict]:
    """
    Call Groq (OpenAI-compatible) to generate a single batch of questions.

    This function handles one API call with retry logic. It is intentionally
    kept as a pure single-call function — batching is handled by the caller
    (generate_questions_batch / generate_questions).

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
    temperature = AppConfig.AI_TEMPERATURE_MOCK
    max_tokens  = AppConfig.AI_MAX_TOKENS_MOCK

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }

    payload = {
        "model":       model,
        "messages":    [
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
            break
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            logger.error(
                "Groq mock HTTP error (attempt %d/%d): status=%s body=%r model=%s",
                attempt + 1, max_retries,
                exc.response.status_code,
                exc.response.text[:2000],
                model,
            )
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
                "Groq mock timeout (attempt %d/%d) after %.1fs",
                attempt + 1, max_retries, timeout,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(_RETRY_DELAY)
    else:
        if timed_out:
            raise httpx.TimeoutException(
                f"Groq mock timed out after {max_retries} attempts."
            )
        if last_exc is not None:
            raise httpx.HTTPStatusError(
                f"Groq API returned HTTP {last_exc.response.status_code}",
                request=last_exc.request,
                response=last_exc.response,
            ) from last_exc

    data     = response.json()
    check_finish_reason_groq(data)
    raw_text = extract_raw_text_groq(data)
    parsed   = _safe_json_extract(raw_text)

    if not isinstance(parsed, list):
        raise GeminiParseError(f"Expected a JSON array, got {type(parsed).__name__}")

    return parsed


# ── Batched generation (v0.9 fix) ─────────────────────────────────────────────

async def _generate_one_batch(
    exam: str,
    subject: str,
    difficulty: str,
    batch_count: int,
    batch_dist: dict,
    weak_topics: list[str],
    batch_idx: int,
    n_batches: int,
) -> list[dict]:
    """Generate a single batch of questions and return the raw (unindexed) list."""
    system_prompt, user_message = build_generation_prompt(
        exam=exam, subject=subject, difficulty=difficulty,
        count=batch_count, dist=batch_dist, weak_topics=weak_topics,
    )
    logger.info(
        "Groq mock batch %d/%d: exam=%s subject=%s difficulty=%s count=%d model=%s",
        batch_idx + 1, n_batches,
        exam, subject, difficulty, batch_count,
        AppConfig.GROQ_MODEL,
    )
    return await call_groq_generate(system_prompt, user_message)


# ── Main generation entry point ────────────────────────────────────────────────

async def generate_questions(
    exam: str,
    subject: str,
    difficulty: str,
    count: int,
    proficiency_score: float = 400.0,
    weak_topics: Optional[list[str]] = None,
) -> list[dict]:
    """
    Generate AI mock questions, automatically batching large requests.

    For count <= AI_MOCK_BATCH_SIZE (default: 10): one API call.
    For count  > AI_MOCK_BATCH_SIZE: sequential batches, merged and re-indexed.

    The outer log line preserves the existing format used by the router/log parser:
      "Generating AI mock: exam=... subject=... difficulty=... count=... model=..."
    """
    count       = min(count, 20)
    weak_topics = weak_topics or []
    batch_size  = AppConfig.AI_MOCK_BATCH_SIZE

    dist         = get_difficulty_distribution(proficiency_score)
    full_counts  = counts_from_distribution(count, dist)
    n_batches    = math.ceil(count / batch_size)

    # Preserve the top-level log line (log parsers / monitoring expects this format)
    logger.info(
        "Generating AI mock: exam=%s subject=%s difficulty=%s count=%d model=%s%s",
        exam, subject, difficulty, count, AppConfig.GROQ_MODEL,
        f" (batches={n_batches}×{batch_size})" if n_batches > 1 else "",
    )

    all_raw: list[dict] = []

    for batch_idx in range(n_batches):
        batch_start = batch_idx * batch_size
        batch_end   = min(batch_start + batch_size, count)
        batch_count = batch_end - batch_start

        batch_dist = _slice_counts(full_counts, batch_size, batch_idx, n_batches)

        batch_raw = await _generate_one_batch(
            exam=exam, subject=subject, difficulty=difficulty,
            batch_count=batch_count, batch_dist=batch_dist,
            weak_topics=weak_topics,
            batch_idx=batch_idx, n_batches=n_batches,
        )
        all_raw.extend(batch_raw[:batch_count])

        # Small inter-batch delay to be a good API citizen (only when batching)
        if batch_idx < n_batches - 1:
            await asyncio.sleep(0.5)

    # Validate and re-index all questions sequentially across the merged result
    validated: list[dict] = []
    errors:    list[str]  = []

    for i, raw in enumerate(all_raw[:count]):
        try:
            validated.append(validate_ai_question(raw, i))
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        logger.warning(
            "AI mock validation errors (%d/%d): %s",
            len(errors), len(all_raw),
            "; ".join(errors[:5]),
        )

    if len(validated) < max(1, count // 2):
        raise ValueError(
            f"Too few valid questions generated ({len(validated)}/{count}). "
            f"Errors: {'; '.join(errors[:3])}"
        )

    return validated
