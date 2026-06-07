"""
VYAS v2.0 — Redis Client & Utilities
=======================================
v2.1 FIX: All bare `except Exception: pass` blocks now log at WARNING level.
           Previously, every Redis failure was completely invisible — no log,
           no warning, just silent degraded behaviour.

Provides:
  - Connection pool for FastAPI (sync)
  - Async pool for Celery tasks
  - Rate limiting helpers (sliding window)
  - Job status cache helpers
  - Wallet balance cache helpers

Redis DB allocation:
  DB 0 → Celery broker + result backend
  DB 1 → Application cache (rate limits, job status, pricing)
"""

import json
import logging
from typing import Any, Optional

import redis
from redis import ConnectionPool

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Connection Pools ──────────────────────────────────────────────────────────

def _build_pool(db: int) -> ConnectionPool:
    """Build a Redis connection pool for the given database index."""
    base_url = settings.REDIS_URL.rstrip("/")
    parts = base_url.rsplit("/", 1)
    if len(parts) == 2 and parts[1].isdigit():
        url = f"{parts[0]}/{db}"
    else:
        url = f"{base_url}/{db}"
    return ConnectionPool.from_url(url, decode_responses=True, max_connections=20)


_broker_pool: Optional[ConnectionPool] = None
_cache_pool: Optional[ConnectionPool] = None


def get_redis() -> redis.Redis:
    """
    Get a Redis client for application cache (DB 1).
    Used for: rate limits, job status, pricing cache, wallet balance cache.
    """
    global _cache_pool
    if _cache_pool is None:
        _cache_pool = _build_pool(settings.REDIS_CACHE_DB)
    return redis.Redis(connection_pool=_cache_pool)


def get_broker_redis() -> redis.Redis:
    """
    Get a Redis client for Celery broker (DB 0).
    Used for: enqueueing Celery tasks, checking queue length.
    """
    global _broker_pool
    if _broker_pool is None:
        _broker_pool = _build_pool(0)
    return redis.Redis(connection_pool=_broker_pool)


def ping_redis() -> bool:
    """Check if Redis is reachable. Returns True/False (never raises)."""
    try:
        return get_redis().ping()
    except Exception as exc:
        logger.warning("Redis ping failed: %s", exc)
        return False


# ── Rate Limiting — Sliding Window ────────────────────────────────────────────

def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
    redis_client: Optional[redis.Redis] = None,
) -> tuple[bool, int]:
    """
    Sliding window rate limiter using Redis sorted set.

    Returns:
        (allowed: bool, remaining: int)
    """
    if redis_client is None:
        redis_client = get_redis()

    import time
    now = time.time()
    window_start = now - window_seconds

    pipe = redis_client.pipeline(transaction=True)
    try:
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds + 10)
        results = pipe.execute()

        current_count = results[1]
        allowed = current_count < limit
        remaining = max(0, limit - current_count - 1) if allowed else 0
        return allowed, remaining

    except redis.RedisError as exc:
        logger.warning("Rate limit Redis error (fail-open): key=%s error=%s", key, exc)
        return True, limit


def get_rate_limit_reset_time(key: str, window_seconds: int) -> int:
    """Returns seconds until the oldest entry in this rate limit window expires."""
    try:
        r = get_redis()
        oldest = r.zrange(key, 0, 0, withscores=True)
        if oldest:
            import time
            oldest_ts = oldest[0][1]
            reset_at = oldest_ts + window_seconds
            return max(0, int(reset_at - time.time()))
    except redis.RedisError as exc:
        logger.warning("Rate limit reset time Redis error: key=%s error=%s", key, exc)
    except Exception as exc:
        logger.warning("Rate limit reset time unexpected error: %s", exc)
    return window_seconds


# ── Job Status Cache ───────────────────────────────────────────────────────────

JOB_STATUS_TTL = settings.REDIS_JOB_TTL  # 24 hours


def cache_job_status(job_id: str, status_data: dict) -> None:
    """Store AI job status in Redis for fast polling."""
    key = f"job:status:{job_id}"
    try:
        r = get_redis()
        r.setex(key, JOB_STATUS_TTL, json.dumps(status_data))
    except redis.RedisError as exc:
        logger.warning("Failed to cache job status: job_id=%s error=%s", job_id, exc)
    except Exception as exc:
        logger.warning("Unexpected error caching job status: job_id=%s error=%s", job_id, exc)


def get_cached_job_status(job_id: str) -> Optional[dict]:
    """Retrieve cached job status. Returns None if not found or Redis unavailable."""
    key = f"job:status:{job_id}"
    try:
        r = get_redis()
        raw = r.get(key)
        if raw:
            return json.loads(raw)
    except redis.RedisError as exc:
        logger.warning("Failed to get cached job status: job_id=%s error=%s", job_id, exc)
    except Exception as exc:
        logger.warning("Unexpected error reading job status: job_id=%s error=%s", job_id, exc)
    return None


def delete_job_status_cache(job_id: str) -> None:
    """Remove job status from Redis (called after job is archived)."""
    try:
        get_redis().delete(f"job:status:{job_id}")
    except redis.RedisError as exc:
        logger.warning("Failed to delete job status cache: job_id=%s error=%s", job_id, exc)
    except Exception as exc:
        logger.warning("Unexpected error deleting job status: job_id=%s error=%s", job_id, exc)


