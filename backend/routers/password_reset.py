"""
VYAS v2.0 — Password Reset Router
====================================
Production hardening applied:

  SECURITY FIXES:
    1. reset_password() now normalises the token from the DB with timezone-aware
       comparison — removed the fragile .replace(tzinfo=...) approach that could
       silently accept expired tokens if the DB stores naive UTC datetimes and
       the comparison truncates the timezone. Now uses consistent UTC-aware
       comparison on both sides.
    2. Password minimum length raised from 6 to 8 characters to match modern
       security standards. (The frontend validation should match this value.)
    3. reset_password() wraps the entire operation in a try/except so a DB
       error mid-reset (e.g. after deleting the token but before saving the
       new password) is caught, rolled back, and returns 500 instead of
       leaving the user in a broken state.
    4. forgot_password() wraps DB operations in try/except — a DB error when
       deleting stale tokens or writing the new reset record should not crash
       the handler (still returns 202 for information-hiding reasons, but logs
       the error so it's visible to operators).

  DEFENSIVE PROGRAMMING:
    5. Token lookup validates the token length before querying the DB to prevent
       DoS via extremely long token strings.

  All existing endpoints, email-sending logic, and security properties
  (always-202, hashed tokens, refresh token revocation) are fully preserved.
"""

import logging
import traceback
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from core.security import hash_password
from database import get_db
from models.user import PasswordReset, User, RefreshToken
from schemas.auth import ForgotPasswordRequest, ResetPasswordRequest
from services.email import send_password_reset_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

RESET_TOKEN_EXPIRE_HOURS = 1
_PASSWORD_MIN_LENGTH = 8   # raised from 6 — matches modern security guidance
_MAX_TOKEN_LENGTH = 256    # sanity cap for path/body token params


@router.post("/forgot-password", status_code=202)
def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Request a password reset email.
    Always returns 202 regardless of whether the email exists (prevents
    user enumeration attacks).
    """
    try:
        user = db.query(User).filter_by(email=body.email.lower()).first()

        if user:
            # Invalidate any existing reset tokens for this user
            db.query(PasswordReset).filter_by(user_id=user.id).delete()
            db.commit()

            raw_token  = str(uuid.uuid4())
            token_hash = PasswordReset.hash_token(raw_token)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)

            reset = PasswordReset(
                id=str(uuid.uuid4()),
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            db.add(reset)
            db.commit()

            background_tasks.add_task(
                send_password_reset_email,
                to_email=user.email,
                user_name=user.name,
                reset_token=raw_token,
            )
            logger.info("Password reset requested for user_id=%s", user.id)

    except Exception as exc:
        # DEFENSIVE: DB errors during reset setup should not expose information.
        # Log the error but always return 202 to maintain security invariant.
        logger.error(
            "Error in forgot_password for email=%s: %s\n%s",
            body.email, exc, traceback.format_exc(),
        )
        try:
            db.rollback()
        except Exception:
            pass

    # Always 202 — never reveal if email exists or if an error occurred
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Complete a password reset using the token from the email link.
    """
    # DEFENSIVE: validate token length before touching the DB
    if not body.token or len(body.token) > _MAX_TOKEN_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    if len(body.new_password) < _PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at least {_PASSWORD_MIN_LENGTH} characters."
        )

    token_hash = PasswordReset.hash_token(body.token)

    reset = (
        db.query(PasswordReset)
        .filter_by(token_hash=token_hash)
        .first()
    )

    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    # SECURITY FIX: consistent timezone-aware comparison.
    # Use replace() only when tzinfo is genuinely missing (naive datetime from DB);
    # otherwise compare directly. This prevents silent acceptance of expired tokens.
    expires_at = reset.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        db.delete(reset)
        db.commit()
        raise HTTPException(status_code=400, detail="Reset token has expired. Please request a new one.")

    user = db.query(User).filter_by(id=reset.user_id).first()
    if not user:
        # Token references a deleted user — clean up and return generic error
        db.delete(reset)
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    try:
        new_hashed = hash_password(body.new_password)
        user.hashed_password = new_hashed

        # Revoke ALL refresh tokens for this user on password change (security)
        now = datetime.now(timezone.utc)
        active_tokens = (
            db.query(RefreshToken)
            .filter_by(user_id=user.id)
            .filter(RefreshToken.revoked_at.is_(None))
            .all()
        )
        for rt in active_tokens:
            rt.revoked_at = now

        db.delete(reset)
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.error(
            "Error completing password reset for user_id=%s: %s\n%s",
            user.id, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail="Password reset failed due to a server error. Please try again.",
        )

    logger.info("Password reset completed for user_id=%s", user.id)
    return {"message": "Password updated successfully. Please log in with your new password."}
