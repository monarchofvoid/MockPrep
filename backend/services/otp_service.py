"""
VYAS v2.1 — OTP Service
==========================
Production hardening applied:

  SECURITY FIXES:
    1. generate_and_store_otp() now uses secrets.randbelow(1_000_000) instead
       of random.randint() — the standard library `random` module is NOT
       cryptographically secure and must never be used for security tokens.
    2. verify_otp() uses hmac.compare_digest() for the hash comparison instead
       of ==. Although the hash itself is not secret, constant-time comparison
       prevents any theoretical timing side-channel.
    3. OTP hash function changed from SHA-1 (used by some implementations) to
       SHA-256. If the existing model stores SHA-256 hashes this is a no-op;
       if it stored SHA-1 hashes, all pending OTPs will be invalidated (they
       expire in 10 minutes anyway — acceptable).
    4. verify_otp() no longer reveals *why* verification failed in its raised
       ValueError ("expired" vs "invalid code") — both cases raise the same
       generic message to prevent oracle attacks.
    5. Resend rate limit now checks resend_count from DB rather than relying on
       a separate Redis counter — simpler, accurate, and works without Redis.
    6. delete_pending() now handles DB errors gracefully and never raises —
       a failure to delete a used OTP record should not crash the signup flow.

  DEFENSIVE PROGRAMMING:
    7. get_pending() catches DB errors and returns None rather than propagating
       a DB exception up through the auth flow.
    8. OTP input is stripped and validated to be exactly 6 digits before any
       DB/hash operation.

  All existing method signatures and rate-limiting behaviour are preserved.
"""

import hashlib
import hmac
import logging
import secrets
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from models.user import PendingOTP

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES  = 10
OTP_MAX_RESENDS     = 3
OTP_RESEND_COOLDOWN = 60   # seconds between resends


class OTPService:
    def __init__(self, db: Session):
        self.db = db

    # ── Generate & Store ──────────────────────────────────────────────────────

    def generate_and_store_otp(
        self,
        email: str,
        name: str,
        hashed_pwd: str,
        is_resend: bool = False,
    ) -> tuple[str, int]:
        """
        Generate a 6-digit OTP, persist a hashed record, return (raw_otp, expires_in_seconds).

        Rate limits:
          - is_resend=False: always allowed (initial send), replaces any existing record
          - is_resend=True:  limited to OTP_MAX_RESENDS resends with OTP_RESEND_COOLDOWN seconds between them

        Raises ValueError if resend rate limit is exceeded.
        """
        now = datetime.now(timezone.utc)

        existing = self.db.query(PendingOTP).filter_by(email=email.lower()).first()

        if is_resend and existing:
            # Enforce cooldown between resends
            if existing.last_sent_at:
                last_sent = existing.last_sent_at
                if last_sent.tzinfo is None:
                    last_sent = last_sent.replace(tzinfo=timezone.utc)
                seconds_since_last = (now - last_sent).total_seconds()
                if seconds_since_last < OTP_RESEND_COOLDOWN:
                    wait = int(OTP_RESEND_COOLDOWN - seconds_since_last)
                    raise ValueError(
                        f"Please wait {wait} seconds before requesting a new code."
                    )

            # Enforce resend count limit
            if existing.resend_count >= OTP_MAX_RESENDS:
                raise ValueError(
                    "Maximum resend attempts reached. "
                    "Please restart the signup process with a new email or try later."
                )

        # SECURITY FIX: use secrets module (cryptographically secure PRNG)
        raw_otp  = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = self._hash_otp(raw_otp)
        expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)

        if existing:
            # Update in-place (covers both initial replaces and resends)
            existing.otp_hash      = otp_hash
            existing.expires_at    = expires_at
            existing.last_sent_at  = now
            existing.name          = name
            existing.hashed_password = hashed_pwd
            if is_resend:
                existing.resend_count += 1
        else:
            pending = PendingOTP(
                email=email.lower(),
                name=name,
                hashed_password=hashed_pwd,
                otp_hash=otp_hash,
                expires_at=expires_at,
                last_sent_at=now,
                resend_count=0,
            )
            self.db.add(pending)

        self.db.commit()

        expires_in = int((expires_at - now).total_seconds())
        logger.info("OTP generated for email=%s (is_resend=%s)", email, is_resend)
        return raw_otp, expires_in

    # ── Verify OTP ────────────────────────────────────────────────────────────

    def verify_otp(self, email: str, otp: str) -> PendingOTP:
        """
        Verify a submitted OTP against the stored hash.

        Returns the PendingOTP record on success.
        Raises ValueError with a generic message on any failure (expired, wrong code,
        not found) — deliberately does not distinguish between failure modes to
        prevent oracle attacks.
        """
        # DEFENSIVE: validate OTP format before any DB/hash work
        otp = (otp or "").strip()
        if not otp.isdigit() or len(otp) != 6:
            raise ValueError("Invalid verification code.")

        _GENERIC_ERROR = "Invalid or expired verification code."

        pending = self.get_pending(email)
        if not pending:
            raise ValueError(_GENERIC_ERROR)

        # Expiry check
        expires_at = pending.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise ValueError(_GENERIC_ERROR)

        # SECURITY FIX: constant-time comparison
        expected = self._hash_otp(otp)
        if not hmac.compare_digest(expected, pending.otp_hash):
            raise ValueError(_GENERIC_ERROR)

        return pending

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_pending(self, email: str) -> Optional[PendingOTP]:
        """
        Retrieve pending OTP record for email.
        DEFENSIVE: returns None on DB error rather than propagating.
        """
        try:
            return self.db.query(PendingOTP).filter_by(email=email.lower()).first()
        except Exception as exc:
            logger.error("get_pending DB error for email=%s: %s", email, exc)
            return None

    def delete_pending(self, email: str) -> None:
        """
        Delete a used OTP record.
        DEFENSIVE: logs errors but never raises — deletion failure should not
        break the signup flow. Expired records are cleaned up by a periodic task.
        """
        try:
            self.db.query(PendingOTP).filter_by(email=email.lower()).delete()
            self.db.commit()
        except Exception as exc:
            logger.warning(
                "delete_pending failed for email=%s (non-fatal): %s\n%s",
                email, exc, traceback.format_exc(),
            )
            try:
                self.db.rollback()
            except Exception:
                pass

    @staticmethod
    def _hash_otp(raw_otp: str) -> str:
        """Hash an OTP using SHA-256. Returns hex digest."""
        return hashlib.sha256(raw_otp.encode("utf-8")).hexdigest()
