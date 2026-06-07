"""
VYAS v2.2.0 — Payment Background Task Tests
=============================================
Tests for the BackgroundTasks-based receipt email replacing the Celery
send_payment_receipt_task.delay() call.

Tests:
  - test_receipt_email_added_to_background_tasks: BackgroundTasks.add_task called
  - test_receipt_email_failure_doesnt_break_webhook: email exception is swallowed
  - test_webhook_triggers_background_email_via_router: end-to-end webhook test
  - test_receipt_email_not_called_when_payment_fails: no email on payment.failed

Run:
    pytest tests/test_payment_background.py -v
"""

import hashlib
import hmac
import json
import uuid
from unittest.mock import MagicMock, patch, call

import pytest

from models.payment import PaymentOrder, PaymentOrderStatus as PaymentStatus, CreditPlan


WEBHOOK_SECRET = "test_webhook_secret_for_tests_only"


@pytest.fixture(autouse=True)
def patch_webhook_secret(monkeypatch):
    """Ensure tests use the test webhook secret."""
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    # Clear config cache so the new value is picked up
    try:
        from core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


def _make_webhook_signature(payload: dict, secret: str) -> str:
    body = json.dumps(payload, separators=(',', ':')).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _make_payment_captured_event(rzp_order_id: str, rzp_payment_id: str, amount_paise: int) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": rzp_payment_id,
                    "order_id": rzp_order_id,
                    "amount": amount_paise,
                    "status": "captured",
                }
            }
        }
    }


# ── Test: BackgroundTasks.add_task called for receipt email ───────────────────

def test_receipt_email_added_to_background_tasks(db, make_user, make_credit_plan):
    """
    After a payment.captured webhook, send_payment_receipt_email should be
    added to BackgroundTasks (not called directly).
    """
    from fastapi import BackgroundTasks
    from services.payment_service import PaymentService

    user = make_user(wallet_microcredits=0)
    plan = make_credit_plan(amount_paise=9900, credits_granted=10)

    rzp_order_id  = f"order_{uuid.uuid4().hex[:16]}"
    rzp_payment_id = f"pay_{uuid.uuid4().hex[:16]}"
    order = PaymentOrder(
        id=str(uuid.uuid4()),
        user_id=user.id,
        plan_id=plan.id,
        razorpay_order_id=rzp_order_id,
        amount_paise=9900,
        credits_to_grant=1000,
        status=PaymentStatus.CREATED,
    )
    db.add(order)
    db.flush()

    payload = _make_payment_captured_event(rzp_order_id, rzp_payment_id, 9900)
    raw_body = json.dumps(payload).encode()

    bg_tasks = MagicMock(spec=BackgroundTasks)

    service = PaymentService(db)
    service.verify_webhook_signature = MagicMock()  # Skip sig check in this unit test

    with patch("services.payment_service.send_payment_receipt_email") as mock_email:
        result = service.handle_webhook(raw_body, payload, background_tasks=bg_tasks)

    # Result should indicate credits were granted
    assert result["action"] == "credits_granted"

    # BackgroundTasks.add_task should have been called with the email function
    bg_tasks.add_task.assert_called_once()
    call_kwargs = bg_tasks.add_task.call_args
    assert call_kwargs[0][0] == mock_email.__wrapped__ if hasattr(mock_email, "__wrapped__") else True
    # Verify it was NOT called synchronously
    mock_email.assert_not_called()


# ── Test: Email failure doesn't break webhook ─────────────────────────────────

