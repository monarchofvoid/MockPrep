"""
VYAS v2.0 — Payment Webhook Integration Tests
==============================================
Tests the most critical financial flow: Razorpay webhook → credit grant.

These test the complete server path, not mocked services.
Requires: TEST_DATABASE_URL, RAZORPAY_WEBHOOK_SECRET set.

Run:
    pytest tests/test_payment_webhook.py -v
"""

import hashlib
import hmac
import json
import uuid
import pytest

from models.payment import PaymentOrder, PaymentOrderStatus as PaymentStatus, CreditPlan
from models.wallet import CreditLedger


WEBHOOK_SECRET = "test_webhook_secret_for_tests_only"


@pytest.fixture(autouse=True)
def patch_webhook_secret(monkeypatch):
    """Ensure tests use the test webhook secret."""
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)


def _make_webhook_signature(payload: dict, secret: str) -> str:
    """Reproduce the HMAC-SHA256 Razorpay uses for webhook signatures."""
    body = json.dumps(payload, separators=(',', ':')).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _make_payment_captured_event(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    amount_paise: int,
) -> dict:
    """Build a synthetic Razorpay payment.captured webhook payload."""
    return {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": razorpay_payment_id,
                    "order_id": razorpay_order_id,
                    "amount": amount_paise,
                    "status": "captured",
                }
            }
        }
    }


class TestWebhookSignatureVerification:

    def test_valid_signature_accepted(self, client, db, make_user, make_credit_plan):
        """Webhook with correct HMAC signature should return 200."""
        user = make_user(wallet_microcredits=0)
        plan = make_credit_plan(amount_paise=9900, credits_granted=10)

        # Create a payment order directly in DB (simulating /create-order call)
        rzp_order_id = f"order_{uuid.uuid4().hex[:16]}"
        rzp_payment_id = f"pay_{uuid.uuid4().hex[:16]}"
        order = PaymentOrder(
            id=str(uuid.uuid4()),
            user_id=user.id,
            plan_id=plan.id,
            razorpay_order_id=rzp_order_id,
            amount_paise=9900,
            credits_to_grant=10,
            status=PaymentStatus.INITIATED,
        )
        db.add(order)
        db.flush()

        payload = _make_payment_captured_event(rzp_order_id, rzp_payment_id, 9900)
        sig = _make_webhook_signature(payload, WEBHOOK_SECRET)

        resp = client.post(
            "/api/v1/payments/webhook",
            json=payload,
            headers={"x-razorpay-signature": sig},
        )
        assert resp.status_code == 200

    def test_invalid_signature_rejected(self, client, db, make_user, make_credit_plan):
        """Webhook with wrong signature must return 400."""
        payload = _make_payment_captured_event("order_fake", "pay_fake", 9900)
        resp = client.post(
            "/api/v1/payments/webhook",
            json=payload,
            headers={"x-razorpay-signature": "wrong_signature_entirely"},
        )
        assert resp.status_code == 400

    def test_missing_signature_header_rejected(self, client):
        """Webhook without signature header must return 400."""
        payload = _make_payment_captured_event("order_fake", "pay_fake", 9900)
        resp = client.post("/api/v1/payments/webhook", json=payload)
        assert resp.status_code == 400


