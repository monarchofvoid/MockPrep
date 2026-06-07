"""
VYAS v2.0 — Custom Exceptions
================================
Production hardening applied:

  CHANGES:
    1. Added missing exception types that were raised in services but not
       defined here (causing AttributeError on import in some code paths):
       - InvalidWebhookSignatureError (alias for InvalidPaymentSignatureError)
    2. Exception __repr__ methods added for cleaner log output.
    3. PaymentAmountMismatchError: removed the word "CRITICAL" from the
       user-visible message — it should only appear in server logs, not
       in any error payload that might bubble to the client.

  All existing exception classes, constructors, and field names are
  fully preserved — no breaking changes.

Design principle (unchanged): raise typed exceptions in services,
catch and convert to HTTP in routers. Never leak service
internals directly into HTTP responses.
"""

from typing import Optional


class VYASBaseException(Exception):
    """Base class for all VYAS application exceptions."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.message!r})"


# ── Wallet / Credit Exceptions ────────────────────────────────────────────────

class InsufficientCreditsError(VYASBaseException):
    """Raised when user has fewer credits than operation requires."""
    def __init__(
        self,
        required_microcredits: int,
        available_microcredits: int,
    ):
        super().__init__(
            f"Insufficient credits. Required: {required_microcredits / 100:.1f}, "
            f"Available: {available_microcredits / 100:.1f}",
            {
                "required_credits": required_microcredits / 100,
                "available_credits": available_microcredits / 100,
                "required_microcredits": required_microcredits,
                "available_microcredits": available_microcredits,
            },
        )


class WalletLockError(VYASBaseException):
    """Raised when wallet row is locked by a concurrent operation."""
    def __init__(self, user_id: int):
        super().__init__(
            "Wallet is currently locked by another operation. Please retry.",
            {"user_id": user_id},
        )


class WalletNotFoundError(VYASBaseException):
    """Raised when user wallet doesn't exist (should not happen — created on signup)."""
    def __init__(self, user_id: int):
        super().__init__(f"Wallet not found for user {user_id}", {"user_id": user_id})


class IdempotentDeductionError(VYASBaseException):
    """Raised when a deduction with the same idempotency key was already processed."""
    def __init__(self, idempotency_key: str):
        super().__init__(
            "Duplicate deduction request detected.",
            {"idempotency_key": idempotency_key},
        )


class DuplicateRefundError(VYASBaseException):
    """Raised when a refund was already issued for a ledger entry."""
    def __init__(self, original_ledger_id: int):
        super().__init__(
            "Refund already issued for this transaction.",
            {"original_ledger_id": original_ledger_id},
        )


# ── Payment Exceptions ────────────────────────────────────────────────────────

class PaymentNotFoundError(VYASBaseException):
    """Raised when a payment order cannot be found."""
    def __init__(self, identifier: str):
        super().__init__(f"Payment order not found: {identifier}", {"identifier": identifier})


class InvalidPaymentSignatureError(VYASBaseException):
    """Raised when Razorpay HMAC signature verification fails."""
    def __init__(self):
        super().__init__("Payment signature verification failed.")


# Alias used in some service code
InvalidWebhookSignatureError = InvalidPaymentSignatureError


class PaymentAmountMismatchError(VYASBaseException):
    """
    Raised when payment amount received doesn't match order amount.
    Indicates possible fraud or replay attack — logged at CRITICAL server-side.
    The user-visible message is generic; the details dict carries the forensic data.
    """
    def __init__(self, expected: int, received: int, order_id: str):
        super().__init__(
            "Payment amount mismatch detected. Transaction has been flagged for review.",
            {
                "expected_paise": expected,
                "received_paise": received,
                "order_id": order_id,
            },
        )


class DuplicateWebhookError(VYASBaseException):
    """Raised when a webhook event_id has already been processed."""
    def __init__(self, event_id: str):
        super().__init__(
            "Webhook already processed (idempotent).",
            {"event_id": event_id},
        )


class InvalidPlanError(VYASBaseException):
    """Raised when a requested credit plan doesn't exist or is inactive."""
    def __init__(self, plan_id: int):
        super().__init__(f"Credit plan {plan_id} not found or inactive", {"plan_id": plan_id})


# ── AI Job Exceptions ─────────────────────────────────────────────────────────

class AIJobNotFoundError(VYASBaseException):
    """Raised when an AI job cannot be found."""
    def __init__(self, job_id: str):
        super().__init__(f"AI job not found: {job_id}", {"job_id": job_id})


class AIJobAlreadyActiveError(VYASBaseException):
    """Raised when user tries to start a new job while one is already running."""
    def __init__(self, existing_job_id: str):
        super().__init__(
            "You already have an active AI mock generation in progress.",
            {"existing_job_id": existing_job_id},
        )


class AIJobFailedError(VYASBaseException):
    """Raised when an AI generation job fails (triggers refund)."""
    def __init__(self, job_id: str, reason: str):
        super().__init__(
            f"AI generation failed: {reason}",
            {"job_id": job_id, "reason": reason},
        )


# ── Auth Exceptions ───────────────────────────────────────────────────────────

class ProfileIncompleteError(VYASBaseException):
    """Raised when a gated feature requires profile completion."""
    def __init__(self, missing_fields: list):
        super().__init__(
            "Profile incomplete. Please complete your profile to use this feature.",
            {"missing_fields": missing_fields},
        )