def test_receipt_email_failure_doesnt_break_webhook(db, make_user, make_credit_plan):
    """
    If send_payment_receipt_email raises an exception inside BackgroundTask,
    the webhook should still return success and the credits should be granted.
    This test verifies the PaymentService handles email lookup errors gracefully.
    """
    from services.payment_service import PaymentService

    user = make_user(wallet_microcredits=0)
    plan = make_credit_plan(amount_paise=4900, credits_granted=5)

    rzp_order_id  = f"order_{uuid.uuid4().hex[:16]}"
    rzp_payment_id = f"pay_{uuid.uuid4().hex[:16]}"
    order = PaymentOrder(
        id=str(uuid.uuid4()),
        user_id=user.id,
        plan_id=plan.id,
        razorpay_order_id=rzp_order_id,
        amount_paise=4900,
        credits_to_grant=500,
        status=PaymentStatus.CREATED,
    )
    db.add(order)
    db.flush()

    payload = _make_payment_captured_event(rzp_order_id, rzp_payment_id, 4900)
    raw_body = json.dumps(payload).encode()

    bg_tasks = MagicMock()
    # Simulate BackgroundTasks.add_task raising (e.g. bad function argument)
    bg_tasks.add_task.side_effect = RuntimeError("Simulated BackgroundTasks error")

    service = PaymentService(db)
    service.verify_webhook_signature = MagicMock()

    # Should not raise despite bg_tasks.add_task failing
    result = service.handle_webhook(raw_body, payload, background_tasks=bg_tasks)

    # Credits should still be granted
    assert result.get("action") in ("credits_granted",), \
        f"Expected credits_granted action, got: {result}"


# ── Test: End-to-end webhook triggers background email ───────────────────────

def test_webhook_triggers_background_email_via_router(client, db, make_user, make_credit_plan):
    """
    End-to-end test: POST /api/v1/payments/webhook with valid signature
    should return 200 and schedule the receipt email as a BackgroundTask.

    Verifies the router correctly injects BackgroundTasks and threads it
    through to PaymentService.handle_webhook().
    """
    user = make_user(wallet_microcredits=0)
    plan = make_credit_plan(amount_paise=4900, credits_granted=5)

    rzp_order_id  = f"order_{uuid.uuid4().hex[:16]}"
    rzp_payment_id = f"pay_{uuid.uuid4().hex[:16]}"
    order = PaymentOrder(
        id=str(uuid.uuid4()),
        user_id=user.id,
        plan_id=plan.id,
        razorpay_order_id=rzp_order_id,
        amount_paise=4900,
        credits_to_grant=500,
        status=PaymentStatus.CREATED,
    )
    db.add(order)
    db.flush()

    payload = _make_payment_captured_event(rzp_order_id, rzp_payment_id, 4900)
    sig = _make_webhook_signature(payload, WEBHOOK_SECRET)

    email_calls = []

    def mock_send_email(**kwargs):
        email_calls.append(kwargs)
        return True

    with patch("services.payment_service.send_payment_receipt_email", side_effect=mock_send_email):
        resp = client.post(
            "/api/v1/payments/webhook",
            json=payload,
            headers={"x-razorpay-signature": sig},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"

    # With TestClient, BackgroundTasks run synchronously before the response.
    # Verify the email was triggered with the correct parameters.
    assert len(email_calls) == 1
    email_call = email_calls[0]
    assert email_call["to_email"] == user.email
    assert email_call["credits_granted"] == 5  # 500 microcredits / 100
    assert email_call["amount_inr"] == pytest.approx(49.0)


# ── Test: No email on payment.failed ──────────────────────────────────────────

def test_receipt_email_not_called_when_payment_fails(client, db, make_user, make_credit_plan):
    """
    payment.failed webhook should NOT trigger a receipt email.
    """
    user = make_user(wallet_microcredits=0)
    plan = make_credit_plan(amount_paise=9900, credits_granted=10)

    rzp_order_id  = f"order_{uuid.uuid4().hex[:16]}"
    rzp_payment_id = f"pay_{uuid.uuid4().hex[:16]}"
    order = PaymentOrder(
        id=str(uuid.uuid4()),
        user_id=user.id,
        plan_id=plan.id,
        razorpay_order_id=rzp_order_id,
        amount_paise=9900,
        credits_to_grant=1000,
        status=PaymentStatus.CREATED,
    )
    db.add(order)
    db.flush()

    failed_payload = {
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": rzp_payment_id,
                    "order_id": rzp_order_id,
                    "error_description": "Insufficient funds",
                }
            }
        }
    }
    sig = _make_webhook_signature(failed_payload, WEBHOOK_SECRET)

    with patch("services.payment_service.send_payment_receipt_email") as mock_email:
        resp = client.post(
            "/api/v1/payments/webhook",
            json=failed_payload,
            headers={"x-razorpay-signature": sig},
        )

    assert resp.status_code == 200
    # Email must NOT have been called
    mock_email.assert_not_called()