class TestWebhookCreditGrant:

    def test_credits_granted_after_valid_webhook(self, client, db, make_user, make_credit_plan):
        """After a valid payment.captured webhook, user wallet should be credited."""
        user = make_user(wallet_microcredits=0)
        plan = make_credit_plan(amount_paise=4900, credits_granted=5)

        rzp_order_id = f"order_{uuid.uuid4().hex[:16]}"
        rzp_payment_id = f"pay_{uuid.uuid4().hex[:16]}"
        order = PaymentOrder(
            id=str(uuid.uuid4()),
            user_id=user.id,
            plan_id=plan.id,
            razorpay_order_id=rzp_order_id,
            amount_paise=4900,
            credits_to_grant=5,
            status=PaymentStatus.INITIATED,
        )
        db.add(order)
        db.flush()

        from services.wallet_service import WalletService
        balance_before = WalletService(db).get_wallet(user.id).balance_microcredits

        payload = _make_payment_captured_event(rzp_order_id, rzp_payment_id, 4900)
        sig = _make_webhook_signature(payload, WEBHOOK_SECRET)
        resp = client.post(
            "/api/v1/payments/webhook",
            json=payload,
            headers={"x-razorpay-signature": sig},
        )

        assert resp.status_code == 200

        db.expire_all()
        balance_after = WalletService(db).get_wallet(user.id).balance_microcredits
        # 5 credits = 500 microcredits granted
        assert balance_after == balance_before + 500

    def test_webhook_idempotency_no_double_credit(self, client, db, make_user, make_credit_plan):
        """
        Sending the same webhook twice (Razorpay retries on timeout) must NOT
        double-credit the user. The DB UNIQUE constraint on event_id enforces this.
        """
        user = make_user(wallet_microcredits=0)
        plan = make_credit_plan(amount_paise=4900, credits_granted=5)

        rzp_order_id = f"order_{uuid.uuid4().hex[:16]}"
        rzp_payment_id = f"pay_{uuid.uuid4().hex[:16]}"
        order = PaymentOrder(
            id=str(uuid.uuid4()),
            user_id=user.id,
            plan_id=plan.id,
            razorpay_order_id=rzp_order_id,
            amount_paise=4900,
            credits_to_grant=5,
            status=PaymentStatus.INITIATED,
        )
        db.add(order)
        db.flush()

        payload = _make_payment_captured_event(rzp_order_id, rzp_payment_id, 4900)
        sig = _make_webhook_signature(payload, WEBHOOK_SECRET)

        # First webhook
        resp1 = client.post(
            "/api/v1/payments/webhook",
            json=payload,
            headers={"x-razorpay-signature": sig},
        )
        assert resp1.status_code == 200

        db.expire_all()
        balance_after_first = WalletService(db).get_wallet(user.id).balance_microcredits

        # Second webhook (duplicate delivery)
        resp2 = client.post(
            "/api/v1/payments/webhook",
            json=payload,
            headers={"x-razorpay-signature": sig},
        )
        # Should be 200 (idempotent, not an error) or 409 (already processed)
        assert resp2.status_code in (200, 409)

        db.expire_all()
        balance_after_second = WalletService(db).get_wallet(user.id).balance_microcredits

        # Balance must NOT have increased again
        assert balance_after_second == balance_after_first, (
            f"Double credit detected! "
            f"Balance increased from {balance_after_first} to {balance_after_second} "
            f"after duplicate webhook."
        )

    def test_amount_mismatch_no_credits(self, client, db, make_user, make_credit_plan):
        """
        Webhook with amount != expected amount (fraud attempt) must NOT grant credits.
        This is a critical financial security check.
        """
        user = make_user(wallet_microcredits=0)
        plan = make_credit_plan(amount_paise=9900, credits_granted=10)

        rzp_order_id = f"order_{uuid.uuid4().hex[:16]}"
        rzp_payment_id = f"pay_{uuid.uuid4().hex[:16]}"
        order = PaymentOrder(
            id=str(uuid.uuid4()),
            user_id=user.id,
            plan_id=plan.id,
            razorpay_order_id=rzp_order_id,
            amount_paise=9900,  # expected: ₹99
            credits_to_grant=10,
            status=PaymentStatus.INITIATED,
        )
        db.add(order)
        db.flush()

        from services.wallet_service import WalletService
        balance_before = WalletService(db).get_wallet(user.id).balance_microcredits

        # Tampered payload: amount is ₹1 instead of ₹99
        payload = _make_payment_captured_event(rzp_order_id, rzp_payment_id, 100)
        sig = _make_webhook_signature(payload, WEBHOOK_SECRET)

        resp = client.post(
            "/api/v1/payments/webhook",
            json=payload,
            headers={"x-razorpay-signature": sig},
        )

        # Should reject or process without granting credits
        db.expire_all()
        balance_after = WalletService(db).get_wallet(user.id).balance_microcredits
        assert balance_after == balance_before, (
            "Amount mismatch webhook resulted in credit grant — CRITICAL SECURITY BUG"
        )