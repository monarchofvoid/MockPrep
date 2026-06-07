"""
VYAS v2.0 — Wallet & Credit Models
=====================================
Financial-grade design principles:
  1. Ledger is the single source of truth (balance is a materialized view)
  2. Integer microcredits everywhere (no floats in financial calculations)
  3. Immutable ledger entries (corrections via compensating entries)
  4. Pessimistic locking (SELECT FOR UPDATE NOWAIT) on deduction
  5. balance_microcredits CHECK >= 0 prevents going negative

Models:
  Wallet          — per-user credit balance (1 wallet per user)
  CreditLedger    — immutable accounting log (append-only)
  FeaturePricing  — configurable cost per feature (admin-controlled)

BUG FIXES (v2.0.1):
  - Wallet.user_id: changed ondelete from CASCADE → RESTRICT.
    CASCADE means deleting a user silently destroys their entire financial
    history. For a fintech system this is dangerous — a bug in a user
    deletion flow could permanently destroy audit records. RESTRICT forces
    explicit handling of financial data before the user record can be deleted.
    See migration 007_wallet_restrict_delete.py.

  - CreditLedger.payment_order_id: added ForeignKey("payment_orders.id").
    The column previously had a comment saying it "links to PaymentOrder.id"
    but no FK constraint, so referential integrity was not enforced at DB level.
    A ledger entry could reference a non-existent payment order ID.
    See migration 006_fix_credit_ledger_fk.py.
"""

import enum

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum as SAEnum,
    ForeignKey, Index, Integer, String, Text, UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.base import Base


# ── Ledger Entry Types ────────────────────────────────────────────────────────

class LedgerEntryType(str, enum.Enum):
    # Credit additions (positive amount)
    TOPUP_PAYMENT       = "topup_payment"       # User purchased credits
    ADMIN_CREDIT        = "admin_credit"         # Admin manually credited
    PROMOTIONAL         = "promotional"          # Marketing/bonus credits
    REFERRAL_BONUS      = "referral_bonus"       # Referral reward
    SIGNUP_BONUS        = "signup_bonus"         # New user welcome bonus
    REFUND              = "refund"               # Refund after AI failure
    SUBSCRIPTION_CREDIT = "subscription_credit" # Monthly subscription grant

    # Credit deductions (negative amount)
    AI_MOCK_DEDUCTION   = "ai_mock_deduction"   # Mock test generation
    TUTOR_DEDUCTION     = "tutor_deduction"     # VYAS Explain usage
    SUBSCRIPTION_CHARGE = "subscription_charge" # Future subscription

    # Corrections (can be positive or negative)
    ADMIN_DEDUCTION     = "admin_deduction"     # Admin correction
    RECONCILIATION_ADJ  = "reconciliation_adj"  # Balance reconciliation adjustment


# ── Wallet ─────────────────────────────────────────────────────────────────────

class Wallet(Base):
    """
    Per-user credit wallet. One wallet per user (enforced by unique constraint).

    balance_microcredits: current balance (1 credit = 100 microcredits).
    Must always equal SUM(credit_ledger.amount_microcredits WHERE wallet_id=id).

    CHECK constraint prevents balance from going negative at DB level.
    Application-level pessimistic locking prevents race conditions.

    ondelete=RESTRICT: user deletion is blocked while a wallet exists.
    This is intentional — financial records must be explicitly handled
    before a user account can be deleted. Never silently CASCADE financial data.
    """
    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_wallets_user_id"),
        CheckConstraint("balance_microcredits >= 0", name="chk_wallet_balance_non_negative"),
        Index("ix_wallets_user_id", "user_id"),
    )

    id                              = Column(Integer, primary_key=True, index=True)
    # FIX: ondelete changed from CASCADE → RESTRICT.
    # A user with an active wallet cannot be deleted until the wallet is
    # explicitly handled. This prevents accidental financial record destruction.
    user_id                         = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Balance in microcredits (integer — no floats in financial code)
    balance_microcredits            = Column(Integer, nullable=False, default=0)

    # Lifetime totals for analytics/display
    lifetime_earned_microcredits    = Column(BigInteger, nullable=False, default=0)
    lifetime_spent_microcredits     = Column(BigInteger, nullable=False, default=0)

    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user         = relationship("User", back_populates="wallet")
    ledger_entries = relationship(
        "CreditLedger",
        back_populates="wallet",
        order_by="CreditLedger.created_at.desc()",
        cascade="all, delete-orphan",
    )

    @property
    def balance_credits(self) -> float:
        """Display balance in credits (divide by 100). Display-layer use only."""
        return self.balance_microcredits / 100.0

    @property
    def lifetime_earned_credits(self) -> float:
        return self.lifetime_earned_microcredits / 100.0

    @property
    def lifetime_spent_credits(self) -> float:
        return self.lifetime_spent_microcredits / 100.0


