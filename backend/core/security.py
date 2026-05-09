"""
VYAS v2.0 — Core Security Utilities
======================================
Centralised JWT creation/verification and password hashing.
Separated from auth.py to avoid circular imports.

v2.0 changes:
  - create_access_token: uses SECRET_KEY, short expiry (15 min)
  - create_refresh_token: uses REFRESH_SECRET_KEY, long expiry (7 days)
  - verify_access_token / verify_refresh_token: separate verifiers
  - generate_refresh_token_str: cryptographically secure raw token
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import AppConfig

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Access Token ──────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a short-lived JWT access token (default 15 min).
    Signed with SECRET_KEY.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=AppConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, AppConfig.SECRET_KEY, algorithm=AppConfig.ALGORITHM)


def verify_access_token(token: str) -> dict:
    """
    Decodes and validates an access token.
    Raises JWTError on failure.
    """
    payload = jwt.decode(token, AppConfig.SECRET_KEY, algorithms=[AppConfig.ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


# ── Refresh Token ─────────────────────────────────────────────────────────────

def generate_refresh_token_str() -> str:
    """
    Generates a cryptographically secure random refresh token string.
    This is stored hashed in the DB — the raw value goes in the httpOnly cookie.
    """
    return secrets.token_urlsafe(48)


def create_refresh_token_jwt(data: dict) -> str:
    """
    Creates a signed JWT for the refresh token payload.
    Signed with REFRESH_SECRET_KEY (separate from access key).
    NOTE: The raw token sent to client is generate_refresh_token_str(),
    NOT this JWT. This JWT is used internally if you need verifiable claims.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=AppConfig.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, AppConfig.REFRESH_SECRET_KEY, algorithm=AppConfig.ALGORITHM)