# ── Wallet Balance Cache ───────────────────────────────────────────────────────

WALLET_CACHE_TTL = 300  # 5 minutes


def cache_wallet_balance(user_id: int, balance_microcredits: int) -> None:
    """Cache user's wallet balance for fast reads on every page load."""
    key = f"wallet:balance:{user_id}"
    try:
        get_redis().setex(key, WALLET_CACHE_TTL, str(balance_microcredits))
    except redis.RedisError as exc:
        logger.warning("Failed to cache wallet balance: user_id=%s error=%s", user_id, exc)
    except Exception as exc:
        logger.warning("Unexpected error caching wallet balance: user_id=%s error=%s", user_id, exc)


def get_cached_wallet_balance(user_id: int) -> Optional[int]:
    """Get cached wallet balance. Returns None if not cached."""
    key = f"wallet:balance:{user_id}"
    try:
        val = get_redis().get(key)
        if val is not None:
            return int(val)
    except redis.RedisError as exc:
        logger.warning("Failed to get cached wallet balance: user_id=%s error=%s", user_id, exc)
    except Exception as exc:
        logger.warning("Unexpected error reading wallet balance cache: user_id=%s error=%s", user_id, exc)
    return None


def invalidate_wallet_cache(user_id: int) -> None:
    """Invalidate wallet balance cache after any balance change."""
    try:
        get_redis().delete(f"wallet:balance:{user_id}")
    except redis.RedisError as exc:
        logger.warning("Failed to invalidate wallet cache: user_id=%s error=%s", user_id, exc)
    except Exception as exc:
        logger.warning("Unexpected error invalidating wallet cache: user_id=%s error=%s", user_id, exc)


# ── Pricing Cache ─────────────────────────────────────────────────────────────

PRICING_CACHE_TTL = 300  # 5 minutes


def cache_feature_pricing(pricing_data: dict) -> None:
    """Cache feature pricing dict (feature_key -> cost_microcredits)."""
    try:
        get_redis().setex("pricing:features", PRICING_CACHE_TTL, json.dumps(pricing_data))
    except redis.RedisError as exc:
        logger.warning("Failed to cache feature pricing: %s", exc)
    except Exception as exc:
        logger.warning("Unexpected error caching feature pricing: %s", exc)


def get_cached_feature_pricing() -> Optional[dict]:
    """Get cached feature pricing."""
    try:
        raw = get_redis().get("pricing:features")
        if raw:
            return json.loads(raw)
    except redis.RedisError as exc:
        logger.warning("Failed to get cached feature pricing: %s", exc)
    except Exception as exc:
        logger.warning("Unexpected error reading feature pricing cache: %s", exc)
    return None


def invalidate_pricing_cache() -> None:
    """Called when an admin updates pricing."""
    try:
        get_redis().delete("pricing:features")
    except redis.RedisError as exc:
        logger.warning("Failed to invalidate pricing cache: %s", exc)
    except Exception as exc:
        logger.warning("Unexpected error invalidating pricing cache: %s", exc)


# ── Idempotency Key Store ─────────────────────────────────────────────────────

IDEMPOTENCY_TTL = 86400  # 24 hours


def mark_idempotency_key_used(key: str) -> bool:
    """
    Mark an idempotency key as used in Redis.
    Returns True if first use (proceed), False if duplicate (skip).
    """
    try:
        r = get_redis()
        result = r.set(f"idem:{key}", "1", nx=True, ex=IDEMPOTENCY_TTL)
        return result is True
    except redis.RedisError as exc:
        logger.warning("Idempotency Redis error (fail-safe: allow): key=%s error=%s", key, exc)
        return True  # Fail-safe: DB constraint will catch duplicates


# ── Active AI Job Tracking ────────────────────────────────────────────────────

def set_user_active_job(user_id: int, job_id: str, ttl: int = 600) -> None:
    """Track that a user has an active AI job (prevents concurrent submissions)."""
    try:
        get_redis().setex(f"user:active_job:{user_id}", ttl, job_id)
    except redis.RedisError as exc:
        logger.warning("Failed to set active job marker: user_id=%s error=%s", user_id, exc)
    except Exception as exc:
        logger.warning("Unexpected error setting active job: user_id=%s error=%s", user_id, exc)


def get_user_active_job(user_id: int) -> Optional[str]:
    """Get the active job ID for a user, if any."""
    try:
        return get_redis().get(f"user:active_job:{user_id}")
    except redis.RedisError as exc:
        logger.warning("Failed to get active job: user_id=%s error=%s", user_id, exc)
        return None
    except Exception as exc:
        logger.warning("Unexpected error getting active job: user_id=%s error=%s", user_id, exc)
        return None


def clear_user_active_job(user_id: int) -> None:
    """Remove the active job marker when job completes or fails."""
    try:
        get_redis().delete(f"user:active_job:{user_id}")
    except redis.RedisError as exc:
        logger.warning("Failed to clear active job: user_id=%s error=%s", user_id, exc)
    except Exception as exc:
        logger.warning("Unexpected error clearing active job: user_id=%s error=%s", user_id, exc)