# ── Credit Ledger ─────────────────────────────────────────────────────────────

class CreditLedger(Base):
    """
    Immutable financial audit log. Every balance change creates a ledger entry.
    Entries are NEVER updated or deleted. Corrections via compensating entries.

    Invariants:
      1. amount_microcredits > 0 for additions, < 0 for deductions
      2. balance_after_microcredits = previous_balance + amount_microcredits
      3. balance_after_microcredits >= 0 always
      4. idempotency_key is UNIQUE — prevents double-processing

    References: at least ONE of payment_order_id, ai_job_id, or admin_user_id
    must be non-null to trace the source of the credit change.
    """
    __tablename__ = "credit_ledger"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ledger_idempotency_key"),
        CheckConstraint("amount_microcredits != 0", name="chk_ledger_nonzero_amount"),
        Index("ix_ledger_wallet_id", "wallet_id"),
        Index("ix_ledger_created_at", "created_at"),
        Index("ix_ledger_entry_type", "entry_type"),
        Index("ix_ledger_ai_job_id", "ai_job_id"),
        Index("ix_ledger_payment_order_id", "payment_order_id"),
    )

    id              = Column(Integer, primary_key=True, index=True)
    wallet_id       = Column(
        Integer, ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )

    # Signed amount: positive = credit granted, negative = credit deducted
    amount_microcredits         = Column(Integer, nullable=False)

    # Running balance AFTER this entry (snapshot for audit trail)
    balance_after_microcredits  = Column(Integer, nullable=False)

    entry_type      = Column(String(50), nullable=False)  # BUG FIX: was SAEnum(LedgerEntryType) but migration created this as String(50). SAEnum coerces 'signup_bonus' to enum name 'SIGNUP_BONUS', causing LookupError.
    idempotency_key = Column(String(100), nullable=False, unique=True)

    # Description for user-facing transaction history
    description     = Column(String(500), nullable=True)

    # Traceability references (at least one should be set)
    # FIX: payment_order_id now has a proper FK constraint to payment_orders.id.
    # Previously this was a plain String(36) column with a comment saying it
    # "links to PaymentOrder.id" — but no DB-level enforcement existed.
    payment_order_id = Column(
        String(36),
        ForeignKey("payment_orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    ai_job_id        = Column(String(36), nullable=True)   # links to AIJob.id (UUID)
    admin_user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Refund traceability — points back to the deduction entry being refunded
    refund_for_ledger_id = Column(
        Integer, ForeignKey("credit_ledger.id"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    wallet       = relationship("Wallet", back_populates="ledger_entries")
    refund_entry = relationship("CreditLedger", remote_side="CreditLedger.id", foreign_keys=[refund_for_ledger_id])


# ── Feature Pricing ───────────────────────────────────────────────────────────

class FeaturePricing(Base):
    """
    Admin-configurable pricing table. Allows changing feature costs
    without code deployment.

    Pricing is read from DB on startup and cached in Redis for 5 minutes.
    Admin updates invalidate the Redis cache immediately.

    Default feature keys:
      'ai_mock_per_question' — cost per question in AI mock (microcredits)
      'tutor_explain'        — cost per VYAS Explain request (microcredits)
    """
    __tablename__ = "feature_pricing"
    __table_args__ = (
        UniqueConstraint("feature_key", name="uq_feature_pricing_key"),
    )

    id                  = Column(Integer, primary_key=True, index=True)
    feature_key         = Column(String(50), unique=True, nullable=False)
    cost_microcredits   = Column(Integer, nullable=False)
    description         = Column(String(200), nullable=True)
    is_active           = Column(Boolean, default=True, nullable=False)

    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by  = Column(Integer, ForeignKey("users.id"), nullable=True)

# ── Backward-compat alias ─────────────────────────────────────────────────────
# wallet_service.py imports LedgerEntry, but the ORM class is CreditLedger.
# Adding an alias here is the least-invasive fix — no need to rename all
# usages in wallet_service.py (14 occurrences) just to satisfy an import.
LedgerEntry = CreditLedger
