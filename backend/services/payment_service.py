"""
VYAS v2.2.0 — Payment Service
==============================
v2.2.0 Migration: Celery → BackgroundTasks

Changes from v2.1.5:
  1. handle_webhook(): accepts optional `background_tasks: BackgroundTasks`
     and threads it through to _handle_payment_captured().
  2. _handle_payment_captured(): replaced send_payment_receipt_task.delay()
     with background_tasks.add_task(send_payment_receipt_email, ...).
  3. _enqueue_receipt_email(): new helper — BackgroundTasks path (webhook)
     or synchronous path (reconciliation scheduler).

All security hardening from v2.1.5 is fully preserved and unchanged.
"""

import hashlib
import hmac
import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from core.config import get_settings
from core.exceptions import (
    DuplicateWebhookError,
    InvalidPaymentSignatureError,
    InvalidPlanError,
    PaymentAmountMismatchError,
    PaymentNotFoundError,
)
from models.payment import CreditPlan, PaymentOrder, PaymentOrderStatus, WebhookEvent
from models.wallet import LedgerEntryType
from services.wallet_service import WalletService

logger = logging.getLogger(__name__)
settings = get_settings()


class RazorpayGatewayError(Exception):
    """Raised when the Razorpay API call itself fails (network, auth, etc.)."""
    pass


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self._razorpay_client = None

    def _get_razorpay_client(self):
        if self._razorpay_client is None:
            try:
                import razorpay
                self._razorpay_client = razorpay.Client(
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
                )
            except ImportError:
                raise RuntimeError("razorpay package not installed. Run: pip install razorpay")
        return self._razorpay_client

    # ── Plans ─────────────────────────────────────────────────────────────────

    def get_active_plans(self) -> list:
        return (
            self.db.query(CreditPlan)
            .filter_by(is_active=True)
            .order_by(CreditPlan.amount_paise)
            .all()
        )

    # ── Create Order ──────────────────────────────────────────────────────────

    def create_order(self, user_id: int, plan_id: int) -> PaymentOrder:
        """
        Create a Razorpay payment order and persist a PaymentOrder record.
        NOTE: Does NOT call db.commit() — commit is the caller's responsibility.
        """
        plan = self.db.query(CreditPlan).filter_by(id=plan_id, is_active=True).first()
        if not plan:
            raise InvalidPlanError(plan_id)

        try:
            client = self._get_razorpay_client()
            rz_order = client.order.create({
                "amount":          plan.amount_paise,
                "currency":        "INR",
                "payment_capture": 1,
                "notes": {
                    "user_id": str(user_id),
                    "plan_id": str(plan_id),
                    "credits": str(plan.credits_granted),  # BUG FIX: was plan.credits_microcredits (attr doesn't exist); credits_granted is already in credits
                },
            })
        except Exception as exc:
            logger.error(
                "Razorpay order creation FAILED: user_id=%s plan_id=%s error=%s",
                user_id, plan_id, exc,
            )
            raise RazorpayGatewayError(f"Razorpay API error: {exc}") from exc

        order = PaymentOrder(
            id=str(uuid.uuid4()),  # BUG FIX: PaymentOrder.id is String(36) PK with no DB default.
            # Without this, SQLAlchemy inserts NULL → NotNullViolation crash on flush.
            user_id=user_id,
            plan_id=plan_id,
            razorpay_order_id=rz_order["id"],
            amount_paise=plan.amount_paise,
            currency="INR",
            credits_to_grant=plan.microcredits_to_grant,
            status=PaymentOrderStatus.CREATED,
        )
        self.db.add(order)
        self.db.flush()

        logger.info(
            "PaymentOrder created: order_id=%s rz_order_id=%s user_id=%s amount_paise=%s",
            order.id, rz_order["id"], user_id, plan.amount_paise,
        )
        return order

    # ── Verify Signature (client-side) ────────────────────────────────────────

    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> PaymentOrder:
        """Verify client-side Razorpay HMAC signature."""
        order = (
            self.db.query(PaymentOrder)
            .filter_by(razorpay_order_id=razorpay_order_id)
            .first()
        )
        if not order:
            raise PaymentNotFoundError(razorpay_order_id)

        message  = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, razorpay_signature):
            logger.warning(
                "Client-side signature MISMATCH: order_id=%s payment_id=%s",
                razorpay_order_id, razorpay_payment_id,
            )
            raise InvalidPaymentSignatureError()

        order.razorpay_payment_id = razorpay_payment_id
        order.status              = PaymentOrderStatus.VERIFIED
        order.verified_at         = datetime.now(timezone.utc)

        logger.info(
            "Payment verified (client): order_id=%s payment_id=%s",
            order.id, razorpay_payment_id,
        )
        return order

    # ── Webhook Signature Verification ────────────────────────────────────────

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> None:
        """Verify Razorpay webhook HMAC-SHA256 signature."""
        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise InvalidPaymentSignatureError()

    # ── Handle Webhook ────────────────────────────────────────────────────────

    def handle_webhook(
        self,
        raw_body: bytes,
        payload: dict,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> dict:
        """
        Process a verified Razorpay webhook event.

        v2.2.0: accepts optional background_tasks parameter.
        When provided, receipt emails are sent via BackgroundTasks (non-blocking).
        When None (reconciliation scheduler), emails are sent synchronously.

        Returns: {"processed": True, "action": "<description>"}
        Raises: DuplicateWebhookError if already processed.
        """
        event_id   = payload.get("id", "unknown")
        event_type = payload.get("event", "unknown")

        existing = self.db.query(WebhookEvent).filter_by(event_id=event_id).first()
        if existing:
            raise DuplicateWebhookError(event_id)

        webhook_event = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            received_at=datetime.now(timezone.utc),
        )
        self.db.add(webhook_event)
        self.db.flush()

        if event_type == "payment.captured":
            return self._handle_payment_captured(
                payload, webhook_event, background_tasks=background_tasks
            )
        elif event_type == "payment.failed":
            return self._handle_payment_failed(payload)
        elif event_type == "order.paid":
            logger.info("Webhook order.paid received (informational): event_id=%s", event_id)
            return {"processed": True, "action": "acknowledged_order_paid"}
        elif event_type == "refund.created":
            return self._handle_refund_created(payload)
        else:
            logger.info("Unhandled webhook event_type=%s — acknowledging", event_type)
            return {"processed": True, "action": f"acknowledged_{event_type}"}

    def _handle_payment_captured(
        self,
        payload: dict,
        webhook_event: WebhookEvent,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> dict:
        """Process payment.captured webhook event."""
        payment_entity     = payload.get("payload", {}).get("payment", {}).get("entity", {})
        razorpay_order_id  = payment_entity.get("order_id")
        razorpay_payment_id = payment_entity.get("id")
        amount_paise        = payment_entity.get("amount", 0)

        if not razorpay_order_id:
            logger.warning("payment.captured webhook missing order_id")
            return {"processed": True, "action": "skipped_missing_order_id"}

        order = (
            self.db.query(PaymentOrder)
            .filter_by(razorpay_order_id=razorpay_order_id)
            .first()
        )
        if not order:
            logger.warning(
                "payment.captured: PaymentOrder not found for rz_order_id=%s",
                razorpay_order_id,
            )
            return {"processed": True, "action": "order_not_found"}

        if order.status == PaymentOrderStatus.SETTLED:
            logger.info("Order already settled (idempotent): order_id=%s", order.id)
            return {"processed": True, "action": "already_settled"}

        # Amount fraud check
        if amount_paise != order.amount_paise:
            logger.critical(
                "PAYMENT AMOUNT MISMATCH: order_id=%s expected_paise=%s received_paise=%s "
                "rz_payment_id=%s — FLAGGING for manual review",
                order.id, order.amount_paise, amount_paise, razorpay_payment_id,
            )
            order.status         = PaymentOrderStatus.FAILED
            order.failure_reason = (
                f"Amount mismatch: expected {order.amount_paise}, received {amount_paise}"
            )
            webhook_event.processing_notes = "amount_mismatch"
            raise PaymentAmountMismatchError(
                expected=order.amount_paise,
                received=amount_paise,
                order_id=str(order.id),
            )

        if order.status not in (PaymentOrderStatus.CREATED, PaymentOrderStatus.VERIFIED):
            logger.warning(
                "payment.captured for order in unexpected status=%s order_id=%s — skipping",
                order.status, order.id,
            )
            return {"processed": True, "action": f"skipped_status_{order.status.value}"}

        order.razorpay_payment_id = razorpay_payment_id
        order.status              = PaymentOrderStatus.SETTLED
        order.settled_at          = datetime.now(timezone.utc)

        self._grant_credits_for_order(order)
        webhook_event.processing_notes = "credits_granted"

        logger.info(
            "Payment settled: order_id=%s user_id=%s credits=%s",
            order.id, order.user_id, order.credits_to_grant // 100,
        )

        # v2.2.0: Use FastAPI BackgroundTasks instead of Celery task dispatch.
        self._enqueue_receipt_email(order, background_tasks)

        return {
            "processed": True,
            "action":    "credits_granted",
            "credits":   order.credits_to_grant // 100,
        }

    def _enqueue_receipt_email(
        self,
        order: PaymentOrder,
        background_tasks: Optional[BackgroundTasks],
    ) -> None:
        """
        Schedule or send the payment receipt email.

        BackgroundTasks path (background_tasks provided — normal webhook):
          → uses FastAPI BackgroundTasks.add_task() (non-blocking)

        Synchronous path (background_tasks is None — reconciliation scheduler):
          → calls send_payment_receipt_email() directly in try/except
        """
        from services.email import send_payment_receipt_email
        from models.user import User

        try:
            user = self.db.query(User).filter_by(id=order.user_id).first()
            if not user:
                logger.warning(
                    "_enqueue_receipt_email: user_id=%s not found — skipping email",
                    order.user_id,
                )
                return

            email_kwargs = dict(
                to_email=user.email,
                to_name=user.name,
                credits_granted=order.credits_to_grant // 100,
                amount_inr=order.amount_paise / 100.0,
                order_id=order.id,
            )

            if background_tasks is not None:
                background_tasks.add_task(send_payment_receipt_email, **email_kwargs)
                logger.info(
                    "Receipt email queued (BackgroundTask): user_id=%s order_id=%s",
                    order.user_id, order.id,
                )
            else:
                send_payment_receipt_email(**email_kwargs)
                logger.info(
                    "Receipt email sent (sync): user_id=%s order_id=%s",
                    order.user_id, order.id,
                )

        except Exception as exc:
            logger.warning(
                "Receipt email failed (non-fatal): order_id=%s error=%s",
                order.id, exc,
            )

    def _handle_payment_failed(self, payload: dict) -> dict:
        """Process payment.failed webhook event."""
        payment_entity    = payload.get("payload", {}).get("payment", {}).get("entity", {})
        razorpay_order_id = payment_entity.get("order_id")
        error_description = (
            payment_entity.get("error_description")
            or payment_entity.get("error_reason")
            or "Payment failed"
        )

        if not razorpay_order_id:
            return {"processed": True, "action": "skipped_missing_order_id"}

        order = (
            self.db.query(PaymentOrder)
            .filter_by(razorpay_order_id=razorpay_order_id)
            .first()
        )
        if not order:
            return {"processed": True, "action": "order_not_found"}

        if order.status == PaymentOrderStatus.SETTLED:
            logger.warning(
                "payment.failed received for already SETTLED order_id=%s — ignoring",
                order.id,
            )
            return {"processed": True, "action": "settled_order_unchanged"}

        order.status         = PaymentOrderStatus.FAILED
        order.failure_reason = error_description[:500]

        logger.info("Payment failed: order_id=%s reason=%s", order.id, error_description)
        return {"processed": True, "action": "order_marked_failed"}

    def _handle_refund_created(self, payload: dict) -> dict:
        """Process refund.created webhook event (informational logging)."""
        refund_entity = payload.get("payload", {}).get("refund", {}).get("entity", {})
        refund_id     = refund_entity.get("id", "unknown")
        amount        = refund_entity.get("amount", 0)
        payment_id    = refund_entity.get("payment_id", "unknown")

        logger.info(
            "Refund created: refund_id=%s amount_paise=%s payment_id=%s",
            refund_id, amount, payment_id,
        )
        return {"processed": True, "action": "refund_acknowledged"}

    def _grant_credits_for_order(self, order: PaymentOrder) -> None:
        """Grant credits to user for a settled payment order."""
        wallet_service  = WalletService(self.db)
        idempotency_key = f"payment:{order.razorpay_payment_id or order.id}"

        try:
            wallet_service.grant_credits(
                user_id=order.user_id,
                amount_microcredits=order.credits_to_grant,
                entry_type=LedgerEntryType.PURCHASE,
                idempotency_key=idempotency_key,
                description=(
                    f"Credit purchase — "
                    f"{order.credits_to_grant // 100} credits "
                    f"(order {order.razorpay_order_id})"
                ),
                payment_order_id=str(order.id),
            )
            logger.info(
                "Credits granted: user_id=%s credits=%s order_id=%s",
                order.user_id, order.credits_to_grant // 100, order.id,
            )
        except Exception as exc:
            logger.error(
                "CREDIT GRANT FAILED — REQUIRES MANUAL RECONCILIATION: "
                "order_id=%s user_id=%s credits=%s error=%s\n%s",
                order.id, order.user_id, order.credits_to_grant // 100,
                exc, traceback.format_exc(),
            )

    # ── Status Polling ────────────────────────────────────────────────────────

    def get_order_status(self, razorpay_order_id: str, user_id: int) -> PaymentOrder:
        """Retrieve order status for polling. Raises PaymentNotFoundError on user_id mismatch."""
        order = (
            self.db.query(PaymentOrder)
            .filter_by(razorpay_order_id=razorpay_order_id)
            .first()
        )
        if not order or order.user_id != user_id:
            raise PaymentNotFoundError(razorpay_order_id)
        return order