"""
VYAS v0.11 — AI Mock Generator Service
=======================================
v0.11 changes (413 / TPM fix):

  ROOT CAUSE:
    Groq counts (input_tokens + max_tokens_param) against the TPM limit —
    NOT just generated output. The code was sending max_tokens=16384 for every
    batch regardless of size. Input prompt ≈ 262 tokens, so Groq saw:
      262 + 16384 = 16646 requested tokens > 8000 TPM limit → HTTP 413.

    Even though batch_size was already 5, all three retries sent the same
    16384 cap, so every attempt failed identically.

  FIX 1 — Dynamic max_tokens per batch (PRIMARY FIX):
    max_tokens is now computed per batch:
      dynamic_max = min(
          batch_count × AI_TOKENS_PER_QUESTION × AI_OUTPUT_TOKEN_OVERHEAD,
          AI_MAX_TOKENS_MOCK,          ← hard safety cap
      )
    For the default config (3 questions, 600 TPQ, 1.20 overhead):
      dynamic_max = 3 × 600 × 1.20 = 2160
      total_groq_sees = 350 (input) + 2160 = 2510 < 8000 ✓

  FIX 2 — AI_MOCK_BATCH_SIZE lowered from 5 → 3:
    With dynamic max_tokens, batch_size=5 would send 3950 tokens per batch
    (still within 8K), but 3 leaves more headroom for prompt growth and
    is safer when the user's subjects have verbose questions.

  FIX 3 — AI_BATCH_DELAY raised from 2.0 → 22.0 s:
    Minimum safe delay at 8K TPM = (2510/8000)×60 = 18.8 s.
    22 s adds a 17% buffer. The delay is also logged clearly.

  FIX 4 — AI_RATE_LIMIT_BACKOFF raised from 15 → 30 s:
    If a 429 still occurs (e.g., concurrent users), the backoff must clear
    at least one full TPM window (60 s). 30 × attempt scales to 60 s on
    attempt 2, which covers the window.

  FIX 5 — Pre-flight budget check uses total_tokens (input + output):
    _check_token_budget now includes AI_PROMPT_TOKEN_ESTIMATE so the warning
    reflects what Groq will actually count, not just the output side.

  Preserved from v0.10:
    - All validation logic (validate_ai_question unchanged)
    - Difficulty distribution logic (counts_from_distribution unchanged)
    - Retry behaviour pattern, async architecture, logging format
    - Response schema, router interface
    - GeminiTruncationError / GeminiParseError propagation
    - HTTP 429 dedicated backoff path
    - 400/401/403 hard-error fast-fail (no retry)
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
    """
    result = {}
    for diff, total in full_counts.items():
        base = total // n_batches
        remainder = total % n_batches
        extra = remainder if batch_idx == n_batches - 1 else 0
        result[diff] = base + extra
    return result


# ── Dynamic max_tokens calculation (v0.11 PRIMARY FIX) ───────────────────────

def _compute_dynamic_max_tokens(batch_count: int) -> int:
    """
    Compute the max_tokens value to send in the Groq API request for this batch.

    Groq counts (input_tokens + max_tokens_param) against the TPM limit.
    Sending a large fixed cap (e.g. 16384) exceeds the 8000 TPM ceiling even
    for small batches, causing HTTP 413.

    This function returns the minimum sufficient cap:
      dynamic = batch_count × AI_TOKENS_PER_QUESTION × AI_OUTPUT_TOKEN_OVERHEAD

    It is also clamped to AI_MAX_TOKENS_MOCK as an absolute upper bound.

    Example with defaults (batch_count=3, TPQ=600, overhead=1.20, cap=7500):
      dynamic  = 3 × 600 × 1.20 = 2160
      total_groq_sees = 350 (prompt) + 2160 = 2510  <  8000 TPM ✓
    """
    tpq      = AppConfig.AI_TOKENS_PER_QUESTION
    overhead = AppConfig.AI_OUTPUT_TOKEN_OVERHEAD
    cap      = AppConfig.AI_MAX_TOKENS_MOCK

    dynamic = int(batch_count * tpq * overhead)
    return min(dynamic, cap)


# ── Pre-flight token budget check ─────────────────────────────────────────────

