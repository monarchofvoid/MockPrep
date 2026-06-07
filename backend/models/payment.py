"""
VYAS v2.0 — Payment Models
=============================
Razorpay integration models with ACID guarantees.

Models:
  CreditPlan         — available purchase tiers (seeded, admin-configurable)
  PaymentOrder       — tracks each Razorpay order lifecycle
  PaymentWebhookLog  — idempotent webhook event deduplication table

Security principles:
  - PaymentOrder.amount_paise must match Razorpay webhook amount (fraud check)
  - PaymentWebhookLog.razorpay_event_id is UNIQUE (webhook idempotency)
  - Order status transitions are one-directional (created → initiated → settled)
  - Credits are ONLY granted via the webhook handler, never client-side
"""

import enum

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum as SAEnum,
    ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.base import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class PaymentOrderStatus(str, enum.Enum):
    CREATED   = "created"    # Order created, not yet paid
    INITIATED = "initiated"  # Payment initiated (Razorpay checkout opened)
    VERIFIED  = "verified"   # Client-side signature verified (DO NOT grant credits yet)
    SETTLED   = "settled"    # Webhook confirmed — credits granted (FINAL)
    FAILED    = "failed"     # Payment failed or expired
    REFUNDED  = "refunded"   # Razorpay refunded the payment


# ── Credit Plans ──────────────────────────────────────────────────────────────

class CreditPlan(Base):
    """
    Available credit purchase tiers.
    Seeded in the database, admin-configurable via admin panel.

    All amounts in integer paise (1 INR = 100 paise) to avoid float issues.
    credits_granted in actual credits (not microcredits) for display simplicity.
    The wallet receives credits * MICROCREDITS_PER_CREDIT microcredits.

    Example:
      Plan: "Starter" — ₹99 for 25 credits
      amount_paise = 9900
      credits_granted = 25
      → wallet receives 25 * 100 = 2500 microcredits
    """
    __tablename__ = "credit_plans"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(50), nullable=False)          # "Starter", "Popular", etc.
    description     = Column(String(200), nullable=True)
    amount_paise    = Column(Integer, nullable=False)             # price in paise
    credits_granted = Column(Integer, nullable=False)             # number of credits
    is_active       = Column(Boolean, default=True, nullable=False)
    is_popular      = Column(Boolean, default=False, nullable=False)  # UI highlight
    sort_order      = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def amount_inr(self) -> float:
        """Display price in INR. Display layer only."""
        return self.amount_paise / 100.0

    @property
    def microcredits_to_grant(self) -> int:
        """Microcredits to add to wallet. This is what gets stored."""
        return self.credits_granted * 100  # 1 credit = 100 microcredits


# ── Payment Orders ────────────────────────────────────────────────────────────

class PaymentOrder(Base):
    """
    Tracks each Razorpay payment order from creation to settlement.

    Lifecycle:
      1. POST /payments/create-order → status=CREATED
      2. User opens Razorpay checkout → status=INITIATED (optional)
      3. Client POSTs /payments/verify (signature check) → status=VERIFIED
      4. Razorpay sends webhook payment.captured → status=SETTLED + credits granted
         OR webhook payment.failed → status=FAILED

    Security: credits are ONLY granted in step 4 via the authenticated webhook.
    Client-side signature verification (step 3) updates status but grants NO credits.

    Idempotency: the webhook handler checks order.status == SETTLED before granting
    credits. Safe to receive the same webhook multiple times.
    """
    __tablename__ = "payment_orders"
    __table_args__ = (
        UniqueConstraint("razorpay_order_id", name="uq_payment_orders_rzp_order_id"),
        Index("ix_payment_orders_user_id", "user_id"),
        Index("ix_payment_orders_status", "status"),
        Index("ix_payment_orders_created_at", "created_at"),
    )

    id                  = Column(String(36), primary_key=True)  # UUID
    user_id             = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_id             = Column(Integer, ForeignKey("credit_plans.id"), nullable=False)

    # Razorpay identifiers
    razorpay_order_id   = Column(String(50), unique=True, nullable=False)
    razorpay_payment_id = Column(String(50), nullable=True)  # Set on capture

    # Amount must be server-verified against Razorpay webhook (fraud prevention)
    amount_paise        = Column(Integer, nullable=False)
    currency            = Column(String(3), default="INR", nullable=False)
    credits_to_grant    = Column(Integer, nullable=False)  # microcredits

    status = Column(
        SAEnum(PaymentOrderStatus),
        default=PaymentOrderStatus.CREATED,
        nullable=False,
    )

    # Timestamps
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    initiated_at = Column(DateTime(timezone=True), nullable=True)
    verified_at  = Column(DateTime(timezone=True), nullable=True)
    captured_at  = Column(DateTime(timezone=True), nullable=True)
    settled_at   = Column(DateTime(timezone=True), nullable=True)
    failed_at    = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    failure_reason  = Column(String(300), nullable=True)
    razorpay_notes  = Column(Text, nullable=True)  # JSON

    # Relationships
    user = relationship("User", back_populates="payment_orders")
    plan = relationship("CreditPlan")


# ── Payment Webhook Log ───────────────────────────────────────────────────────

class PaymentWebhookLog(Base):
    """
    Idempotent webhook event log.

    Every Razorpay webhook is stored here with its event_id.
    The UNIQUE constraint on razorpay_event_id is the primary
    idempotency mechanism — a second INSERT with the same event_id
    raises IntegrityError, which the handler catches to skip processing.

    This table also serves as a complete audit trail of all payment events.
    """
    __tablename__ = "payment_webhook_logs"
    __table_args__ = (
        UniqueConstraint("razorpay_event_id", name="uq_webhook_logs_event_id"),
        Index("ix_webhook_logs_event_type", "event_type"),
        Index("ix_webhook_logs_created_at", "created_at"),
        Index("ix_webhook_logs_order_id", "razorpay_order_id"),
    )

    id                 = Column(Integer, primary_key=True, index=True)
    razorpay_event_id  = Column(String(50), unique=True, nullable=False)
    event_type         = Column(String(50), nullable=False)  # "payment.captured", etc.
    razorpay_order_id  = Column(String(50), nullable=True)
    razorpay_payment_id = Column(String(50), nullable=True)
    amount_paise       = Column(Integer, nullable=True)

    # Full webhook payload (JSON) for debugging
    raw_payload        = Column(Text, nullable=False)
    processed          = Column(Boolean, default=True, nullable=False)
    processing_error   = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ── Backward-compat aliases ───────────────────────────────────────────────────
# payment_service.py imports WebhookEvent but the class was renamed
# PaymentWebhookLog during the v2.0 security overhaul.
WebhookEvent = PaymentWebhookLog