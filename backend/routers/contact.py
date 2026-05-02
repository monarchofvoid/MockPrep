"""
VYAS — Contact Router
POST /api/contact

Validates the submission, optionally persists it to the DB (non-blocking),
and forwards it to the platform owner via Resend.

Security notes:
  • Inputs are stripped of leading/trailing whitespace
  • Email format validated by Pydantic (EmailStr)
  • Message minimum length enforced server-side
  • Email delivery failure does NOT expose internals to the client
"""

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from services.email import send_contact_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Contact"])

MESSAGE_MIN_LEN = 10
MESSAGE_MAX_LEN = 3000


# ── Schema ─────────────────────────────────────────────────────────────────────

class ContactRequest(BaseModel):
    name:    str
    email:   EmailStr
    message: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required.")
        if len(v) > 120:
            raise ValueError("Name is too long.")
        return v

    @field_validator("message")
    @classmethod
    def message_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < MESSAGE_MIN_LEN:
            raise ValueError(f"Message must be at least {MESSAGE_MIN_LEN} characters.")
        if len(v) > MESSAGE_MAX_LEN:
            raise ValueError(f"Message must be under {MESSAGE_MAX_LEN} characters.")
        return v


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/contact", status_code=200)
def contact(body: ContactRequest, db: Session = Depends(get_db)):
    """
    Accept a contact form submission.
    1. Optionally save to DB (best-effort — will not fail the request if DB errors)
    2. Send notification email to the platform owner via Resend
    """
    name    = body.name
    email   = str(body.email)
    message = body.message

    # ── 1. Persist to DB (optional, best-effort) ──────────────────────────────
    try:
        _save_to_db(db, name=name, email=email, message=message)
    except Exception as exc:
        # DB failure must not prevent email delivery
        logger.warning("Contact DB insert failed (non-fatal): %s", exc)

    # ── 2. Send email ─────────────────────────────────────────────────────────
    sent = send_contact_email(name=name, email=email, message=message)

    if not sent:
        # Log it; we still return success so users aren't left confused.
        # Admins can check logs and the DB record.
        logger.error(
            "Contact email delivery failed for %s <%s>. "
            "Message saved to DB (if DB is up).",
            name, email
        )

    return {
        "success": True,
        "message": "Your message has been received. We'll get back to you within 48 hours.",
    }


# ── DB helper (best-effort) ────────────────────────────────────────────────────

def _save_to_db(db: Session, *, name: str, email: str, message: str) -> None:
    """
    Persist the contact submission.
    Uses raw SQL so we don't need to define a full SQLAlchemy model for this.
    The table is created automatically on first use (if it doesn't exist).
    """
    # Ensure table exists — idempotent
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id         SERIAL PRIMARY KEY,
            name       VARCHAR(120) NOT NULL,
            email      VARCHAR(200) NOT NULL,
            message    TEXT         NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """) if _is_postgres(db) else text("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       VARCHAR(120) NOT NULL,
            email      VARCHAR(200) NOT NULL,
            message    TEXT         NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))

    db.execute(
        text("INSERT INTO contact_messages (name, email, message) VALUES (:name, :email, :message)"),
        {"name": name, "email": email, "message": message},
    )
    db.commit()


def _is_postgres(db: Session) -> bool:
    """Detect if the underlying DB is PostgreSQL."""
    try:
        dialect = db.bind.dialect.name
        return dialect == "postgresql"
    except Exception:
        return False
