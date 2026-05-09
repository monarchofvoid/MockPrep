"""
VYAS v2.0 — Auth Router
=========================
Endpoints:
  POST /auth/signup   — register a new user
  POST /auth/login    — login, returns access token + sets httpOnly refresh cookie
  POST /auth/refresh  — exchange refresh cookie for new access token (token rotation)
  POST /auth/logout   — revoke refresh token + clear cookie
  GET  /auth/me       — return current user info

v2.0 security improvements:
  - Access tokens: 15-minute expiry (was 7 days)
  - Refresh tokens: 7-day expiry, stored as SHA-256 hash in DB
  - Refresh tokens delivered via httpOnly, SameSite=Lax cookie (not JS-accessible)
  - Token rotation: each /refresh invalidates the old token and issues a new one
  - Brute-force protection: 5 failed attempts → 15-minute lockout (per email)
  - Login attempts logged in DB for audit trail
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

import models
import schemas
from config import AppConfig
from core.auth import get_current_user
from core.security import (
    create_access_token,
    generate_refresh_token_str,
    hash_password,
    verify_password,
)
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    """Write the refresh token into a secure httpOnly cookie."""
    max_age = AppConfig.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    response.set_cookie(
        key=AppConfig.REFRESH_TOKEN_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=AppConfig.REFRESH_TOKEN_COOKIE_SECURE,
        samesite=AppConfig.REFRESH_TOKEN_COOKIE_SAMESITE,
        max_age=max_age,
        domain=AppConfig.COOKIE_DOMAIN,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh token cookie."""
    response.delete_cookie(
        key=AppConfig.REFRESH_TOKEN_COOKIE_NAME,
        path="/",
        domain=AppConfig.COOKIE_DOMAIN,
    )


def _store_refresh_token(
    db: Session,
    user_id: int,
    raw_token: str,
    request: Request,
) -> models.RefreshToken:
    """Hash and persist a refresh token record in the database."""
    token_hash = models.RefreshToken.hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=AppConfig.REFRESH_TOKEN_EXPIRE_DAYS)
    ua = request.headers.get("User-Agent", "")[:300]
    ip = request.client.host if request.client else None

    rt = models.RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=ua,
        ip_address=ip,
    )
    db.add(rt)
    db.commit()
    db.refresh(rt)
    return rt


def _check_brute_force(db: Session, email: str) -> None:
    """
    Raises HTTP 429 if the email has too many recent failed attempts.
    Window: LOGIN_LOCKOUT_MINUTES. Threshold: MAX_LOGIN_ATTEMPTS.
    """
    window_start = datetime.now(timezone.utc) - timedelta(
        minutes=AppConfig.LOGIN_LOCKOUT_MINUTES
    )
    failed_count = (
        db.query(models.LoginAttempt)
        .filter(
            and_(
                models.LoginAttempt.email == email.lower(),
                models.LoginAttempt.success == False,  # noqa: E712
                models.LoginAttempt.attempted_at >= window_start,
            )
        )
        .count()
    )
    if failed_count >= AppConfig.MAX_LOGIN_ATTEMPTS:
        logger.warning("Brute-force lockout triggered for email=%s", email)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many failed login attempts. "
                f"Please wait {AppConfig.LOGIN_LOCKOUT_MINUTES} minutes before trying again."
            ),
        )


def _record_attempt(db: Session, email: str, request: Request, success: bool) -> None:
    """Persist a login attempt record for audit / brute-force tracking."""
    ip = request.client.host if request.client else None
    attempt = models.LoginAttempt(
        email=email.lower(),
        ip_address=ip,
        success=success,
    )
    db.add(attempt)
    db.commit()


