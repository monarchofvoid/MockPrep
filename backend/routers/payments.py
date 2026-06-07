"""
VYAS v2.2.0 — Payments Router
==============================
v2.2.0 Migration: Celery → BackgroundTasks

Changes from v2.1.5:
  1. razorpay_webhook(): accepts BackgroundTasks (injected by FastAPI) and
     passes it to service.handle_webhook(). FastAPI runs BackgroundTasks after
     the HTTP response is sent — identical fire-and-forget semantics to the
     old Celery send_payment_receipt_task.delay() call.

All security hardening from v2.1.5 is fully preserved and unchanged.
"""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.config import get_settings
from core.exceptions import (
    DuplicateWebhookError,
    InvalidPaymentSignatureError,
    InvalidPlanError,
    PaymentNotFoundError,
)
from database import get_db
from middleware.rate_limit import payment_rate_limit
from models.user import User
from schemas.payment import (
    CreateOrderRequest,
    CreateOrderResponse,
    CreditPlanOut,
    PaymentStatusResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from services.payment_service import PaymentService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])

_MAX_ORDER_ID_LEN = 64


# ── List Plans ────────────────────────────────────────────────────────────────

@router.get("/plans", response_model=list[CreditPlanOut])
def get_plans(db: Session = Depends(get_db)):
    """Get all available credit plans. Public endpoint — no auth required."""
    service = PaymentService(db)
    return service.get_active_plans()


# ── Create Order ──────────────────────────────────────────────────────────────

@router.post("/create-order", response_model=CreateOrderResponse, status_code=201)
def create_order(
    body: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(payment_rate_limit),
):
    """Create a Razorpay payment order for a credit plan."""
    service = PaymentService(db)
    try:
        order = service.create_order(user_id=current_user.id, plan_id=body.plan_id)
        db.commit()
    except InvalidPlanError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create payment order: user_id=%s error=%s", current_user.id, exc)
        raise HTTPException(status_code=502, detail="Payment service unavailable. Please retry.")

    return CreateOrderResponse(
        internal_order_id=order.id,
        razorpay_order_id=order.razorpay_order_id,
        razorpay_key_id=settings.RAZORPAY_KEY_ID,
        amount_paise=order.amount_paise,
        currency=order.currency,
        credits_to_grant=order.credits_to_grant // 100,
    )


# ── Verify Payment (client-side) ──────────────────────────────────────────────

@router.post("/verify", response_model=VerifyPaymentResponse)
def verify_payment(
    body: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(payment_rate_limit),
):
    """Verify Razorpay HMAC signature after client-side payment."""
    service = PaymentService(db)
    try:
        order = service.verify_payment_signature(
            razorpay_order_id=body.razorpay_order_id,
            razorpay_payment_id=body.razorpay_payment_id,
            razorpay_signature=body.razorpay_signature,
        )
        db.commit()
    except InvalidPaymentSignatureError:
        raise HTTPException(status_code=400, detail="Payment signature verification failed.")
    except PaymentNotFoundError:
        raise HTTPException(status_code=404, detail="Payment order not found.")

    return VerifyPaymentResponse(
        status="pending_webhook",
        order_id=order.id,
        razorpay_order_id=order.razorpay_order_id,
        message="Payment received. Credits will be added to your account within a few seconds.",
    )


# ── Webhook Handler ───────────────────────────────────────────────────────────

@router.post("/webhook", status_code=200)
async def razorpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: str = Header(None, alias="X-Razorpay-Event-Id"),
):
    """
    Razorpay webhook handler.

    v2.2.0: BackgroundTasks injected by FastAPI and passed to PaymentService
    so the receipt email fires after the HTTP 200 response is sent to Razorpay.
    This preserves the fire-and-forget semantics of the old Celery approach.
    """
    if not x_razorpay_signature:
        logger.warning("Webhook received without X-Razorpay-Signature header — rejected")
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header")

    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        logger.warning("Webhook rejected: unexpected Content-Type=%s", content_type)
        raise HTTPException(status_code=400, detail="Content-Type must be application/json")

    raw_body = await request.body()

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if (
        x_razorpay_event_id
        and not payload.get("id")
        and isinstance(x_razorpay_event_id, str)
        and 0 < len(x_razorpay_event_id) <= 128
        and x_razorpay_event_id.isprintable()
    ):
        payload["id"] = x_razorpay_event_id
        logger.info("Injected event_id from header: %s", x_razorpay_event_id)

    event_id   = payload.get("id", "unknown")
    event_type = payload.get("event", "unknown")

    logger.info("Webhook received: event_id=%s event_type=%s", event_id, event_type)

    service = PaymentService(db)

    try:
        service.verify_webhook_signature(raw_body, x_razorpay_signature)
    except InvalidPaymentSignatureError:
        logger.warning(
            "Webhook signature verification FAILED: event_id=%s event_type=%s",
            event_id, event_type,
        )
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        result = service.handle_webhook(raw_body, payload, background_tasks=background_tasks)
        db.commit()
        logger.info(
            "Webhook processed: event_id=%s event_type=%s processed=%s",
            event_id, event_type, result.get("processed"),
        )
        return {"status": "ok", **result}

    except DuplicateWebhookError as exc:
        db.rollback()
        logger.info("Duplicate webhook acknowledged: event_id=%s", exc.details.get("event_id"))
        return {"status": "already_processed"}

    except Exception as exc:
        db.rollback()
        logger.error(
            "Webhook processing error: event_id=%s event_type=%s error=%s",
            event_id, event_type, exc, exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Webhook processing failed")


# ── Payment Status Polling ────────────────────────────────────────────────────

@router.get("/status/{razorpay_order_id}", response_model=PaymentStatusResponse)
def get_payment_status(
    razorpay_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll payment status. Frontend calls every 3 seconds until settled or failed."""
    if not razorpay_order_id or len(razorpay_order_id) > _MAX_ORDER_ID_LEN:
        raise HTTPException(status_code=400, detail="Invalid order ID format.")

    service = PaymentService(db)
    try:
        order = service.get_order_status(razorpay_order_id, current_user.id)
    except PaymentNotFoundError:
        raise HTTPException(status_code=404, detail="Payment order not found.")

    return PaymentStatusResponse(
        internal_order_id=order.id,
        razorpay_order_id=order.razorpay_order_id,
        status=order.status.value,
        credits_granted=order.credits_to_grant // 100 if order.status.value == "settled" else None,
        amount_inr=order.amount_paise / 100,
        failure_reason=order.failure_reason,
    )