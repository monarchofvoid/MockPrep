"""
VYAS v2.0 — Rate Limiting Middleware
=======================================
Redis-backed sliding window rate limiter as FastAPI dependency.

v0.11 had rate limit CONSTANTS defined in config but NEVER ENFORCED.
This implementation actually enforces them.

Usage in routers:
    from middleware.rate_limit import ai_rate_limit, auth_rate_limit

    @router.post("/generate")
    def generate(
        _: None = Depends(ai_rate_limit),
        current_user = Depends(get_current_user),
    ):
        ...

Rate limit keys:
    auth endpoints: rl:auth:ip:{ip_address}
    AI endpoints:   rl:ai:user:{user_id}
    payments:       rl:pay:user:{user_id}
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from core.config import get_settings
from core.redis import check_rate_limit, get_rate_limit_reset_time

logger = logging.getLogger(__name__)
settings = get_settings()

oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, checking X-Forwarded-For for proxy setups."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def make_rate_limiter(
    key_prefix: str,
    limit: int,
    window_seconds: int,
    key_type: str = "ip",  # "ip" or "user"
):
    """
    Factory function that returns a FastAPI dependency for rate limiting.

    Args:
        key_prefix: Redis key prefix (e.g., "rl:auth")
        limit: max requests per window
        window_seconds: window duration in seconds
        key_type: "ip" for IP-based, "user" for per-user limits
    """
    async def rate_limit_dependency(
        request: Request,
        token: Optional[str] = Depends(oauth2_scheme_optional),
    ):
        if key_type == "ip":
            identifier = _get_client_ip(request)
            redis_key = f"{key_prefix}:{identifier}"
        else:
            # User-based rate limiting requires auth token
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            # Extract user_id from token without full validation
            # (full validation happens in get_current_user — this is just for rate limiting)
            try:
                from core.security import verify_access_token
                payload = verify_access_token(token)
                user_id = payload.get("sub", "unknown")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                )
            redis_key = f"{key_prefix}:{user_id}"

        allowed, remaining = check_rate_limit(redis_key, limit, window_seconds)

        if not allowed:
            retry_after = get_rate_limit_reset_time(redis_key, window_seconds)
            logger.warning(
                "Rate limit exceeded: key=%s limit=%d window=%ds",
                redis_key, limit, window_seconds,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Limit: {limit} per {window_seconds}s",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

    return rate_limit_dependency


# Pre-built rate limiters for common use cases

auth_rate_limit = make_rate_limiter(
    key_prefix="rl:auth",
    limit=settings.RATE_LIMIT_AUTH_REQUESTS,
    window_seconds=settings.RATE_LIMIT_AUTH_WINDOW,
    key_type="ip",
)

ai_rate_limit = make_rate_limiter(
    key_prefix="rl:ai",
    limit=settings.RATE_LIMIT_AI_REQUESTS,
    window_seconds=settings.RATE_LIMIT_AI_WINDOW,
    key_type="user",
)

payment_rate_limit = make_rate_limiter(
    key_prefix="rl:pay",
    limit=settings.RATE_LIMIT_PAYMENT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_PAYMENT_WINDOW,
    key_type="user",
)
