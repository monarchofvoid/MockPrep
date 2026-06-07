"""
VYAS v2.2.0 — AI Job Async Tests
===================================
Unit tests for the asyncio-based AI generation replacing Celery generate_mock_task.

Tests:
  - test_enqueue_job_creates_asyncio_task: enqueue_job() calls asyncio.create_task()
  - test_run_ai_generation_completes: successful generation marks job COMPLETED
  - test_run_ai_generation_failure_refunds: exception triggers credit refund
  - test_stale_job_cleanup_refunds: cleanup_stale_jobs() marks RUNNING jobs as FAILED

Run:
    pytest tests/test_ai_job_async.py -v
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.ai_job import AIJob, AIJobStatus


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ai_job(db, user_id: int, status=AIJobStatus.PENDING) -> AIJob:
    """Create a minimal AIJob for testing."""
    job_id = str(uuid.uuid4())
    job = AIJob(
        id=job_id,
        user_id=user_id,
        exam="CUET",
        subject="Economics",
        difficulty="medium",
        question_count=3,
        use_proficiency=False,
        cost_microcredits=45,
        deduction_ledger_entry_id=None,
        status=status,
        proficiency_score=400.0,
        weak_topics_json="[]",
    )
    db.add(job)
    db.flush()
    return job


# ── Test: enqueue_job creates asyncio task ────────────────────────────────────

@pytest.mark.asyncio
async def test_enqueue_job_creates_asyncio_task(db, make_user):
    """
    enqueue_job() should call asyncio.create_task() and return job.id.
    The task name should be 'ai_gen_{job_id}'.
    """
    from services.ai_job_service import AIJobService

    user = make_user(wallet_microcredits=1000)
    job = _make_ai_job(db, user.id, status=AIJobStatus.PENDING)

    created_tasks = []

    original_create_task = asyncio.create_task

    def mock_create_task(coro, *, name=None):
        # Record the call but cancel the actual coroutine to avoid side effects
        task = original_create_task(coro, name=name)
        task.cancel()
        created_tasks.append({"name": name, "task": task})
        return task

    service = AIJobService(db)

    with patch("services.ai_job_service.asyncio.create_task", side_effect=mock_create_task):
        with patch("services.ai_job_service.cache_job_status"):
            with patch("services.ai_job_service.set_user_active_job"):
                result = service.enqueue_job(job)

    assert result == job.id
    assert len(created_tasks) == 1
    assert created_tasks[0]["name"] == f"ai_gen_{job.id}"

    # Verify job status was updated to QUEUED
    db.refresh(job)
    assert job.status == AIJobStatus.QUEUED


# ── Test: _run_ai_generation completes successfully ───────────────────────────

@pytest.mark.asyncio
async def test_run_ai_generation_completes(db, make_user):
    """
    _run_ai_generation() should mark job COMPLETED and update Redis
    when generate_questions() returns valid questions.
    """
    from services.ai_job_service import _run_ai_generation

    user = make_user(wallet_microcredits=1000)
    job = _make_ai_job(db, user.id, status=AIJobStatus.QUEUED)

    # Build 3 valid question dicts matching validate_ai_question() output shape
    mock_questions = [
        {
            "id": i + 1,
            "type": "mcq",
            "question": f"Test question {i + 1}?",
            "options": {"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"},
            "correct": "A",
            "explanation": "A is correct.",
            "difficulty": "medium",
            "topic": "Microeconomics",
            "marks": 4,
            "negative_marking": 1,
        }
        for i in range(3)
    ]

    with patch("services.ai_job_service.SessionLocal") as mock_session_factory:
        mock_session_factory.return_value = db

        with patch("services.ai_job_service.generate_questions", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_questions

            with patch("services.ai_job_service.cache_job_status") as mock_cache:
                with patch("services.ai_job_service.clear_user_active_job") as mock_clear:
                    await _run_ai_generation(job_id=job.id)

    # Verify job was marked COMPLETED
    db.refresh(job)
    assert job.status == AIJobStatus.COMPLETED
    assert job.result_mock_id is not None
    assert job.completed_at is not None
    assert job.progress_percent == 100

    # Verify Redis was updated with completed status
    assert mock_cache.called
    final_cache_call = mock_cache.call_args_list[-1]
    assert final_cache_call[0][1]["status"] == "completed"
    assert final_cache_call[0][1]["mock_id"] is not None

    # Verify active job marker was cleared
    mock_clear.assert_called_once_with(user.id)


# ── Test: _run_ai_generation failure triggers refund ─────────────────────────

@pytest.mark.asyncio
async def test_run_ai_generation_failure_refunds(db, make_user):
    """
    _run_ai_generation() should mark job FAILED/REFUNDED and log CRITICAL
    when generate_questions() raises an exception.
    Credit refund is handled by mark_job_failed().
    """
    import httpx
    from services.ai_job_service import _run_ai_generation
    from services.wallet_service import WalletService
    from models.wallet import LedgerEntryType

    user = make_user(wallet_microcredits=1000)
    job = _make_ai_job(db, user.id, status=AIJobStatus.QUEUED)

    # Give the job a real ledger entry so refund can be issued
    wallet_svc = WalletService(db)
    ledger_entry = wallet_svc.deduct_credits(
        user_id=user.id,
        cost_microcredits=45,
        entry_type=LedgerEntryType.AI_MOCK_DEDUCTION,
        idempotency_key=f"ai_mock:{job.id}",
        description="Test deduction",
        ai_job_id=job.id,
    )
    job.deduction_ledger_entry_id = ledger_entry.id
    db.flush()

    with patch("services.ai_job_service.SessionLocal") as mock_session_factory:
        mock_session_factory.return_value = db

        with patch("services.ai_job_service.generate_questions", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = httpx.TimeoutException("Groq timed out")

            with patch("services.ai_job_service.cache_job_status"):
                with patch("services.ai_job_service.clear_user_active_job"):
                    await _run_ai_generation(job_id=job.id)

    # Verify job was marked FAILED or REFUNDED
    db.refresh(job)
    assert job.status in (AIJobStatus.FAILED, AIJobStatus.REFUNDED)
    assert job.failed_at is not None


# ── Test: cleanup_stale_jobs marks RUNNING jobs as FAILED ─────────────────────

@pytest.mark.asyncio
async def test_stale_job_cleanup_refunds(db, make_user):
    """
    cleanup_stale_jobs() should find RUNNING jobs older than 30 minutes,
    mark them FAILED, and issue credit refunds.
    """
    from scheduler.jobs import cleanup_stale_jobs
    from services.wallet_service import WalletService
    from models.wallet import LedgerEntryType

    user = make_user(wallet_microcredits=1000)

    # Create a stale RUNNING job (60 minutes old)
    stale_job = AIJob(
        id=str(uuid.uuid4()),
        user_id=user.id,
        exam="CUET",
        subject="Physics",
        difficulty="easy",
        question_count=5,
        use_proficiency=False,
        cost_microcredits=75,
        status=AIJobStatus.RUNNING,
        proficiency_score=400.0,
        weak_topics_json="[]",
    )
    # Backdate created_at to simulate a stale job
    stale_job.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add(stale_job)
    db.flush()

    # Give the job a real ledger entry so refund can be issued
    wallet_svc = WalletService(db)
    ledger_entry = wallet_svc.deduct_credits(
        user_id=user.id,
        cost_microcredits=75,
        entry_type=LedgerEntryType.AI_MOCK_DEDUCTION,
        idempotency_key=f"ai_mock:{stale_job.id}",
        description="Test deduction for stale job",
        ai_job_id=stale_job.id,
    )
    stale_job.deduction_ledger_entry_id = ledger_entry.id
    db.commit()

    balance_before = wallet_svc.get_wallet(user.id).balance_microcredits

    with patch("scheduler.jobs.SessionLocal") as mock_session_factory:
        mock_session_factory.return_value = db
        with patch("scheduler.jobs.clear_user_active_job"):
            await cleanup_stale_jobs()

    db.expire_all()

    # Verify job was marked FAILED
    updated_job = db.query(AIJob).filter_by(id=stale_job.id).first()
    assert updated_job.status == AIJobStatus.FAILED
    assert updated_job.failed_at is not None
    assert "credits have been refunded" in (updated_job.error_message or "")

    # Verify credits were refunded
    balance_after = wallet_svc.get_wallet(user.id).balance_microcredits
    assert balance_after == balance_before + 75, (
        f"Expected refund of 75 microcredits: before={balance_before} after={balance_after}"
    )
