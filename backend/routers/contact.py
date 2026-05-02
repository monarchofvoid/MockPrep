"""
VYAS — Contact Router
POST /api/contact

Validates the submission, persists it to the DB (best-effort),
and forwards it to the platform owner via Gmail SMTP.

Security:
  • Inputs stripped and validated by Pydantic
  • Email format checked via EmailStr
  • Message length enforced (10–3000 chars)
  • DB failure never blocks email delivery
  • No internal details exposed to the client
"""

import os
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from services.email import send_contact_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Contact"])

MESSAGE_MIN_LEN = 10
MESSAGE_MAX_LEN = 3000


# ── Request schema ────────────────────────────────────────────────────────────

class ContactRequest(BaseModel):
    name:    str
    email:   EmailStr
    message: str

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required.")
        if len(v) > 120:
            raise ValueError("Name must be under 120 characters.")
        return v

    @field_validator("message")
    @classmethod
    def message_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < MESSAGE_MIN_LEN:
            raise ValueError(f"Message must be at least {MESSAGE_MIN_LEN} characters.")
        if len(v) > MESSAGE_MAX_LEN:
            raise ValueError(f"Message must be under {MESSAGE_MAX_LEN} characters.")
        return v


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/contact", status_code=200)
def contact(body: ContactRequest, db: Session = Depends(get_db)):
    """
    Accept a contact form submission.
    Step 1: Try to save to DB (non-blocking — never fails the request).
    Step 2: Forward to owner via Gmail SMTP.
    Always returns 200 so the user gets clear feedback.
    """
    name    = body.name
    email   = str(body.email)
    message = body.message

    # Step 1 — persist (best-effort)
    try:
        _save_to_db(db, name=name, email=email, message=message)
    except Exception as exc:
        logger.warning("Contact DB insert failed (non-fatal): %s", exc)

    # Step 2 — send email
    sent = send_contact_email(name=name, email=email, message=message)
    if not sent:
        logger.error(
            "Contact email delivery failed for %s <%s>. "
            "Message may still be in DB.",
            name, email,
        )

    return {
        "success": True,
        "message": "Your message has been received. We'll get back to you within 48 hours.",
    }


# ── DB helper ─────────────────────────────────────────────────────────────────

def _is_postgres() -> bool:
    """
    Check DATABASE_URL env var to detect PostgreSQL.
    Avoids using SQLAlchemy's deprecated db.bind attribute.
    """
    db_url = os.getenv("DATABASE_URL", "").lower()
    return db_url.startswith("postgresql") or db_url.startswith("postgres")


def _save_to_db(db: Session, *, name: str, email: str, message: str) -> None:
    """
    Persist the contact submission to contact_messages table.
    Creates the table automatically on first use if it doesn't exist.
    """
    if _is_postgres():
        create_sql = text("""
            CREATE TABLE IF NOT EXISTS contact_messages (
                id         SERIAL PRIMARY KEY,
                name       VARCHAR(120) NOT NULL,
                email      VARCHAR(200) NOT NULL,
                message    TEXT         NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
    else:
        # SQLite fallback (local dev without PostgreSQL)
        create_sql = text("""
            CREATE TABLE IF NOT EXISTS contact_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       VARCHAR(120) NOT NULL,
                email      VARCHAR(200) NOT NULL,
                message    TEXT         NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

    db.execute(create_sql)
    db.execute(
        text(
            "INSERT INTO contact_messages (name, email, message) "
            "VALUES (:name, :email, :message)"
        ),
        {"name": name, "email": email, "message": message},
    )
    db.commit()
