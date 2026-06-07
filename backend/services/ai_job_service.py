"""
VYAS v2.2.0 — AI Job Service
==============================
v2.2.0 Migration: Celery → asyncio.create_task

Changes from v2.1.5:
  1. enqueue_job(): replaced generate_mock_task.apply_async() with
     asyncio.create_task(_run_ai_generation(job_id=...)).

  2. _run_ai_generation(): new async coroutine that replaces the Celery
     generate_mock_task. Runs natively in FastAPI's event loop.

  3. celery_task_id: still written (set to job.id) for schema compatibility.

  4. mark_job_failed(): uses correct parameter name `original_ledger_entry_id`.

v2.1.5 FIX (preserved): Corrected SQLAlchemy identity_map lookup in get_job_status().
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from core.config import get_settings
from core.exceptions import AIJobAlreadyActiveError, AIJobNotFoundError
from core.redis import (
    cache_job_status,
    clear_user_active_job,
    get_cached_job_status,
    get_user_active_job,
    set_user_active_job,
)
from models.ai_job import AIJob, AIJobStatus
from models.wallet import LedgerEntryType
from services.wallet_service import WalletService

logger = logging.getLogger(__name__)
settings = get_settings()


class AIJobService:
    def __init__(self, db: Session):
        self.db = db
        self._wallet_service = WalletService(db)

    # ── Job Creation (with credit deduction) ──────────────────────────────────

    def create_job_with_deduction(
        self,
        user_id: int,
        exam: str,
        subject: str,
        difficulty: str,
        question_count: int,
        use_proficiency: bool = True,
        proficiency_score: float = 400.0,
        weak_topics: Optional[list] = None,
    ) -> tuple:
        """
        Create an AI job record and atomically deduct credits.

        Returns:
            (AIJob, cost_microcredits)

        Raises:
            AIJobAlreadyActiveError: user has active job in progress
            InsufficientCreditsError: not enough credits
            WalletLockError: concurrent request, retry
        """
        existing_job_id = get_user_active_job(user_id)
        if existing_job_id:
            existing_job = self.db.query(AIJob).filter_by(id=existing_job_id).first()
            if existing_job and not existing_job.is_terminal:
                raise AIJobAlreadyActiveError(existing_job_id)

        # BUG FIX: WalletService.calculate_mock_cost() does not exist.
        # Cost is simply question_count * COST_PER_QUESTION_MICROCREDITS from config.
        cost_microcredits = question_count * settings.COST_PER_QUESTION_MICROCREDITS
        job_id = str(uuid.uuid4())
        idempotency_key = f"ai_mock:{job_id}"

        ledger_entry = self._wallet_service.deduct_credits(
            user_id=user_id,
            amount_microcredits=cost_microcredits,  # BUG FIX: was cost_microcredits (wrong kwarg)
            entry_type=LedgerEntryType.AI_MOCK_DEDUCTION,
            idempotency_key=idempotency_key,
            description=f"{question_count}-question {exam} {subject} Mock",
            ai_job_id=job_id,
        )

        job = AIJob(
            id=job_id,
            user_id=user_id,
            exam=exam,
            subject=subject,
            difficulty=difficulty,
            question_count=question_count,
            use_proficiency=use_proficiency,
            cost_microcredits=cost_microcredits,
            deduction_ledger_entry_id=ledger_entry.id,
            status=AIJobStatus.PENDING,
            proficiency_score=proficiency_score,
            weak_topics_json=json.dumps(weak_topics or []),
        )

        self.db.add(job)
        self.db.flush()

        logger.info(
            "AI job created: job_id=%s user_id=%s exam=%s subject=%s "
            "questions=%d cost_microcredits=%d",
            job_id, user_id, exam, subject, question_count, cost_microcredits,
        )
        return job, cost_microcredits

    def enqueue_job(self, job: AIJob) -> str:
        """
        Start AI generation as an asyncio task in the FastAPI event loop.
        MUST be called from an async context (async def endpoint) AFTER the
        DB transaction that created the job has committed.

        v2.2.0: Replaces generate_mock_task.apply_async() (Celery).

        Returns:
            job.id (used as task identifier)
        """
        job.status = AIJobStatus.QUEUED
        job.celery_task_id = job.id   # repurposed as asyncio task name for audit trail
        self.db.commit()

        cache_job_status(job.id, {
            "status": "queued",
            "progress_percent": 0,
            "questions_generated": 0,
            "total_questions": job.question_count,
            "mock_id": None,
            "error_message": None,
        })

        set_user_active_job(
            job.user_id,
            job.id,
            ttl=settings.AI_TASK_HARD_TIMEOUT + 60,
        )

        task = asyncio.create_task(
            _run_ai_generation(job_id=job.id),
            name=f"ai_gen_{job.id}",
        )

        logger.info(
            "AI job enqueued as asyncio task: job_id=%s task_name=%s",
            job.id, task.get_name(),
        )
        return job.id

    # ── Status Retrieval ──────────────────────────────────────────────────────

    def get_job_status(self, job_id: str, user_id: int) -> dict:
        """
        Get job status with fresh DB reads for non-terminal jobs.

        v2.1.5 FIX (preserved): Replaced broken identity_map.get((AIJob, (job_id,)))
        with the canonical session.get(AIJob, job_id) API.

        Raises:
            AIJobNotFoundError: job not found or does not belong to user
        """
        cached_instance = self.db.get(AIJob, job_id)
        if cached_instance is not None:
            self.db.expire(cached_instance)

        job = self.db.query(AIJob).filter_by(id=job_id, user_id=user_id).first()
        if not job:
            raise AIJobNotFoundError(job_id)

        if job.is_terminal:
            cached = get_cached_job_status(job_id)
            if cached:
                return {
                    **cached,
                    "job_id": job_id,
                    "cost_credits": job.cost_credits,
                    "created_at": job.created_at.isoformat(),
                    "estimated_seconds": 0,
                }

        return {
            "job_id": job_id,
            "status": job.status.value,
            "progress_percent": job.progress_percent,
            "questions_generated": job.questions_generated,
            "total_questions": job.question_count,
            "mock_id": job.result_mock_id,
            "error_message": job.error_message,
            "cost_credits": job.cost_credits,
            "created_at": job.created_at.isoformat(),
            "estimated_seconds": self._estimate_remaining(job),
        }

    def get_job(self, job_id: str, user_id: int) -> AIJob:
        """Get AIJob by id+user_id. Raises AIJobNotFoundError if not found."""
        job = self.db.query(AIJob).filter_by(id=job_id, user_id=user_id).first()
        if not job:
            raise AIJobNotFoundError(job_id)
        return job

    def get_job_result(self, job_id: str, user_id: int) -> dict:
        """Get result data for a completed job."""
        job = self.get_job(job_id, user_id)
        if not job.result_mock_id:
            raise AIJobNotFoundError(job_id)
        return {
            "job_id": job_id,
            "status": job.status.value,
            "mock_test_id": job.result_mock_id,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }

    def list_jobs(self, user_id: int, limit: int = 10) -> list:
        """Get recent AI jobs for a user."""
        return (
            self.db.query(AIJob)
            .filter_by(user_id=user_id)
            .order_by(AIJob.created_at.desc())
            .limit(limit)
            .all()
        )

    def cancel_job(self, job_id: str, user_id: int) -> dict:
        """Cancel a pending/queued job and refund credits."""
        job = self.get_job(job_id, user_id)
        if job.is_terminal:
            raise ValueError(f"Cannot cancel job in terminal state: {job.status.value}")

        self.mark_job_failed(job_id, "Cancelled by user.")
        return {"cancelled": True, "refunded_credits": job.cost_microcredits // 100}

    def get_user_jobs(self, user_id: int, limit: int = 10) -> list:
        """Get recent AI jobs for a user."""
        return self.list_jobs(user_id, limit)

    # ── Job Completion / Failure ──────────────────────────────────────────────

    def mark_job_completed(self, job_id: str, mock_id: str) -> None:
        """Mark job as completed. Updates DB and Redis."""
        job = self.db.query(AIJob).filter_by(id=job_id).first()
        if not job:
            logger.error("mark_job_completed: job not found: %s", job_id)
            return

        job.status = AIJobStatus.COMPLETED
        job.result_mock_id = mock_id
        job.completed_at = datetime.now(timezone.utc)
        job.progress_percent = 100
        self.db.commit()

        cache_job_status(job_id, {
            "status": "completed",
            "progress_percent": 100,
            "questions_generated": job.question_count,
            "total_questions": job.question_count,
            "mock_id": mock_id,
            "error_message": None,
        })

        clear_user_active_job(job.user_id)
        logger.info("AI job completed: job_id=%s mock_id=%s", job_id, mock_id)

    def mark_job_failed(self, job_id: str, error_message: str) -> None:
        """Mark job as failed and issue credit refund."""
        job = self.db.query(AIJob).filter_by(id=job_id).first()
        if not job:
            logger.error("mark_job_failed: job not found: %s", job_id)
            return

        job.status = AIJobStatus.FAILED
        job.error_message = error_message[:1000]
        job.failed_at = datetime.now(timezone.utc)

        if job.deduction_ledger_entry_id:
            try:
                wallet_service = WalletService(self.db)
                # v2.2.0 FIX: correct parameter name (was `original_ledger_id` — TypeError)
                refund_entry = wallet_service.refund_credits(
                    original_ledger_entry_id=job.deduction_ledger_entry_id,
                    reason=f"AI job failed: {error_message[:200]}",
                )
                if refund_entry:
                    job.refund_ledger_entry_id = refund_entry.id
                    job.status = AIJobStatus.REFUNDED
            except Exception as exc:
                logger.error(
                    "Failed to issue refund for job %s: %s — MANUAL INTERVENTION REQUIRED",
                    job_id, exc,
                )

        self.db.commit()

        cache_job_status(job_id, {
            "status": job.status.value,
            "progress_percent": job.progress_percent,
            "questions_generated": job.questions_generated,
            "total_questions": job.question_count,
            "mock_id": None,
            "error_message": error_message,
        })

        clear_user_active_job(job.user_id)
        logger.info("AI job failed+refunded: job_id=%s error=%s", job_id, error_message)

    def update_job_progress(self, job_id: str, questions_generated: int) -> None:
        """Update progress during generation. Only updates Redis."""
        job = self.db.query(AIJob).filter_by(id=job_id).first()
        if not job:
            return

        percent = int((questions_generated / job.question_count) * 100) if job.question_count else 0

        cache_job_status(job_id, {
            "status": "running",
            "progress_percent": percent,
            "questions_generated": questions_generated,
            "total_questions": job.question_count,
            "mock_id": None,
            "error_message": None,
        })

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _estimate_remaining(self, job: AIJob) -> Optional[int]:
        """Estimate seconds remaining for an active job."""
        if job.is_terminal:
            return 0

        n_batches = max(1, job.question_count // settings.AI_MOCK_BATCH_SIZE)
        batches_done = int(job.progress_percent / 100 * n_batches)
        batches_remaining = n_batches - batches_done

        seconds_per_batch = settings.AI_BATCH_DELAY + 10
        return max(0, batches_remaining * int(seconds_per_batch))


# ── Async AI Generation Coroutine ─────────────────────────────────────────────
# Replaces Celery generate_mock_task. Runs in FastAPI's asyncio event loop.

async def _run_ai_generation(job_id: str) -> None:
    """
    Async coroutine: generate AI mock test questions and save to DB.
    Equivalent to the old Celery generate_mock_task, minus Celery machinery.

    All I/O is already async (httpx in generate_questions, asyncio.sleep for
    inter-batch delays) so this coroutine yields control to the event loop
    during every wait, never blocking other requests.

    Error handling:
      - On any exception: _safe_fail_and_refund() is called → credits refunded.
      - CRITICAL log if refund itself fails (requires manual reconciliation).

    Safety net:
      - If this coroutine is abandoned (process restart while running),
        cleanup_stale_jobs() APScheduler job finds it within 30 minutes
        and issues the refund.
    """
    import traceback as _traceback
    import uuid as _uuid

    from database import SessionLocal
    from models.ai_job import AIJob, AIJobStatus
    from models.mock_test import AIMockQuestion, MockTest
    from services.ai_mock import generate_questions

    logger.info("_run_ai_generation started: job_id=%s", job_id)

    db = SessionLocal()
    job = None

    try:
        job = db.query(AIJob).filter_by(id=job_id).first()

        if not job:
            logger.error("_run_ai_generation: job_id=%s not found — aborting", job_id)
            return

        if job.is_terminal:
            logger.info(
                "_run_ai_generation: job_id=%s already terminal status=%s — skipping",
                job_id, job.status,
            )
            return

        # Transition to RUNNING
        job.status           = AIJobStatus.RUNNING
        job.started_at       = datetime.now(timezone.utc)
        job.attempt_count    += 1
        job.progress_message = "AI is generating your mock test…"
        db.commit()

        cache_job_status(job_id, {
            "status":              "running",
            "progress_percent":    0,
            "questions_generated": 0,
            "total_questions":     job.question_count,
            "mock_id":             None,
            "error_message":       None,
        })

        logger.info(
            "_run_ai_generation: job_id=%s exam=%s subject=%s difficulty=%s questions=%d",
            job_id, job.exam, job.subject, job.difficulty, job.question_count,
        )

        def _progress_callback(questions_generated: int) -> None:
            try:
                percent = int((questions_generated / job.question_count) * 100) if job.question_count else 0
                cache_job_status(job_id, {
                    "status":              "running",
                    "progress_percent":    percent,
                    "questions_generated": questions_generated,
                    "total_questions":     job.question_count,
                    "mock_id":             None,
                    "error_message":       None,
                })
            except Exception:
                pass

        weak_topics = json.loads(job.weak_topics_json or "[]")

        validated_questions = await generate_questions(
            exam=job.exam,
            subject=job.subject,
            difficulty=job.difficulty,
            count=job.question_count,
            proficiency_score=job.proficiency_score or 400.0,
            weak_topics=weak_topics,
            progress_callback=_progress_callback,
        )

        if not validated_questions:
            raise ValueError("AI returned no valid questions")

        # Persist MockTest + AIMockQuestion rows
        mock_test = MockTest(
            id=str(_uuid.uuid4()),
            exam=job.exam,
            subject=job.subject,
            year="AI Generated",
            duration_minutes=max(10, job.question_count * 2),
            total_marks=float(job.question_count),
            question_count=len(validated_questions),
            is_ai_generated=True,
            ai_job_id=job.id,
            ai_generation_params={
                "exam":           job.exam,
                "subject":        job.subject,
                "difficulty":     job.difficulty,
                "question_count": job.question_count,
                "proficiency_score": job.proficiency_score,
                "weak_topics":    weak_topics,
            },
        )
        db.add(mock_test)
        db.flush()

        for i, q in enumerate(validated_questions):
            question_data = {**q, "id": i + 1}
            ai_question = AIMockQuestion(
                mock_id=mock_test.id,
                question_data=question_data,
                position=i + 1,
            )
            db.add(ai_question)

        job.status           = AIJobStatus.COMPLETED
        job.result_mock_id   = str(mock_test.id)
        job.completed_at     = datetime.now(timezone.utc)
        job.progress_percent = 100
        job.progress_message = "Mock test ready!"
        job.error_message    = None
        db.commit()

        cache_job_status(job_id, {
            "status":              "completed",
            "progress_percent":    100,
            "questions_generated": len(validated_questions),
            "total_questions":     job.question_count,
            "mock_id":             str(mock_test.id),
            "error_message":       None,
        })

        clear_user_active_job(job.user_id)

        logger.info(
            "_run_ai_generation COMPLETED: job_id=%s mock_id=%s questions=%d",
            job_id, mock_test.id, len(validated_questions),
        )

    except Exception as exc:
        logger.error(
            "_run_ai_generation FAILED: job_id=%s error=%s\n%s",
            job_id, exc, _traceback.format_exc(),
        )

        try:
            db.rollback()
        except Exception:
            pass

        try:
            _safe_fail_and_refund(db, job_id)
        except Exception as refund_exc:
            logger.critical(
                "REFUND FAILED — MANUAL ACTION REQUIRED: job_id=%s error=%s\n%s",
                job_id, refund_exc, _traceback.format_exc(),
            )

    finally:
        try:
            db.close()
        except Exception:
            pass


def _safe_fail_and_refund(db, job_id: str) -> None:
    """Mark job FAILED and issue credit refund on a clean session after rollback."""
    service = AIJobService(db)
    service.mark_job_failed(
        job_id=job_id,
        error_message="Mock test generation failed. Your credits have been refunded.",
    )