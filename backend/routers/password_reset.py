"""
VYAS — Password Reset Router
Implements POST /auth/forgot-password and POST /auth/reset-password.

Security model:
  • Raw token  → sent in email URL (never persisted)
  • Hashed token (SHA-256) → stored in password_resets table
  • Verification: hash the submitted token and compare with stored hash
  • Token TTL: 15 minutes
  • One-time use: token is deleted immediately after a successful reset
  • No user-enumeration: /forgot-password always returns 200
"""

import hashlib
import secrets
import uuid
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import hash_password
from services.email import send_password_reset_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

# ── Constants ─────────────────────────────────────────────────────────────────

TOKEN_EXPIRE_MINUTES = 15
MIN_PASSWORD_LENGTH  = 8   # enforce slightly stronger rule on reset


# ── Internal helpers ──────────────────────────────────────────────────────────

def _generate_raw_token() -> str:
    """
    Generate a cryptographically secure URL-safe token (256 bits of entropy).
    Uses secrets.token_urlsafe — NOT Math.random or uuid4 alone.
    """
    return secrets.token_urlsafe(32)   # 32 bytes → 43 URL-safe chars


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash a token for safe storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _purge_expired_resets(db: Session, user_id: int) -> None:
    """Delete any existing (possibly expired) reset records for this user."""
    db.query(models.PasswordReset).filter_by(user_id=user_id).delete()
    db.flush()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/forgot-password", status_code=200)
def forgot_password(
    body: schemas.ForgotPasswordRequest,
    db:   Session = Depends(get_db),
):
    """
    Accept an email and — if the user exists — generate a reset token,
    store it (hashed), and send a reset email.

    Always returns the same 200 response regardless of whether the email
    exists, to prevent user enumeration.
    """
    SAFE_RESPONSE = {"message": "If that email is registered, a reset link has been sent."}

    user = db.query(models.User).filter_by(email=body.email).first()

    if not user or not user.is_active:
        # Return success silently — do NOT reveal whether the account exists
        logger.info("Forgot-password: no active user found for email (not disclosed)")
        return SAFE_RESPONSE

    # Purge any existing reset tokens for this user (one-token-at-a-time policy)
    _purge_expired_resets(db, user.id)

    # Generate token
    raw_token    = _generate_raw_token()
    hashed_token = _hash_token(raw_token)
    expires_at   = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)

    reset_record = models.PasswordReset(
        id         = str(uuid.uuid4()),
        user_id    = user.id,
        token      = hashed_token,
        expires_at = expires_at,
    )
    db.add(reset_record)
    db.commit()

    # Send email (non-blocking: a send failure must not expose user existence)
    sent = send_password_reset_email(to_email=user.email, reset_token=raw_token)
    if not sent:
        logger.warning(
            "Forgot-password: email delivery failed for user_id=%s. "
            "Raw token (dev only): %s",
            user.id, raw_token
        )

    return SAFE_RESPONSE


@router.post("/reset-password", status_code=200)
def reset_password(
    body: schemas.ResetPasswordRequest,
    db:   Session = Depends(get_db),
):
    """
    Verify the reset token, enforce password rules, update the hashed
    password, and invalidate the token.
    """
    INVALID_TOKEN_ERROR = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This reset link is invalid or has expired.",
    )

    # ── 1. Validate new password before touching the DB ──────────────────────
    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )

    # ── 2. Hash the submitted token and look it up ───────────────────────────
    hashed_submitted = _hash_token(body.token)

    reset_record = (
        db.query(models.PasswordReset)
        .filter_by(token=hashed_submitted)
        .first()
    )

    if not reset_record:
        raise INVALID_TOKEN_ERROR

    # ── 3. Check expiry ───────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    # expires_at may be naive (SQLite) or aware (Postgres); normalise
    expires = reset_record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if now > expires:
        # Clean up the stale record
        db.delete(reset_record)
        db.commit()
        raise INVALID_TOKEN_ERROR

    # ── 4. Fetch user ─────────────────────────────────────────────────────────
    user = db.query(models.User).filter_by(id=reset_record.user_id).first()
    if not user or not user.is_active:
        raise INVALID_TOKEN_ERROR

    # ── 5. Hash new password and update (uses same bcrypt helper as signup) ──
    user.hashed_password = hash_password(body.new_password)

    # ── 6. One-time use — delete the token record immediately ─────────────────
    db.delete(reset_record)

    db.commit()
    logger.info("Password reset successful for user_id=%s", user.id)

    return {"message": "Password updated successfully. You can now sign in."}
