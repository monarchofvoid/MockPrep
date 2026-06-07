"""
VYAS v2.0 — Security Utilities
=================================
Low-level crypto operations. Never import from here into models — only from
services, routers, and auth middleware.

Provides:
  - hash_password / verify_password (bcrypt)
  - create_access_token (15-min HS256 JWT)
  - verify_access_token
  - generate_refresh_token_str (cryptographically secure random)
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import get_settings

settings = get_settings()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── Access Tokens ─────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_access_token(token: str) -> dict:
    """
    Verify and decode an access token.

    Raises:
        JWTError: if token is invalid, expired, or wrong type
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


# ── Refresh Tokens ────────────────────────────────────────────────────────────

def generate_refresh_token_str() -> str:
    """Generate a cryptographically secure 32-byte URL-safe refresh token string."""
    return secrets.token_urlsafe(32)
