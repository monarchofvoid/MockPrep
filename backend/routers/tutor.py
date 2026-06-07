"""
VYAS v2.1.2 — Tutor Router
=================================================

v2.1.2 bugfixes (on top of v2.1.1):

  BUG-DOUBLE-COMMIT (CRITICAL — 500 on pgBouncer):
    The service called db.commit() internally before the router called it
    again after credit deduction. On Supabase's pgBouncer transaction pooler
    (pooler.supabase.com:5432) the first commit released the PostgreSQL
    backend connection, causing the wallet lock SELECT FOR UPDATE NOWAIT to
    run on a new connection where the lock was invalid → OperationalError →
    WalletLockError → HTTP 429, or in some cases an unlogged 500.
    Fix: service now uses db.flush() only. This router does ONE db.commit()
    at the very end, covering TutorInteraction + TutorCache + CreditLedger
    atomically. db.rollback() is called on any exception before the final
    commit to keep the session in a clean state.

  BUG-CACHE-KEY-MISMATCH (billing — credits charged on warm cache):
    The check_only=True pre-flight call did not pass proficiency_bucket,
    using the default "Beginner". For users with any other bucket, the cache
    key differed from the key used by the check_only=False generation call.
    Result: check_only=True always returned None (cache miss) → credits
    charged → check_only=False found the cached entry → free delivery.
    Fix: proficiency_bucket is now computed BEFORE the check_only call and
    passed to both invocations.

Preserved from v2.1.1:
  BUG-KEY-MISMATCH:  why_wrong / follow_up field names (not common_mistake / mnemonic)
  BUG-FORCE-REFRESH: force_refresh passed to both get_or_create_explanation calls
  BUG-JSON-STRING:   isinstance check + json.loads() fallback on explanation_text
  BUG-NO-ENTRY-LOG:  logger.info() as first line of _tutor_explain_inner()
  BUG-008:           Credit deduction before AI calls
"""

import json
import logging
import traceback

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from core.auth import get_current_user
from core.config import get_settings
from core.exceptions import InsufficientCreditsError, WalletLockError, WalletNotFoundError
from database import get_db
from models.wallet import LedgerEntryType
from services.gemini_utils import GeminiParseError, GeminiTruncationError
from services.proficiency import get_proficiency_level
from services.question_bank import load_question_json
from services.tutor import (
    build_behavioral_note,
    get_or_create_explanation,
    get_proficiency_bucket,
)
from services.wallet_service import WalletService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/tutor", tags=["Tutor"])


# ── GET /tutor/proficiency ─────────────────────────────────────────────────────

@router.get("/proficiency", response_model=schemas.UserProficiencyResponse)
def get_proficiency(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.UserProficiency)
        .filter_by(user_id=current_user.id)
        .order_by(
            models.UserProficiency.subject,
            models.UserProficiency.topic,
        )
        .all()
    )

    overall_score = round(sum(r.proficiency for r in rows) / len(rows), 2) if rows else 400.0
    overall_level = get_proficiency_level(overall_score)

    topics = [
        schemas.TopicProficiency(
            exam=r.exam,
            subject=r.subject,
            topic=r.topic,
            subtopic=r.subtopic,
            proficiency=round(r.proficiency, 2),
            level=get_proficiency_level(r.proficiency),
            accuracy_rate=r.accuracy_rate,
            total_count=r.total_count,
            correct_count=r.correct_count,
            difficulty_profile=schemas.DifficultyProfile(
                easy=r.difficulty_easy_acc,
                medium=r.difficulty_med_acc,
                hard=r.difficulty_hard_acc,
            ),
            avg_time_efficiency=r.avg_time_efficiency,
            last_updated=r.last_updated,
        )
        for r in rows
    ]

    return schemas.UserProficiencyResponse(
        user_id=current_user.id,
        overall_level=overall_level,
        overall_score=overall_score,
        topic_count=len(rows),
        topics=topics,
    )


# ── POST /tutor/explain ────────────────────────────────────────────────────────

