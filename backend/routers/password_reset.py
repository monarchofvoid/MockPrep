"""
VYAS v2.0 — Password Reset Router
====================================
Endpoints preserved from v0.6, updated to import from auth shim.
  POST /auth/forgot-password
  POST /auth/reset-password
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import hash_password
from services.email import send_password_reset_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

RESET_TOKEN_EXPIRE_HOURS = 1


@router.post("/forgot-password", status_code=202)
def forgot_password(
    body: schemas.ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Request a password reset email.
    Always returns 202 regardless of whether the email exists (prevents
    user enumeration attacks).
    """
    user = db.query(models.User).filter_by(email=body.email.lower()).first()

    if user:
        # Invalidate any existing reset tokens for this user
        db.query(models.PasswordReset).filter_by(user_id=user.id).delete()
        db.commit()

        token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)

        reset = models.PasswordReset(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token=token,
            expires_at=expires_at,
        )
        db.add(reset)
        db.commit()

        background_tasks.add_task(
            send_password_reset_email,
            to_email=user.email,
            user_name=user.name,
            reset_token=token,
        )
        logger.info("Password reset requested for user_id=%s", user.id)

    # Always 202 — never reveal if email exists
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
def reset_password(
    body: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Complete a password reset using the token from the email link.
    """
    if len(body.new_password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters.")

    reset = (
        db.query(models.PasswordReset)
        .filter_by(token=body.token)
        .first()
    )

    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    if reset.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db.delete(reset)
        db.commit()
        raise HTTPException(status_code=400, detail="Reset token has expired. Please request a new one.")

    user = db.query(models.User).filter_by(id=reset.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.hashed_password = hash_password(body.new_password)

    # Revoke ALL refresh tokens for this user on password change (security)
    now = datetime.now(timezone.utc)
    active_tokens = (
        db.query(models.RefreshToken)
        .filter_by(user_id=user.id)
        .filter(models.RefreshToken.revoked_at.is_(None))
        .all()
    )
    for rt in active_tokens:
        rt.revoked_at = now

    db.delete(reset)
    db.commit()

    logger.info("Password reset completed for user_id=%s", user.id)
    return {"message": "Password updated successfully. Please log in with your new password."}
