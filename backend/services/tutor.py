"""
VYAS v2.1.2 — Tutor Service
==============================
v2.1.2 bugfix (on top of v2.1.1):

  BUG-DOUBLE-COMMIT (CRITICAL — 500 on pgBouncer / Supabase pooler):
    get_or_create_explanation() called db.commit() + db.refresh() internally,
    BEFORE the router's credit deduction. This created two problems:

    Problem A — Transaction boundary violation:
      The service layer committed the TutorInteraction in one transaction,
      then the router ran deduct_credits() + db.commit() in a second
      transaction. On pgBouncer transaction pooling (pooler.supabase.com:5432),
      each db.commit() releases the backend PostgreSQL connection back to the
      pool. The wallet service's SELECT FOR UPDATE NOWAIT then ran on a
      *new* connection that did not hold the same transaction — pgBouncer
      returned OperationalError ("cannot use NOWAIT"), which was caught and
      re-raised as WalletLockError → HTTP 429, silently consumed.

    Problem B — Stale identity-map access on cache hits:
      After db.commit(), SQLAlchemy expires all ORM objects. If any lazy-
      loaded attribute (e.g., cached.explanation_json accessed from a
      TutorCache row fetched before the commit) was accessed AFTER the
      commit, SQLAlchemy would fire a SELECT on the expired session. On
      pgBouncer transaction pooling, this SELECT may run outside a proper
      transaction and raise InterfaceError or InvalidTransactionState,
      which bubbled up as an unlogged 500.

    Fix: Replace db.commit() + db.refresh() with db.flush() only.
      The flush makes interaction.id available (via autoincrement) within
      the same transaction, without ending the transaction or releasing the
      connection. The caller (router) does ONE db.commit() at the very end,
      atomically committing TutorInteraction + TutorCache + CreditLedger
      in a single transaction.

  BUG-CACHE-KEY-MISMATCH (billing):
    The check_only=True pre-flight call in the router used the default
    proficiency_bucket="Beginner", while the actual generation call used
    the real bucket. For users with bucket != "Beginner", the cache key
    was different between the two calls, causing a false cache miss on the
    pre-flight check → credits charged even when a valid cache entry existed
    for the user's actual bucket.
    Fix: Router now computes proficiency_bucket BEFORE calling check_only=True
    and passes it to both calls. (See routers/tutor.py fix.)

Preserved from v2.1.1:
  - BUG-FORCE-REFRESH: force_refresh parameter
  - All BUG-1 through BUG-5 fixes
  - ExplanationResult dataclass
  - get_proficiency_bucket(), make_cache_key(), build_tutor_prompt()
  - call_groq() with retry + exponential back-off
  - build_behavioral_note() with optional question_data
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Union

import httpx
from sqlalchemy.orm import Session

import models
from core.config import get_settings
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


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ExplanationResult:
    """
    Returned by get_or_create_explanation().
    explanation_text  — dict matching TutorExplanation schema fields.
    interaction_id    — TutorInteraction PK (0 for check_only=True results).
    was_cache_hit     — True if explanation came from TutorCache.
    """
    explanation_text: dict
    interaction_id: int
    was_cache_hit: bool


# ── Proficiency helpers ───────────────────────────────────────────────────────

def get_proficiency_bucket(proficiency_rows: Union[List, float, int]) -> str:
    """
    Accept either a list of UserProficiency ORM rows (new usage from
    routers/tutor.py v2.0) or a raw float score (legacy call-sites).

    Score thresholds:
      Expert       >= 800
      Advanced     >= 600
      Intermediate >= 300
      Beginner     <  300
    """
    if isinstance(proficiency_rows, (int, float)):
        score = float(proficiency_rows)
    elif proficiency_rows:
        score = sum(r.proficiency for r in proficiency_rows) / len(proficiency_rows)
    else:
        score = 400.0  # no data → Intermediate default

    if score >= 800:
        return "Expert"
    if score >= 600:
        return "Advanced"
    if score >= 300:
        return "Intermediate"
    return "Beginner"


def make_cache_key(
    question_id: str,
    proficiency_bucket: str,
    user_answer: Optional[str],
    correct_answer: str,
) -> str:
    raw = f"{question_id}:{proficiency_bucket}:{user_answer or 'SKIPPED'}:{correct_answer}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_tutor_prompt(
    question_data: dict,
    user_answer: Optional[str],
    proficiency_level: str,
    time_efficiency: Optional[float],
    was_marked: bool,
    answer_changes: int,
) -> tuple[str, str]:
    actual_time = question_data.get("_actual_time_seconds", 0)
    estimated   = question_data.get("estimated_time_sec", 0)
    subject     = question_data.get("_subject", "") or question_data.get("subject", "")
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


# ── Groq API call ─────────────────────────────────────────────────────────────

async def call_groq(system_prompt: str, user_message: str) -> dict:
    """
    Call Groq API (OpenAI-compatible) for tutor explanations.
    API key is NEVER included in raised exceptions or log messages.
    """
    settings = get_settings()

    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured.")

    model = settings.GROQ_MODEL
    if not model:
        raise ValueError("GROQ_MODEL is not configured.")

    base_url    = settings.GROQ_BASE_URL.rstrip("/")
    url         = f"{base_url}/chat/completions"
    timeout     = settings.AI_TIMEOUT
    max_retries = settings.AI_MAX_RETRIES
    temperature = settings.AI_TEMPERATURE_TUTOR
    max_tokens  = settings.AI_MAX_TOKENS_TUTOR

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
            break
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            logger.error(
                "Groq tutor HTTP error (attempt %d/%d): status=%s body=%r model=%s",
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
        except (httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
            timed_out = True
            logger.error(
                "Groq tutor timeout/transport error (attempt %d/%d): %s",
                attempt + 1, max_retries, exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(_RETRY_DELAY)
        except BaseException as exc:
            import asyncio as _asyncio
            if isinstance(exc, _asyncio.CancelledError):
                raise httpx.TimeoutException(
                    "Groq tutor request was cancelled (asyncio timeout/disconnect)"
                ) from exc
            raise
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


# ── Core tutor service function ───────────────────────────────────────────────

async def get_or_create_explanation(
    db: Session,
    user_id: int,
    question_id: str,
    attempt_id: int,
    question_data: dict,
    check_only: bool = False,
    force_refresh: bool = False,
    proficiency_bucket: str = "Beginner",
    behavioral_note: Optional[str] = None,
) -> Optional[ExplanationResult]:
    """
    Get a cached explanation or generate a new one via Groq.

    v2.1.2 FIX — BUG-DOUBLE-COMMIT:
      This function NO LONGER calls db.commit(). It uses db.flush() only.
      The caller (routers/tutor.py) owns the single transaction boundary
      and calls db.commit() exactly once, after both this function AND
      credit deduction have completed successfully. This ensures:
        - TutorInteraction, TutorCache, and CreditLedger entries are all
          committed atomically in one transaction.
        - No mid-request commit releases the pgBouncer connection between
          the tutor service call and the wallet lock acquisition.
        - No stale ORM object access after a premature commit.

    Parameters
    ----------
    db                  SQLAlchemy session
    user_id             Authenticated user's PK
    question_id         Question ID as string (supports both int and AI mock IDs)
    attempt_id          Attempt PK
    question_data       Full question dict from JSON bank or ai_mock_questions
    check_only          If True: return cached ExplanationResult or None without
                        calling Groq or writing a TutorInteraction. Used by the
                        router to decide whether to charge credits.
    force_refresh       If True: bypass cache entirely and always call Groq.
                        check_only=True + force_refresh=True returns None always
                        (treats as uncached so the router does a credit pre-flight).
    proficiency_bucket  Bucket string from get_proficiency_bucket().
                        IMPORTANT: the router must compute this BEFORE calling
                        check_only=True so both calls use the same cache key.
    behavioral_note     Optional behavioural coaching note (unused internally,
                        kept for API symmetry with v2.1.1).

    Returns
    -------
    ExplanationResult if an explanation exists/was generated, else None (only
    possible when check_only=True, with or without force_refresh=True).
    """
    # ── Resolve response_row to get user_answer for cache key ────────────────
    try:
        _qid_int = int(question_id)
    except (ValueError, TypeError):
        _qid_int = None

    if _qid_int is not None:
        response_row = (
            db.query(models.Response)
            .filter(
                models.Response.attempt_id == attempt_id,
                models.Response.question_id == _qid_int,
            )
            .first()
        )
    else:
        response_row = None

    user_answer    = response_row.selected_option if response_row else None
    correct_answer = question_data.get("correct", "")
    cache_key      = make_cache_key(
        question_id=question_id,
        proficiency_bucket=proficiency_bucket,
        user_answer=user_answer,
        correct_answer=correct_answer,
    )
    now = datetime.now(timezone.utc)

    # ── Cache lookup ──────────────────────────────────────────────────────────
    cached = None
    if not force_refresh:
        cached = (
            db.query(models.TutorCache)
            .filter_by(cache_key=cache_key)
            .filter(models.TutorCache.expires_at > now)
            .first()
        )

    # check_only mode: probe cache only, never call AI or write DB records.
    if check_only:
        if cached:
            logger.debug("Tutor cache CHECK-HIT key=%s", cache_key[:16])
            return ExplanationResult(
                explanation_text=cached.explanation_json,
                interaction_id=0,
                was_cache_hit=True,
            )
        return None  # cache miss (or force_refresh=True) — router will charge credits

    # ── Full mode: get from cache or generate via Groq ────────────────────────
    was_cache_hit = False

    if cached:
        cached.hit_count += 1
        # v2.1.2 FIX: Read explanation_json NOW (while ORM object is live)
        # and store in a local variable. Do NOT access cached.explanation_json
        # after any db.flush() or db.commit() — SQLAlchemy expires ORM objects
        # on commit, and a lazy-reload through pgBouncer may raise
        # InterfaceError or InvalidTransactionState.
        explanation_json = cached.explanation_json
        was_cache_hit    = True
        logger.debug("Tutor cache HIT key=%s", cache_key[:16])
    else:
        if response_row is None:
            raise ValueError(
                f"Response row not found for attempt_id={attempt_id}, "
                f"question_id={question_id}. Cannot generate explanation."
            )

        system_prompt, user_message = build_tutor_prompt(
            question_data=question_data,
            user_answer=user_answer,
            proficiency_level=proficiency_bucket,
            time_efficiency=getattr(response_row, "time_efficiency_ratio", None),
            was_marked=bool(response_row.was_marked_for_review),
            answer_changes=response_row.answer_changed_count or 0,
        )

        logger.info(
            "Calling Groq tutor for question_id=%s bucket=%s user_id=%s force_refresh=%s",
            question_id, proficiency_bucket, user_id, force_refresh,
        )
        explanation_json = await call_groq(system_prompt, user_message)

        if not isinstance(explanation_json, dict):
            raise GeminiParseError("Groq tutor returned a non-dict JSON object.")

        for field in ("opening", "core_concept", "why_correct", "memory_anchor"):
            if not explanation_json.get(field):
                explanation_json[field] = "Explanation not available for this field."
        explanation_json.setdefault("why_wrong", None)
        explanation_json.setdefault("follow_up", None)

        # Persist to TutorCache
        expires = now + timedelta(days=CACHE_TTL_DAYS)
        cache_question_id = _qid_int if _qid_int is not None else 0

        existing_cache = (
            db.query(models.TutorCache).filter_by(cache_key=cache_key).first()
        )
        if existing_cache:
            existing_cache.explanation_json   = explanation_json
            existing_cache.expires_at         = expires
            existing_cache.hit_count          = 0
            existing_cache.proficiency_bucket = proficiency_bucket
        else:
            db.add(models.TutorCache(
                cache_key          = cache_key,
                question_id        = cache_question_id,
                exam               = question_data.get("_exam") or question_data.get("exam"),
                proficiency_bucket = proficiency_bucket,
                user_answer        = user_answer,
                correct_answer     = correct_answer,
                explanation_json   = explanation_json,
                expires_at         = expires,
                hit_count          = 0,
            ))

    # ── Stage TutorInteraction (NO COMMIT — caller commits) ──────────────────
    # v2.1.2 FIX: Changed db.commit() + db.refresh() → db.flush() only.
    #
    # WHY THIS MATTERS ON pgBouncer TRANSACTION POOLING:
    #   db.commit() here would end the current transaction and release the
    #   backend PostgreSQL connection back to the pool. The subsequent
    #   SELECT FOR UPDATE NOWAIT in wallet_service.deduct_credits() would
    #   then run on a *new* connection that pgBouncer assigns — which is
    #   incompatible with NOWAIT semantics and raises OperationalError.
    #
    # WHY db.flush() IS SUFFICIENT:
    #   db.flush() sends the INSERT to PostgreSQL within the current open
    #   transaction, making interaction.id available via autoincrement,
    #   without ending the transaction or releasing the connection.
    #   The caller (router) does ONE db.commit() that covers all of:
    #     TutorInteraction + TutorCache + CreditLedger.
    interaction = models.TutorInteraction(
        user_id      = user_id,
        attempt_id   = attempt_id,
        question_id  = _qid_int if _qid_int is not None else 0,
        was_cache_hit= was_cache_hit,
    )
    db.add(interaction)
    db.flush()  # ← v2.1.2: was db.commit() + db.refresh() — DO NOT revert

    logger.info(
        "Tutor interaction staged: id=%s user_id=%s question_id=%s cache_hit=%s",
        interaction.id, user_id, question_id, was_cache_hit,
    )

    return ExplanationResult(
        explanation_text=explanation_json,
        interaction_id=interaction.id,
        was_cache_hit=was_cache_hit,
    )


# ── Behavioral note builder ───────────────────────────────────────────────────

def build_behavioral_note(
    response_row: models.Response,
    question_data: Optional[dict] = None,
) -> Optional[str]:
    """
    When question_data is not provided (new router call-site), the estimated
    time is read from response_row.estimated_time_sec which is stored on the
    Response model at submit time.
    """
    notes = []

    if question_data is not None:
        estimated = question_data.get("estimated_time_sec") or 0
    else:
        estimated = getattr(response_row, "estimated_time_sec", None) or 0

    actual = response_row.time_spent_seconds or 0

    if estimated > 0 and actual < 0.5 * estimated:
        notes.append(
            f"You spent {actual}s (estimated: {estimated}s) — "
            "you may have rushed this one."
        )
    if response_row.was_marked_for_review:
        notes.append("You marked this for review, indicating you had doubts.")
    if (response_row.answer_changed_count or 0) >= 2:
        notes.append(
            f"You changed your answer {response_row.answer_changed_count}\u00d7 — "
            "trust your first instinct more often."
        )

    return " ".join(notes) if notes else None