@router.post("/explain", response_model=schemas.TutorExplainResponse)
async def tutor_explain(
    body: schemas.TutorExplainRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    VYAS Explain — AI-powered step-by-step explanation for wrong/skipped answers.

    Credit cost: COST_TUTOR_EXPLAIN_MICROCREDITS (default: 50 = 0.5 credits)
    Idempotency: re-explaining the same question uses the same key, so a
    network retry won't double-charge the user.
    """
    try:
        return await _tutor_explain_inner(body, current_user, db)
    except HTTPException:
        raise
    except BaseException as exc:
        import asyncio
        if isinstance(exc, asyncio.CancelledError):
            raise
        logger.error(
            "UNHANDLED EXCEPTION in POST /tutor/explain user=%s attempt=%s q=%s\n%s",
            current_user.id, body.attempt_id, body.question_id,
            traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"VYAS Explain failed: {type(exc).__name__}: {exc}",
        )


async def _tutor_explain_inner(body, current_user, db):
    """Inner implementation — all logic here so the outer handler catches everything."""

    # Entry log — first line so we can tell handler was reached even if everything below fails
    logger.info(
        "POST /tutor/explain: user_id=%s attempt_id=%s question_id=%s force_refresh=%s",
        current_user.id, body.attempt_id, body.question_id, body.force_refresh,
    )

    # ── Validate attempt ownership ────────────────────────────────────────────
    attempt = db.query(models.Attempt).filter_by(id=body.attempt_id).first()
    if not attempt or attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    # ── Validate question response (psycopg3 type safety) ────────────────────
    try:
        _question_id_int = int(body.question_id)
    except (ValueError, TypeError):
        _question_id_int = None

    if _question_id_int is not None:
        response_row = (
            db.query(models.Response)
            .filter(
                models.Response.attempt_id == body.attempt_id,
                models.Response.question_id == _question_id_int,
            )
            .first()
        )
    else:
        response_row = None

    if not response_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found for this attempt/question combination.",
        )
    if response_row.is_correct:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VYAS Tutor is only available for wrong or skipped answers.",
        )

    mock = attempt.mock_test
    if not mock:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mock test not found for this attempt.",
        )

    # ── Load question data ────────────────────────────────────────────────────
    question_data = None

    if mock.is_ai_generated:
        ai_qs = (
            db.query(models.AIMockQuestion)
            .filter_by(mock_id=mock.id)
            .all()
        )
        for aq in ai_qs:
            if aq.question_data and str(aq.question_data.get("id", "")) == str(body.question_id):
                question_data = dict(aq.question_data)
                break

        if question_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question {body.question_id} not found in AI mock question bank.",
            )
    else:
        if not mock.json_file_path:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Mock test question bank file path not found.",
            )

        try:
            mock_data = load_question_json(mock.json_file_path)
        except HTTPException:
            raise

        question_data = next(
            (q for q in mock_data.get("questions", []) if str(q.get("id", "")) == str(body.question_id)),
            None,
        )
        if not question_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question {body.question_id} not found in question bank.",
            )

    # ── Compute proficiency BEFORE cache check ────────────────────────────────
    # v2.1.2 FIX — BUG-CACHE-KEY-MISMATCH:
    # proficiency_bucket is now computed here, before the check_only=True call,
    # so BOTH calls to get_or_create_explanation use the same cache key.
    # Previously, check_only=True used the default "Beginner", causing a false
    # cache miss for any user with a higher proficiency level.
    proficiency_rows = (
        db.query(models.UserProficiency)
        .filter_by(
            user_id=current_user.id,
            subject=question_data.get("subject"),
        )
        .all()
    )
    proficiency_bucket = get_proficiency_bucket(proficiency_rows)
    behavioral_note = build_behavioral_note(response_row)

    # ── Cache check ───────────────────────────────────────────────────────────
    existing = await get_or_create_explanation(
        db=db,
        user_id=current_user.id,
        question_id=body.question_id,
        attempt_id=body.attempt_id,
        question_data=question_data,
        check_only=True,
        force_refresh=body.force_refresh,
        proficiency_bucket=proficiency_bucket,  # v2.1.2: real bucket, not default "Beginner"
    )

    # ── Pre-flight credit check ───────────────────────────────────────────────
    if existing is None:
        wallet_service = WalletService(db)
        try:
            wallet = wallet_service.get_wallet(current_user.id)
        except WalletNotFoundError:
            raise HTTPException(
                status_code=402,
                detail="Wallet not found. Please contact support.",
            )
        if wallet.balance_microcredits < settings.COST_TUTOR_EXPLAIN_MICROCREDITS:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Insufficient credits. VYAS Explain costs "
                    f"{settings.COST_TUTOR_EXPLAIN_MICROCREDITS / settings.MICROCREDITS_PER_CREDIT:.1f} "
                    f"credits per question. Please top up your wallet."
                ),
            )

    # ── Generate or fetch explanation ─────────────────────────────────────────
    try:
        explanation = await get_or_create_explanation(
            db=db,
            user_id=current_user.id,
            question_id=body.question_id,
            attempt_id=body.attempt_id,
            question_data=question_data,
            check_only=False,
            force_refresh=body.force_refresh,
            proficiency_bucket=proficiency_bucket,
            behavioral_note=behavioral_note,
        )
    except GeminiParseError as exc:
        logger.error("Tutor parse error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to parse AI explanation. Please try again.",
        )
    except GeminiTruncationError as exc:
        logger.error("Tutor truncation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI explanation was truncated. Please try again.",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI service timed out. Please try again.",
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Tutor HTTP error: status=%s", exc.response.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service returned an error. Please try again.",
        )

    proficiency_score = (
        round(sum(r.proficiency for r in proficiency_rows) / len(proficiency_rows), 2)
        if proficiency_rows else 400.0
    )

    # ── Build explanation schema object ───────────────────────────────────────
    # Guard against DB returning JSON column as string (pgBouncer + some psycopg versions)
    raw = explanation.explanation_text

    if isinstance(raw, str):
        logger.warning(
            "explanation_text arrived as string (expected dict) — "
            "DB may have returned JSON column as raw text. Attempting json.loads(). "
            "question_id=%s", body.question_id,
        )
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as parse_exc:
            logger.error(
                "Failed to json.loads() explanation_text: %s | raw=%r",
                parse_exc, raw[:200] if isinstance(raw, str) else raw,
            )
            raise HTTPException(
                status_code=502,
                detail="Cached explanation is corrupt. Please try force-refreshing.",
            )

    if not isinstance(raw, dict):
        logger.error(
            "explanation_text is neither str nor dict: type=%s | val=%r",
            type(raw).__name__, str(raw)[:200],
        )
        raise HTTPException(
            status_code=502,
            detail="AI returned an explanation in an unexpected format. Please try again.",
        )

    try:
        explanation_obj = schemas.TutorExplanation(
            opening       = raw.get("opening")       or "Not available.",
            core_concept  = raw.get("core_concept")  or "Not available.",
            why_correct   = raw.get("why_correct")   or "Not available.",
            memory_anchor = raw.get("memory_anchor") or "Not available.",
            why_wrong     = raw.get("why_wrong"),
            follow_up     = raw.get("follow_up"),
            steps         = raw.get("steps"),
            formula       = raw.get("formula"),
        )
    except Exception as exc:
        logger.error("TutorExplanation schema validation failed: %s | raw=%s", exc, raw)
        raise HTTPException(
            status_code=502,
            detail="AI returned an explanation in an unexpected format. Please try again.",
        )

    # ── Single atomic commit: TutorInteraction + TutorCache + CreditLedger ───
    # v2.1.2 FIX — BUG-DOUBLE-COMMIT:
    # The service (get_or_create_explanation) no longer calls db.commit().
    # We do ONE commit here, covering all DB writes from this request.
    # This keeps everything in a single pgBouncer transaction and makes
    # wallet SELECT FOR UPDATE NOWAIT work correctly.
    if existing is None:
        idempotency_key = f"tutor:{body.attempt_id}:{body.question_id}"
        wallet_service = WalletService(db)
        try:
            wallet_service.deduct_credits(
                user_id=current_user.id,
                amount_microcredits=settings.COST_TUTOR_EXPLAIN_MICROCREDITS,  # BUG FIX: was cost_microcredits (wrong kwarg); correct param is amount_microcredits
                entry_type=LedgerEntryType.TUTOR_DEDUCTION,
                idempotency_key=idempotency_key,
                description=(
                    f"VYAS Explain — question {body.question_id} "
                    f"(attempt {body.attempt_id})"
                ),
            )
            # Single commit: atomically commits TutorInteraction (staged by
            # service with flush), TutorCache, and CreditLedger.
            db.commit()
            logger.info(
                "Tutor deduction committed: user_id=%s question=%s cost=%s microcredits",
                current_user.id, body.question_id,
                settings.COST_TUTOR_EXPLAIN_MICROCREDITS,
            )
        except InsufficientCreditsError:
            db.rollback()
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Insufficient credits. VYAS Explain costs "
                    f"{settings.COST_TUTOR_EXPLAIN_MICROCREDITS / settings.MICROCREDITS_PER_CREDIT:.1f} "
                    f"credits per question. Please top up your wallet."
                ),
            )
        except WalletLockError:
            db.rollback()
            raise HTTPException(status_code=429, detail="Wallet is busy. Please try again.")
        except WalletNotFoundError:
            db.rollback()
            raise HTTPException(status_code=402, detail="Wallet not found. Please contact support.")
        except Exception as exc:
            db.rollback()
            logger.error(
                "Unexpected error during credit deduction: user_id=%s question=%s error=%s\n%s",
                current_user.id, body.question_id, exc, traceback.format_exc(),
            )
            raise HTTPException(
                status_code=500,
                detail="Credit deduction failed unexpectedly. Your explanation was generated — please retry.",
            )
    else:
        # Cache hit path: service still staged a TutorInteraction via flush().
        # Commit it now so the interaction is recorded even on cache hits.
        db.commit()

    return schemas.TutorExplainResponse(
        interaction_id=explanation.interaction_id,
        question_id=body.question_id,
        proficiency_level=proficiency_bucket,
        proficiency_score=proficiency_score,
        was_cache_hit=existing is not None,
        behavioral_note=behavioral_note,
        explanation=explanation_obj,
    )