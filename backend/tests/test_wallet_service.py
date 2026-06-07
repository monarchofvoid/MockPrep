"""
VYAS v2.0 — WalletService Unit Tests (v2.0.5)
===============================================
Fixed enum/column names to match actual models:
  - LedgerEntryType.PURCHASE        → TOPUP_PAYMENT
  - LedgerEntryType.ADMIN_GRANT     → ADMIN_CREDIT
  - LedgerEntryType.MOCK_DEDUCTION  → AI_MOCK_DEDUCTION
  - CreditLedger.user_id (no such col) → join via Wallet.user_id
"""

import pytest
from sqlalchemy import func

from models.wallet import CreditLedger, LedgerEntryType, Wallet
from models.user import User
from services.wallet_service import WalletService
from core.exceptions import InsufficientCreditsError, WalletNotFoundError


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def test_user(make_user):
    return make_user(with_wallet=False, wallet_microcredits=0)

@pytest.fixture
def wallet_service(db):
    return WalletService(db)

@pytest.fixture
def user_with_wallet(make_user):
    return make_user(with_wallet=True, wallet_microcredits=1000)


def _ledger_count_for_user(db, user_id: int) -> int:
    """Count ledger entries for a user via the wallet relationship."""
    return (
        db.query(CreditLedger)
        .join(Wallet, Wallet.id == CreditLedger.wallet_id)
        .filter(Wallet.user_id == user_id)
        .count()
    )

def _ledger_sum_for_user(db, user_id: int) -> int:
    """Sum all ledger amounts for a user via the wallet relationship."""
    result = (
        db.query(func.sum(CreditLedger.amount_microcredits))
        .join(Wallet, Wallet.id == CreditLedger.wallet_id)
        .filter(Wallet.user_id == user_id)
        .scalar()
    )
    return result or 0


# ── Tests: Wallet Creation ─────────────────────────────────────────────────────

class TestWalletCreation:

    def test_create_wallet_zero_balance(self, test_user, wallet_service, db):
        wallet = wallet_service.create_wallet(test_user.id)
        db.flush()
        assert wallet.balance_microcredits == 0
        assert wallet.user_id == test_user.id

    def test_get_wallet_returns_created_wallet(self, user_with_wallet, wallet_service):
        wallet = wallet_service.get_wallet(user_with_wallet.id)
        assert wallet is not None
        assert wallet.user_id == user_with_wallet.id

    def test_get_wallet_raises_for_nonexistent_user(self, wallet_service):
        with pytest.raises(WalletNotFoundError):
            wallet_service.get_wallet(user_id=999_999_999)


# ── Tests: Grant Credits ───────────────────────────────────────────────────────

class TestGrantCredits:

    def test_grant_increases_balance(self, user_with_wallet, wallet_service, db):
        before = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits
        wallet_service.grant_credits(
            user_id=user_with_wallet.id,
            amount_microcredits=200,
            entry_type=LedgerEntryType.TOPUP_PAYMENT,
            idempotency_key=f"test_grant_incr:{user_with_wallet.id}:{id(db)}",
            description="Test purchase",
        )
        db.flush()
        after = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits
        assert after == before + 200

    def test_grant_creates_ledger_entry(self, user_with_wallet, wallet_service, db):
        before_count = _ledger_count_for_user(db, user_with_wallet.id)
        wallet_service.grant_credits(
            user_id=user_with_wallet.id,
            amount_microcredits=100,
            entry_type=LedgerEntryType.ADMIN_CREDIT,
            idempotency_key=f"test_grant_ledger:{user_with_wallet.id}:{id(db)}",
            description="Admin test grant",
        )
        db.flush()
        after_count = _ledger_count_for_user(db, user_with_wallet.id)
        assert after_count == before_count + 1

    def test_grant_idempotency_prevents_duplicate(self, user_with_wallet, wallet_service, db):
        key = f"idem_grant:{user_with_wallet.id}:{id(db)}"
        wallet_service.grant_credits(
            user_id=user_with_wallet.id,
            amount_microcredits=500,
            entry_type=LedgerEntryType.TOPUP_PAYMENT,
            idempotency_key=key,
            description="First grant",
        )
        db.flush()
        balance_after_first = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits

        wallet_service.grant_credits(
            user_id=user_with_wallet.id,
            amount_microcredits=500,
            entry_type=LedgerEntryType.TOPUP_PAYMENT,
            idempotency_key=key,
            description="Duplicate — should be ignored",
        )
        db.flush()
        balance_after_second = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits
        assert balance_after_first == balance_after_second


# ── Tests: Deduct Credits ──────────────────────────────────────────────────────

