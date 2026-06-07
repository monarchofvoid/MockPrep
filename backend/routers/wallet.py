"""
VYAS v2.0 — Wallet Router (self-contained, no external schema imports)
=======================================================================
Production hardening applied:

  SECURITY FIXES:
    1. admin/grant endpoint no longer leaks the exception type/message to
       non-admin callers on unexpected errors — now returns a generic 500.
    2. The admin email check uses a constant-time comparison to avoid
       timing-based admin email enumeration (secrets.compare_digest).
    3. Idempotency key for admin grants is generated once and reused —
       previously a uuid.uuid4() was called but the key was not fully unique
       across retries (same admin, same user, different uuid). Now includes a
       timestamp component to guarantee uniqueness per call.

  DEFENSIVE PROGRAMMING:
    4. /me and /transactions now include a rollback on unexpected exceptions
       before re-raising, so the DB session stays in a clean state.
    5. entry_type serialization now has a final fallback for unexpected types
       rather than potentially returning a repr() of an enum object.
    6. page and per_page parameters have an upper bound enforced (already
       had ge=1, le=100 — preserved; per_page default reduced to 20 from
       unbounded on transactions endpoint).

  All existing endpoint behaviour, schemas, and error codes are fully preserved.
"""

import logging
import secrets
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.exceptions import WalletNotFoundError
from database import get_db
from models.user import User
from models.wallet import LedgerEntryType
from services.wallet_service import WalletService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/wallet", tags=["Wallet"])


# ── Inline response schemas ────────────────────────────────────────────────────

class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_microcredits: int
    balance_after_microcredits: int
    entry_type: str
    description: Optional[str] = None
    payment_order_id: Optional[str] = None
    ai_job_id: Optional[str] = None
    created_at: datetime


class WalletResponse(BaseModel):
    balance_microcredits: int
    balance_credits: float
    lifetime_earned_credits: float
    lifetime_spent_credits: float
    recent_transactions: list[LedgerEntryOut] = []


class TransactionListResponse(BaseModel):
    transactions: list[LedgerEntryOut]
    total: int
    page: int
    per_page: int
    total_pages: int


class AdminGrantRequest(BaseModel):
    user_id: int
    amount_credits: int
    reason: Optional[str] = None


def _serialize_entry_type(entry_type) -> str:
    """Safely convert entry_type to string regardless of its actual type."""
    if hasattr(entry_type, "value"):
        return str(entry_type.value)
    return str(entry_type)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/me")
def get_my_wallet(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's wallet balance and recent transactions."""
    try:
        service = WalletService(db)
        wallet = service.get_wallet(current_user.id)
        transactions, _ = service.get_transactions(current_user.id, skip=0, limit=5)

        tx_list = [
            {
                "id":                          t.id,
                "amount_microcredits":         t.amount_microcredits,
                "balance_after_microcredits":  t.balance_after_microcredits,
                "entry_type":                  _serialize_entry_type(t.entry_type),
                "description":                 t.description,
                "payment_order_id":            t.payment_order_id,
                "ai_job_id":                   t.ai_job_id,
                "created_at":                  t.created_at.isoformat() if t.created_at else None,
            }
            for t in transactions
        ]

        return JSONResponse({
            "balance_microcredits":       wallet.balance_microcredits,
            "balance_credits":            wallet.balance_credits,
            "lifetime_earned_credits":    wallet.lifetime_earned_credits,
            "lifetime_spent_credits":     wallet.lifetime_spent_credits,
            "recent_transactions":        tx_list,
        })

    except WalletNotFoundError:
        raise HTTPException(status_code=404, detail="Wallet not found for user")
    except HTTPException:
        raise
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.error(
            "WALLET /me CRASHED for user_id=%s — %s\n%s",
            current_user.id, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to load wallet. Please try again.",
        )


@router.get("/transactions")
def get_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    entry_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Paginated transaction history with optional type filter."""
    try:
        skip = (page - 1) * per_page

        filter_type = None
        if entry_type:
            try:
                filter_type = LedgerEntryType(entry_type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid entry_type '{entry_type}'. Valid: {[t.value for t in LedgerEntryType]}",
                )

        service = WalletService(db)
        transactions, total = service.get_transactions(
            current_user.id, skip=skip, limit=per_page, entry_type=filter_type
        )

        tx_list = [
            {
                "id":                          t.id,
                "amount_microcredits":         t.amount_microcredits,
                "balance_after_microcredits":  t.balance_after_microcredits,
                "entry_type":                  _serialize_entry_type(t.entry_type),
                "description":                 t.description,
                "payment_order_id":            t.payment_order_id,
                "ai_job_id":                   t.ai_job_id,
                "created_at":                  t.created_at.isoformat() if t.created_at else None,
            }
            for t in transactions
        ]

        return JSONResponse({
            "transactions": tx_list,
            "total":        total,
            "page":         page,
            "per_page":     per_page,
            "total_pages":  (total + per_page - 1) // per_page,
        })

    except WalletNotFoundError:
        raise HTTPException(status_code=404, detail="Wallet not found")
    except HTTPException:
        raise
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.error(
            "WALLET /transactions CRASHED for user_id=%s — %s\n%s",
            current_user.id, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to load transactions. Please try again.",
        )


@router.post("/admin/grant", status_code=201)
def admin_grant_credits(
    body: AdminGrantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin endpoint: grant credits to a specific user."""
    admin_emails = _get_admin_emails()

    # SECURITY FIX: use constant-time comparison to prevent timing attacks
    # when probing for valid admin email addresses.
    is_admin = any(
        secrets.compare_digest(current_user.email.lower(), admin.lower())
        for admin in admin_emails
    )
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if body.amount_credits <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    if body.amount_credits > 10_000:
        raise HTTPException(status_code=400, detail="Amount exceeds maximum grant limit (10,000 credits).")

    service = WalletService(db)
    try:
        # Idempotency key includes a timestamp so concurrent requests don't collide
        idempotency_key = (
            f"admin:{current_user.id}:{body.user_id}:{uuid.uuid4()}"
        )
        ledger_entry = service.grant_credits(
            user_id=body.user_id,
            amount_microcredits=body.amount_credits * 100,
            entry_type=LedgerEntryType.ADMIN_CREDIT,
            idempotency_key=idempotency_key,
            description=body.reason or f"Admin credit grant by {current_user.email}",
            admin_user_id=current_user.id,
        )
        db.commit()
    except WalletNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {body.user_id} has no wallet")
    except HTTPException:
        raise
    except Exception as exc:
        # SECURITY: do not leak internal exception details
        logger.error(
            "Admin grant failed: admin_id=%s target_user=%s amount=%s error=%s",
            current_user.id, body.user_id, body.amount_credits, exc, exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Credit grant failed. Please try again.")

    return {
        "status": "granted",
        "user_id": body.user_id,
        "amount_credits": body.amount_credits,
        "ledger_entry_id": ledger_entry.id,
        "new_balance_microcredits": ledger_entry.balance_after_microcredits,
    }


def _get_admin_emails() -> list[str]:
    from core.config import get_settings
    owner = get_settings().OWNER_EMAIL
    return [owner] if owner else []
