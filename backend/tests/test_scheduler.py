"""
VYAS v2.2.0 — Scheduler Tests
================================
Tests for APScheduler setup, job registration, and scheduled job functions.

Tests:
  - test_scheduler_registers_six_jobs: APScheduler has exactly 6 registered jobs
  - test_cleanup_stale_jobs_marks_failed: stale jobs are found and marked FAILED
  - test_cleanup_stale_jobs_issues_refund: refund is issued for stale job credits
  - test_payment_reconcile_skips_when_no_razorpay: graceful skip without credentials
  - test_cleanup_refresh_tokens_deletes_expired: expired tokens are deleted
  - test_reconcile_all_wallets_runs: wallet reconciliation completes without error

Run:
    pytest tests/test_scheduler.py -v
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from models.ai_job import AIJob, AIJobStatus


# ── Test: Scheduler registers exactly 6 jobs ─────────────────────────────────

def test_scheduler_registers_six_jobs():
    """APScheduler must initialize with exactly 6 jobs registered."""
    from unittest.mock import MagicMock

    # Use a memory-only job store to avoid needing Redis in this unit test
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.executors.asyncio import AsyncIOExecutor

    scheduler = AsyncIOScheduler(
        jobstores={"default": MemoryJobStore()},
        executors={"default": AsyncIOExecutor()},
        timezone="UTC",
    )

    from scheduler.setup import register_jobs
    register_jobs(scheduler)

    jobs = scheduler.get_jobs()
    job_ids = {j.id for j in jobs}

    assert len(jobs) == 6, f"Expected 6 jobs, got {len(jobs)}: {job_ids}"

    expected_ids = {
        "cleanup_stale_jobs",
        "reconcile_payments",
        "cleanup_refresh_tokens",
        "cleanup_login_attempts",
        "cleanup_password_resets",
        "reconcile_wallets",
    }
    assert job_ids == expected_ids, (
        f"Job ID mismatch.\nExpected: {expected_ids}\nGot: {job_ids}"
    )


# ── Test: cleanup_stale_jobs marks FAILED ─────────────────────────────────────

@pytest.mark.asyncio
async def test_cleanup_stale_jobs_marks_failed(db, make_user):
    """
    cleanup_stale_jobs() should find RUNNING jobs older than 30 minutes
    and mark them as FAILED.
    """
    from scheduler.jobs import cleanup_stale_jobs

    user = make_user(wallet_microcredits=500)

    # Create a stale RUNNING job (45 minutes old)
    stale_job = AIJob(
        id=str(uuid.uuid4()),
        user_id=user.id,
        exam="CUET",
        subject="Chemistry",
        difficulty="hard",
        question_count=3,
        use_proficiency=False,
        cost_microcredits=45,
        status=AIJobStatus.RUNNING,
        proficiency_score=400.0,
        weak_topics_json="[]",
    )
    stale_job.created_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    db.add(stale_job)
    db.commit()

    # Create a RECENT RUNNING job (5 minutes old — should NOT be touched)
    recent_job = AIJob(
        id=str(uuid.uuid4()),
        user_id=user.id,
        exam="CUET",
        subject="Mathematics",
        difficulty="easy",
        question_count=3,
        use_proficiency=False,
        cost_microcredits=45,
        status=AIJobStatus.RUNNING,
        proficiency_score=400.0,
        weak_topics_json="[]",
    )
    recent_job.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.add(recent_job)
    db.commit()

    with patch("scheduler.jobs.SessionLocal") as mock_sf:
        mock_sf.return_value = db
        with patch("scheduler.jobs.clear_user_active_job"):
            await cleanup_stale_jobs()

    db.expire_all()

    # Stale job should be FAILED
    updated_stale = db.query(AIJob).filter_by(id=stale_job.id).first()
    assert updated_stale.status == AIJobStatus.FAILED

    # Recent job should remain RUNNING (not yet stale)
    updated_recent = db.query(AIJob).filter_by(id=recent_job.id).first()
    assert updated_recent.status == AIJobStatus.RUNNING


# ── Test: cleanup_stale_jobs issues refund ────────────────────────────────────

@pytest.mark.asyncio
async def test_cleanup_stale_jobs_issues_refund(db, make_user):
    """
    cleanup_stale_jobs() should issue a credit refund for stale jobs
    that have a deduction_ledger_entry_id.
    """
    from scheduler.jobs import cleanup_stale_jobs
    from services.wallet_service import WalletService
    from models.wallet import LedgerEntryType

    user = make_user(wallet_microcredits=1000)
    wallet_svc = WalletService(db)

    # Create stale job with a real ledger deduction
    stale_job = AIJob(
        id=str(uuid.uuid4()),
        user_id=user.id,
        exam="JEE",
        subject="Physics",
        difficulty="medium",
        question_count=5,
        use_proficiency=False,
        cost_microcredits=75,
        status=AIJobStatus.QUEUED,
        proficiency_score=400.0,
        weak_topics_json="[]",
    )
    stale_job.created_at = datetime.now(timezone.utc) - timedelta(minutes=60)
    db.add(stale_job)
    db.flush()

    ledger_entry = wallet_svc.deduct_credits(
        user_id=user.id,
        cost_microcredits=75,
        entry_type=LedgerEntryType.AI_MOCK_DEDUCTION,
        idempotency_key=f"ai_mock:{stale_job.id}",
        description="Test deduction",
        ai_job_id=stale_job.id,
    )
    stale_job.deduction_ledger_entry_id = ledger_entry.id
    db.commit()

    balance_before = wallet_svc.get_wallet(user.id).balance_microcredits

    with patch("scheduler.jobs.SessionLocal") as mock_sf:
        mock_sf.return_value = db
        with patch("scheduler.jobs.clear_user_active_job"):
            await cleanup_stale_jobs()

    db.expire_all()

    updated_job = db.query(AIJob).filter_by(id=stale_job.id).first()
    assert updated_job.status == AIJobStatus.FAILED

    balance_after = wallet_svc.get_wallet(user.id).balance_microcredits
    assert balance_after == balance_before + 75, (
        f"Refund not issued: before={balance_before} after={balance_after}"
    )


# ── Test: reconcile_payments skips gracefully without Razorpay creds ─────────

@pytest.mark.asyncio
async def test_payment_reconcile_skips_when_no_razorpay(db):
    """
    reconcile_payments() should log an error and exit gracefully when
    Razorpay credentials are not configured.
    """
    from scheduler.jobs import reconcile_payments

    with patch("scheduler.jobs.SessionLocal") as mock_sf:
        mock_sf.return_value = db
        with patch("scheduler.jobs.get_settings") as mock_settings:
            settings = MagicMock()
            settings.RAZORPAY_KEY_ID = ""
            settings.RAZORPAY_KEY_SECRET = ""
            mock_settings.return_value = settings

            # Should not raise
            await reconcile_payments()


# ── Test: cleanup_expired_refresh_tokens deletes expired tokens ───────────────

@pytest.mark.asyncio
async def test_cleanup_refresh_tokens_deletes_expired(db, make_user):
    """
    cleanup_expired_refresh_tokens() should delete tokens with expires_at in the past.
    """
    from scheduler.jobs import cleanup_expired_refresh_tokens
    from models.user import RefreshToken

    user = make_user()

    # Create expired token (8 days old)
    expired_token = RefreshToken(
        user_id=user.id,
        token_hash="expired_hash_" + str(uuid.uuid4()),
        expires_at=datetime.now(timezone.utc) - timedelta(days=8),
        created_at=datetime.now(timezone.utc) - timedelta(days=8),
    )
    db.add(expired_token)

    # Create valid token (3 days old — should NOT be deleted)
    valid_token = RefreshToken(
        user_id=user.id,
        token_hash="valid_hash_" + str(uuid.uuid4()),
        expires_at=datetime.now(timezone.utc) + timedelta(days=4),
        created_at=datetime.now(timezone.utc) - timedelta(days=3),
    )
    db.add(valid_token)
    db.commit()

    with patch("scheduler.jobs.SessionLocal") as mock_sf:
        mock_sf.return_value = db
        await cleanup_expired_refresh_tokens()

    db.expire_all()

    # Expired token should be deleted
    found_expired = db.query(RefreshToken).filter_by(
        token_hash=expired_token.token_hash
    ).first()
    assert found_expired is None, "Expired token should have been deleted"

    # Valid token should remain
    found_valid = db.query(RefreshToken).filter_by(
        token_hash=valid_token.token_hash
    ).first()
    assert found_valid is not None, "Valid token should not have been deleted"


# ── Test: reconcile_all_wallets runs without error ────────────────────────────

@pytest.mark.asyncio
async def test_reconcile_all_wallets_runs(db, make_user):
    """
    reconcile_all_wallets() should run without error and log consistent
    wallets as passing.
    """
    from scheduler.jobs import reconcile_all_wallets

    # Create a user with a wallet (make_user fixture grants signup bonus)
    make_user(wallet_microcredits=500)

    with patch("scheduler.jobs.SessionLocal") as mock_sf:
        mock_sf.return_value = db
        # Should not raise
        await reconcile_all_wallets()
