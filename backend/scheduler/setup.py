"""
VYAS v2.2.0 — APScheduler Setup
=================================
Factory and job-registration for the AsyncIOScheduler that replaces
Celery Beat + RedBeat.

Architecture:
  - AsyncIOScheduler runs inside the FastAPI/Uvicorn event loop
  - RedisJobStore persists next_run_time so schedules survive cold starts
  - AsyncIOExecutor runs all job coroutines natively in the event loop
  - replace_existing=True prevents duplicate job registration on restart

Redis keys used:
  apscheduler:jobs       — serialized job definitions
  apscheduler:run_times  — sorted set of next_run_time values per job

These keys are safe to delete for a clean scheduler reset.
Jobs re-register with replace_existing=True on next startup.
"""

import logging
import ssl
import urllib.parse

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("vyas.scheduler")


def _parse_redis_kwargs(redis_url: str) -> dict:
    """
    Parse a Redis URL into keyword arguments for RedisJobStore.

    Supports:
      redis://host:port/db
      rediss://host:port/db     (TLS — Upstash)
      redis://:password@host:port/db
      rediss://:password@host:port/db

    RedisJobStore accepts host, port, db, password, ssl kwargs.
    For TLS (rediss://) we pass ssl=True and ssl_cert_reqs=CERT_NONE
    which matches the Upstash free-tier configuration used for the
    application Redis pool (core/redis.py uses the same TLS approach).
    """
    parsed = urllib.parse.urlparse(redis_url)

    scheme   = parsed.scheme.lower()
    host     = parsed.hostname or "localhost"
    port     = parsed.port or (6380 if scheme == "rediss" else 6379)
    password = parsed.password or None

    # Extract DB number from path (e.g. /0 → 0)
    db_str = parsed.path.lstrip("/")
    db     = int(db_str) if db_str.isdigit() else 0

    kwargs: dict = dict(host=host, port=port, db=db)
    if password:
        kwargs["password"] = password

    if scheme == "rediss":
        # Upstash free tier uses self-signed TLS — disable cert verification
        # to match the existing core/redis.py connection pool behavior.
        kwargs["ssl"] = True
        kwargs["ssl_cert_reqs"] = ssl.CERT_NONE

    return kwargs


def create_scheduler(redis_url: str) -> AsyncIOScheduler:
    """
    Create and configure the AsyncIOScheduler with a Redis job store.

    Args:
        redis_url: Full Redis connection URL (same REDIS_URL used by the app).

    Returns:
        A configured (but not yet started) AsyncIOScheduler.
    """
    redis_kwargs = _parse_redis_kwargs(redis_url)

    jobstores = {
        "default": RedisJobStore(
            jobs_key="apscheduler:jobs",
            run_times_key="apscheduler:run_times",
            **redis_kwargs,
        )
    }
    executors = {
        "default": AsyncIOExecutor()
    }

    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        timezone="UTC",
    )

    return scheduler


def register_jobs(scheduler: AsyncIOScheduler) -> None:
    """
    Register all six scheduled jobs on the scheduler.

    Uses replace_existing=True on every job so that:
      - App restarts do not create duplicate job entries in Redis
      - Schedule changes (e.g. changing hours=1 to hours=2) take effect
        on the next deployment without manually deleting Redis keys

    Schedule equivalence with old Celery Beat schedule:
      Old: cleanup-stale-jobs every 3600s      → hours=1
      Old: reconcile-payments-nightly 86400s   → hours=24
      Old: cleanup-expired-refresh-tokens 86400s → hours=24
      Old: cleanup-old-login-attempts 86400s   → hours=24
      Old: cleanup-expired-password-resets 3600s → hours=1
      Old: (no reconcile_all_wallets in original beat_schedule) → hours=24
    """
    from scheduler.jobs import (
        cleanup_stale_jobs,
        reconcile_payments,
        cleanup_expired_refresh_tokens,
        cleanup_old_login_attempts,
        cleanup_expired_password_resets,
        reconcile_all_wallets,
    )

    scheduler.add_job(
        cleanup_stale_jobs,
        trigger="interval",
        hours=1,
        id="cleanup_stale_jobs",
        replace_existing=True,
        name="Cleanup stale AI jobs + refund credits",
    )

    scheduler.add_job(
        reconcile_payments,
        trigger="interval",
        hours=24,
        id="reconcile_payments",
        replace_existing=True,
        name="Nightly Razorpay payment reconciliation",
    )

    scheduler.add_job(
        cleanup_expired_refresh_tokens,
        trigger="interval",
        hours=24,
        id="cleanup_refresh_tokens",
        replace_existing=True,
        name="Cleanup expired refresh tokens",
    )

    scheduler.add_job(
        cleanup_old_login_attempts,
        trigger="interval",
        hours=24,
        id="cleanup_login_attempts",
        replace_existing=True,
        name="Cleanup old login attempt records",
    )

    scheduler.add_job(
        cleanup_expired_password_resets,
        trigger="interval",
        hours=1,
        id="cleanup_password_resets",
        replace_existing=True,
        name="Cleanup expired password reset tokens",
    )

    scheduler.add_job(
        reconcile_all_wallets,
        trigger="interval",
        hours=24,
        id="reconcile_wallets",
        replace_existing=True,
        name="Nightly wallet balance reconciliation",
    )

    logger.info(
        "APScheduler: registered %d jobs: %s",
        len(scheduler.get_jobs()),
        [j.id for j in scheduler.get_jobs()],
    )