# ─── Signup ───────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=schemas.TokenResponse, status_code=201)
def signup(
    body: schemas.SignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Register a new user.
    Returns: access token in body + refresh token in httpOnly cookie.
    """
    if db.query(models.User).filter_by(email=body.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        name=body.name.strip(),
        email=body.email.lower().strip(),
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Issue tokens
    access_token = create_access_token({"sub": str(user.id)})
    raw_refresh = generate_refresh_token_str()
    _store_refresh_token(db, user.id, raw_refresh, request)
    _set_refresh_cookie(response, raw_refresh)

    logger.info("New user registered: id=%s email=%s", user.id, user.email)
    return schemas.TokenResponse(access_token=access_token, user=user)


# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=schemas.TokenResponse)
def login(
    body: schemas.LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticate with email + password.
    Returns: access token in body + refresh token in httpOnly cookie.

    Security:
      - Brute-force protection: checked before credential verification
      - Constant-time password check (passlib bcrypt)
      - Failed attempts logged for audit
    """
    email = body.email.lower().strip()

    # Brute-force gate — checked before touching credentials
    _check_brute_force(db, email)

    user = db.query(models.User).filter_by(email=email).first()

    # Use constant-time comparison regardless of whether user exists
    # (dummy hash avoids timing-based user enumeration)
    _DUMMY_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"
    password_ok = verify_password(
        body.password,
        user.hashed_password if user else _DUMMY_HASH,
    )

    if not user or not password_ok:
        _record_attempt(db, email, request, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    _record_attempt(db, email, request, success=True)

    # Issue tokens
    access_token = create_access_token({"sub": str(user.id)})
    raw_refresh = generate_refresh_token_str()
    _store_refresh_token(db, user.id, raw_refresh, request)
    _set_refresh_cookie(response, raw_refresh)

    logger.info("User login: id=%s", user.id)
    return schemas.TokenResponse(access_token=access_token, user=user)


# ─── Refresh ──────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=schemas.RefreshResponse)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    vyas_refresh: str | None = Cookie(default=None, alias=AppConfig.REFRESH_TOKEN_COOKIE_NAME),
):
    """
    Silent token refresh — called automatically by the frontend interceptor.

    Flow:
      1. Read refresh token from httpOnly cookie
      2. Find non-revoked, non-expired record in DB
      3. Revoke the old token (rotation — prevents reuse)
      4. Issue a new access token + new refresh token
      5. Set the new refresh cookie

    This endpoint is the ONLY way to get a new access token after expiry.
    It is completely transparent to the user.
    """
    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token invalid or expired. Please log in again.",
    )

    if not vyas_refresh:
        raise invalid_exc

    token_hash = models.RefreshToken.hash_token(vyas_refresh)
    now = datetime.now(timezone.utc)

    rt = (
        db.query(models.RefreshToken)
        .filter(
            and_(
                models.RefreshToken.token_hash == token_hash,
                models.RefreshToken.revoked_at.is_(None),
                models.RefreshToken.expires_at > now,
            )
        )
        .first()
    )

    if not rt:
        # Token not found / already revoked / expired → force re-login
        _clear_refresh_cookie(response)
        raise invalid_exc

    user = db.query(models.User).filter_by(id=rt.user_id).first()
    if not user or not user.is_active:
        rt.revoke()
        db.commit()
        _clear_refresh_cookie(response)
        raise invalid_exc

    # ── Token rotation: revoke old, issue new ────────────────────────────────
    rt.revoke()
    db.commit()

    new_access = create_access_token({"sub": str(user.id)})
    new_raw_refresh = generate_refresh_token_str()
    _store_refresh_token(db, user.id, new_raw_refresh, request)
    _set_refresh_cookie(response, new_raw_refresh)

    logger.debug("Token refreshed for user_id=%s", user.id)
    return schemas.RefreshResponse(access_token=new_access, user=user)


# ─── Logout ───────────────────────────────────────────────────────────────────

@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    vyas_refresh: str | None = Cookie(default=None, alias=AppConfig.REFRESH_TOKEN_COOKIE_NAME),
):
    """
    Logout: revokes the current refresh token in the DB and clears the cookie.
    Access token will expire naturally (max 15 min).
    """
    if vyas_refresh:
        token_hash = models.RefreshToken.hash_token(vyas_refresh)
        rt = (
            db.query(models.RefreshToken)
            .filter_by(token_hash=token_hash, user_id=current_user.id)
            .first()
        )
        if rt and not rt.is_revoked:
            rt.revoke()
            db.commit()

    _clear_refresh_cookie(response)
    logger.info("User logged out: id=%s", current_user.id)
    # 204 No Content


# ─── Me ───────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    """Return the authenticated user's basic info."""
    return current_user
