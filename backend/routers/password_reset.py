"""
VYAS — Password Reset Router
POST /auth/forgot-password   — request a reset link
POST /auth/reset-password    — submit new password with token

Security model:
  • Raw token  → sent in email URL, never stored
  • Hashed token (SHA-256) → stored in password_resets table
  • Token TTL: 15 minutes
  • One-time use: record deleted immediately after successful reset
  • No user-enumeration: forgot-password always returns 200
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

TOKEN_EXPIRE_MINUTES = 15
MIN_PASSWORD_LENGTH  = 8


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_raw_token() -> str:
    """Cryptographically secure 256-bit URL-safe token."""
    return secrets.token_urlsafe(32)


def _hash_token(raw: str) -> str:
    """SHA-256 hash of the raw token — what gets stored in the DB."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _purge_user_resets(db: Session, user_id: int) -> None:
    """Remove all existing reset tokens for this user before issuing a new one."""
    db.query(models.PasswordReset).filter_by(user_id=user_id).delete()
    db.flush()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/forgot-password", status_code=200)
def forgot_password(
    body: schemas.ForgotPasswordRequest,
    db:   Session = Depends(get_db),
):
    """
    Generate a reset token for the given email (if it exists) and send
    the link via Gmail SMTP. Always returns the same 200 response to
    prevent user enumeration.
    """
    SAFE_RESPONSE = {
        "message": "If that email is registered, a reset link has been sent."
    }

    user = db.query(models.User).filter_by(email=body.email).first()

    if not user or not user.is_active:
        logger.info("Forgot-password: no active account for submitted email (not disclosed)")
        return SAFE_RESPONSE

    # One token at a time — purge any existing record first
    _purge_user_resets(db, user.id)

    raw_token    = _generate_raw_token()
    hashed_token = _hash_token(raw_token)
    expires_at   = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)

    db.add(models.PasswordReset(
        id         = str(uuid.uuid4()),
        user_id    = user.id,
        token      = hashed_token,
        expires_at = expires_at,
    ))
    db.commit()

    sent = send_password_reset_email(to_email=user.email, reset_token=raw_token)
    if not sent:
        logger.warning(
            "Forgot-password: email delivery failed for user_id=%s. "
            "Raw token (dev-only): %s",
            user.id, raw_token,
        )

    return SAFE_RESPONSE


@router.post("/reset-password", status_code=200)
def reset_password(
    body: schemas.ResetPasswordRequest,
    db:   Session = Depends(get_db),
):
    """
    Verify token, validate new password, update hash, delete token.
    """
    BAD_TOKEN = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This reset link is invalid or has expired.",
    )

    # 1. Validate password length first (cheap check before hitting DB)
    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )

    # 2. Look up hashed token
    hashed = _hash_token(body.token)
    record = db.query(models.PasswordReset).filter_by(token=hashed).first()
    if not record:
        raise BAD_TOKEN

    # 3. Check expiry — handle both timezone-aware and naive datetimes
    now     = datetime.now(timezone.utc)
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if now > expires:
        db.delete(record)
        db.commit()
        raise BAD_TOKEN

    # 4. Fetch user
    user = db.query(models.User).filter_by(id=record.user_id).first()
    if not user or not user.is_active:
        raise BAD_TOKEN

    # 5. Update password using same bcrypt helper as signup
    user.hashed_password = hash_password(body.new_password)

    # 6. Delete token (one-time use)
    db.delete(record)
    db.commit()

    logger.info("Password reset successful for user_id=%s", user.id)
    return {"message": "Password updated successfully. You can now sign in."}