class TestDeductCredits:

    def test_deduct_decreases_balance(self, user_with_wallet, wallet_service, db):
        before = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits
        wallet_service.deduct_credits(
            user_id=user_with_wallet.id,
            cost_microcredits=150,
            entry_type=LedgerEntryType.AI_MOCK_DEDUCTION,
            idempotency_key=f"test_deduct:{user_with_wallet.id}:{id(db)}",
            description="Test deduction",
        )
        db.flush()
        after = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits
        assert after == before - 150

    def test_deduct_raises_insufficient_credits(self, user_with_wallet, wallet_service):
        wallet = wallet_service.get_wallet(user_with_wallet.id)
        too_much = wallet.balance_microcredits + 1
        with pytest.raises(InsufficientCreditsError):
            wallet_service.deduct_credits(
                user_id=user_with_wallet.id,
                cost_microcredits=too_much,
                entry_type=LedgerEntryType.AI_MOCK_DEDUCTION,
                idempotency_key=f"test_overdraft:{user_with_wallet.id}:{id(db)}",
                description="Should fail",
            )

    def test_deduct_idempotency_returns_existing_entry(self, user_with_wallet, wallet_service, db):
        key = f"idem_deduct:{user_with_wallet.id}:{id(db)}"
        entry1 = wallet_service.deduct_credits(
            user_id=user_with_wallet.id,
            cost_microcredits=50,
            entry_type=LedgerEntryType.TUTOR_DEDUCTION,
            idempotency_key=key,
            description="First deduction",
        )
        db.flush()
        balance_after_first = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits

        entry2 = wallet_service.deduct_credits(
            user_id=user_with_wallet.id,
            cost_microcredits=50,
            entry_type=LedgerEntryType.TUTOR_DEDUCTION,
            idempotency_key=key,
            description="Duplicate",
        )
        db.flush()
        balance_after_second = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits

        assert balance_after_first == balance_after_second
        assert entry1.id == entry2.id

    def test_deduct_creates_negative_ledger_entry(self, user_with_wallet, wallet_service, db):
        key = f"test_neg_entry:{user_with_wallet.id}:{id(db)}"
        wallet_service.deduct_credits(
            user_id=user_with_wallet.id,
            cost_microcredits=75,
            entry_type=LedgerEntryType.AI_MOCK_DEDUCTION,
            idempotency_key=key,
            description="Ledger sign test",
        )
        db.flush()
        entry = db.query(CreditLedger).filter_by(idempotency_key=key).first()
        assert entry is not None
        assert entry.amount_microcredits == -75


# ── Tests: Refund ──────────────────────────────────────────────────────────────

class TestRefundCredits:

    def test_refund_restores_balance(self, user_with_wallet, wallet_service, db):
        key = f"test_refund_base:{user_with_wallet.id}:{id(db)}"
        wallet_service.deduct_credits(
            user_id=user_with_wallet.id,
            cost_microcredits=200,
            entry_type=LedgerEntryType.AI_MOCK_DEDUCTION,
            idempotency_key=key,
            description="To be refunded",
        )
        db.flush()
        after_deduct = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits

        wallet_service.refund_credits(
            user_id=user_with_wallet.id,
            amount_microcredits=200,
            original_idempotency_key=key,
            description="Refund",
        )
        db.flush()
        after_refund = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits
        assert after_refund == after_deduct + 200

    def test_refund_is_idempotent_no_double_refund(self, user_with_wallet, wallet_service, db):
        from core.exceptions import DuplicateRefundError
        key = f"test_dup_refund:{user_with_wallet.id}:{id(db)}"
        wallet_service.deduct_credits(
            user_id=user_with_wallet.id,
            cost_microcredits=100,
            entry_type=LedgerEntryType.AI_MOCK_DEDUCTION,
            idempotency_key=key,
            description="Original",
        )
        db.flush()

        wallet_service.refund_credits(
            user_id=user_with_wallet.id,
            amount_microcredits=100,
            original_idempotency_key=key,
            description="First refund",
        )
        db.flush()
        balance_after_first = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits

        with pytest.raises(DuplicateRefundError):
            wallet_service.refund_credits(
                user_id=user_with_wallet.id,
                amount_microcredits=100,
                original_idempotency_key=key,
                description="Second refund — must fail",
            )

        balance_unchanged = wallet_service.get_wallet(user_with_wallet.id).balance_microcredits
        assert balance_unchanged == balance_after_first


# ── Tests: Financial Invariant ─────────────────────────────────────────────────

class TestReconciliation:

    def test_balance_equals_sum_of_ledger_entries(self, user_with_wallet, wallet_service, db):
        """wallet.balance_microcredits MUST equal SUM(ledger.amount_microcredits)."""
        wallet_service.grant_credits(
            user_id=user_with_wallet.id,
            amount_microcredits=300,
            entry_type=LedgerEntryType.TOPUP_PAYMENT,
            idempotency_key=f"reconcile_grant:{user_with_wallet.id}:{id(db)}",
            description="Reconcile test",
        )
        wallet_service.deduct_credits(
            user_id=user_with_wallet.id,
            cost_microcredits=120,
            entry_type=LedgerEntryType.AI_MOCK_DEDUCTION,
            idempotency_key=f"reconcile_deduct:{user_with_wallet.id}:{id(db)}",
            description="Reconcile test",
        )
        db.flush()

        wallet = wallet_service.get_wallet(user_with_wallet.id)
        ledger_sum = _ledger_sum_for_user(db, user_with_wallet.id)

        assert wallet.balance_microcredits == ledger_sum, (
            f"Financial invariant violated: "
            f"wallet={wallet.balance_microcredits} != ledger_sum={ledger_sum}"
        )