def _check_token_budget(batch_count: int, dynamic_max_tokens: int) -> None:
    """
    Log a warning if the total tokens Groq will count for this batch approaches
    the TPM ceiling. Includes both prompt (input) and max_tokens (output cap).

    v0.11: now checks total_tokens = prompt_estimate + dynamic_max_tokens,
    matching what Groq actually counts. Previous version only checked the
    output side, missing the issue entirely.
    """
    prompt_est   = AppConfig.AI_PROMPT_TOKEN_ESTIMATE
    tpm_limit    = AppConfig.GROQ_TPM_LIMIT
    safety       = AppConfig.AI_TOKEN_SAFETY_MARGIN

    total_tokens = prompt_est + dynamic_max_tokens
    safe_budget  = int(tpm_limit * safety)

    if total_tokens > safe_budget:
        logger.warning(
            "Token budget WARNING: batch_count=%d dynamic_max_tokens=%d "
            "prompt_est=%d total=%d safe_budget=%d (tpm=%d × %.2f). "
            "Reduce AI_MOCK_BATCH_SIZE or AI_OUTPUT_TOKEN_OVERHEAD.",
            batch_count, dynamic_max_tokens, prompt_est,
            total_tokens, safe_budget, tpm_limit, safety,
        )
    else:
        logger.debug(
            "Token budget OK: batch_count=%d dynamic_max_tokens=%d "
            "total=%d safe_budget=%d",
            batch_count, dynamic_max_tokens, total_tokens, safe_budget,
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


# ── Compact prompt builder ────────────────────────────────────────────────────

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

    system_prompt = f"""You are an expert MCQ setter for {exam} ({subject}).
Generate exactly {count} original questions. {diff_instruction}
Rules: 4 options (A-D); correct must be A/B/C/D and actually correct; plausible distractors; no answer hints in question text; explanation 2-4 sentences (why correct answer is right); topic = sub-topic within {subject}.{topic_hint}

Return ONLY a JSON array — no markdown, no preamble, no trailing text.
Schema per element: {{"id":int,"type":"mcq","question":str,"options":{{"A":str,"B":str,"C":str,"D":str}},"correct":"A|B|C|D","explanation":str,"difficulty":"easy|medium|hard","topic":str,"marks":4,"negative_marking":1}}"""

    user_message = (
        f"Generate {count} {exam} {subject} MCQ questions now. "
        f"Output ONLY the JSON array."
    )

    return system_prompt, user_message


# ── Groq API call (single batch) ──────────────────────────────────────────────

async def call_groq_generate(
    system_prompt: str,
    user_message: str,
    max_tokens: int,                      # v0.11: dynamic per-batch value
) -> list[dict]:
    """
    Call Groq (OpenAI-compatible) to generate a single batch of questions.

    v0.11 changes vs v0.10:
      - max_tokens is now passed in as a parameter (not read from config).
        The caller computes the precise per-batch value so Groq never sees
        an inflated cap that busts the TPM limit.
      - AI_RATE_LIMIT_BACKOFF raised to 30 s (scales to 60 s on attempt 2).

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
    retry_delay = AppConfig.AI_BATCH_DELAY
    rl_backoff  = AppConfig.AI_RATE_LIMIT_BACKOFF

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
        "max_tokens":  max_tokens,          # v0.11: dynamic, not a fixed config value
    }

    logger.debug(
        "Groq request: model=%s max_tokens=%d (prompt+cap ≈ %d tokens)",
        model, max_tokens, AppConfig.AI_PROMPT_TOKEN_ESTIMATE + max_tokens,
    )

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
            last_exc    = exc
            status_code = exc.response.status_code

            # ── 429: rate limit — dedicated long backoff ───────────────────
            if status_code == 429:
                wait = rl_backoff * (attempt + 1)
                logger.warning(
                    "Groq 429 rate-limit (attempt %d/%d). Backing off %.1f s. model=%s",
                    attempt + 1, max_retries, wait, model,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait)
                continue

            logger.error(
                "Groq mock HTTP error (attempt %d/%d): status=%s body=%r model=%s",
                attempt + 1, max_retries,
                status_code,
                exc.response.text[:2000],
                model,
            )
            # Hard errors — no point retrying
            if status_code in (400, 401, 403):
                raise httpx.HTTPStatusError(
                    f"Groq API returned HTTP {status_code}",
                    request=exc.request,
                    response=exc.response,
                ) from exc
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))

        except httpx.TimeoutException:
            timed_out = True
            logger.error(
                "Groq mock timeout (attempt %d/%d) after %.1fs",
                attempt + 1, max_retries, timeout,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
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


# ── Batched generation ────────────────────────────────────────────────────────

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
    # v0.11: compute exact max_tokens for this batch size
    dynamic_max_tokens = _compute_dynamic_max_tokens(batch_count)
    _check_token_budget(batch_count, dynamic_max_tokens)

    system_prompt, user_message = build_generation_prompt(
        exam=exam, subject=subject, difficulty=difficulty,
        count=batch_count, dist=batch_dist, weak_topics=weak_topics,
    )
    logger.info(
        "Groq mock batch %d/%d: exam=%s subject=%s difficulty=%s count=%d "
        "max_tokens=%d model=%s",
        batch_idx + 1, n_batches,
        exam, subject, difficulty, batch_count,
        dynamic_max_tokens,
        AppConfig.GROQ_MODEL,
    )
    return await call_groq_generate(system_prompt, user_message, max_tokens=dynamic_max_tokens)


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

    v0.11: max_tokens is now computed dynamically per batch so Groq's TPM
    counter never sees an inflated value that busts the 8K ceiling.
    AI_BATCH_DELAY raised to 22 s to respect TPM pacing between batches.

    The outer log line preserves the existing format used by log parsers:
      "Generating AI mock: exam=... subject=... difficulty=... count=... model=..."
    """
    count       = min(count, 20)
    weak_topics = weak_topics or []
    batch_size  = AppConfig.AI_MOCK_BATCH_SIZE
    batch_delay = AppConfig.AI_BATCH_DELAY

    dist        = get_difficulty_distribution(proficiency_score)
    full_counts = counts_from_distribution(count, dist)
    n_batches   = math.ceil(count / batch_size)

    # Log projected token usage for observability
    dyn_ex   = _compute_dynamic_max_tokens(batch_size)
    total_ex = AppConfig.AI_PROMPT_TOKEN_ESTIMATE + dyn_ex
    logger.info(
        "Generating AI mock: exam=%s subject=%s difficulty=%s count=%d model=%s%s "
        "(per-batch tokens ≈ %d, delay=%.0fs)",
        exam, subject, difficulty, count, AppConfig.GROQ_MODEL,
        f" (batches={n_batches}×{batch_size})" if n_batches > 1 else "",
        total_ex, batch_delay,
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

        # TPM-paced inter-batch delay
        if batch_idx < n_batches - 1:
            logger.info(
                "Inter-batch delay %.1f s — respecting 8K TPM limit "
                "(batch %d/%d complete, %d questions so far)",
                batch_delay, batch_idx + 1, n_batches, len(all_raw),
            )
            await asyncio.sleep(batch_delay)

    # Validate and re-index all questions sequentially
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
