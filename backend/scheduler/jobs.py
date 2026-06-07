"""
VYAS v2.2.0 — Scheduled Job Functions
=======================================
APScheduler replacement for all six Celery Beat tasks.

Each function is a 1:1 port of the corresponding Celery task body, with the
@shared_task / @celery_app.task decorator removed and the function signature
made compatible with APScheduler's AsyncIOExecutor.

All database operations use SessionLocal() exactly as the Celery tasks did.
No business logic has been changed — only the task infrastructure.

Job registry (registered in scheduler/setup.py):
  cleanup_stale_jobs              — every 1h  (was: Celery beat, 3600s)
  reconcile_payments              — every 24h (was: Celery beat, 86400s)
  cleanup_expired_refresh_tokens  — every 24h (was: Celery beat, 86400s)
  cleanup_old_login_attempts      — every 24h (was: Celery beat, 86400s)
  cleanup_expired_password_resets — every 1h  (was: Celery beat, 3600s)
  reconcile_all_wallets           — every 24h (was: Celery beat, 86400s)

Note on send_low_credit_warning_task:
  This Celery task was dead code — defined but never dispatched anywhere in the
  codebase. No .delay() or .apply_async() call exists. It is NOT ported here.
  The low-credit warning email remains unimplemented (as it was in the original).
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("vyas.scheduler.jobs")


# ── 1. Cleanup Stale AI Jobs ───────────────────────────────────────────────────

async def cleanup_stale_jobs() -> None:
    """
    Hourly job — mark any AI jobs stuck in PENDING/QUEUED/RUNNING for more than
    30 minutes as FAILED and issue a credit refund.

    Jobs can get stuck when:
      - The FastAPI process restarted while an asyncio task was mid-generation
        (the asyncio task is lost; DB status stays RUNNING)
      - The asyncio task raised an unhandled exception that bypassed _safe_fail

    This is the safety net — it catches anything the task error handler missed.
    The cutoff is 30 minutes (reduced from 2 hours in the old Celery task)
    because asyncio tasks complete or fail quickly; no queue delays exist.

    Ported from: tasks/ai_tasks.py::cleanup_stale_jobs (Celery @shared_task)
    """
    from database import SessionLocal
    from models.ai_job import AIJob, AIJobStatus
    from services.wallet_service import WalletService

    logger.info("cleanup_stale_jobs: scanning for stale AI jobs…")
    db = SessionLocal()
    stale_count = 0

    try:
        # 30-minute cutoff — asyncio tasks should never take this long legitimately.
        # The old Celery task used 2 hours to allow for worker cold-start delays;
        # those delays no longer exist since we run in-process.
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

        stale_jobs = (
            db.query(AIJob)
            .filter(
                AIJob.status.in_([
                    AIJobStatus.PENDING,
                    AIJobStatus.QUEUED,
                    AIJobStatus.RUNNING,
                ]),
                AIJob.created_at < cutoff,
            )
            .all()
        )

        for job in stale_jobs:
            logger.warning(
                "cleanup_stale_jobs: marking job_id=%s (status=%s created_at=%s) as FAILED",
                job.id, job.status, job.created_at,
            )
            try:
                job.status        = AIJobStatus.FAILED
                job.error_message = "Generation timed out. Your credits have been refunded."
                job.failed_at     = datetime.now(timezone.utc)
                db.flush()

                if job.deduction_ledger_entry_id:
                    wallet_service = WalletService(db)
                    wallet_service.refund_credits(
                        original_ledger_entry_id=job.deduction_ledger_entry_id,
                        reason=f"Stale AI job cleanup: job_id={job.id}",
                    )

                db.commit()
                stale_count += 1

                # Clear Redis active-job marker so user can submit a new job
                try:
                    from core.redis import clear_user_active_job
                    clear_user_active_job(job.user_id)
                except Exception as redis_exc:
                    logger.warning(
                        "cleanup_stale_jobs: could not clear Redis active job for "
                        "user_id=%s: %s", job.user_id, redis_exc
                    )

            except Exception as exc:
                logger.error(
                    "cleanup_stale_jobs: failed to clean job_id=%s: %s", job.id, exc
                )
                try:
                    db.rollback()
                except Exception:
                    pass

    except Exception as exc:
        logger.error("cleanup_stale_jobs: query failed: %s", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass

    logger.info("cleanup_stale_jobs: cleaned %d stale jobs", stale_count)


# ── 2. Reconcile Payments ──────────────────────────────────────────────────────

async def reconcile_payments() -> None:
    """
    Daily job — find payment orders stuck in CREATED or VERIFIED status.

    An order gets stuck when:
      - Razorpay webhook was never delivered (network issues, server restart)
      - Webhook signature failed due to misconfigured RAZORPAY_WEBHOOK_SECRET
      - User paid but closed the browser before /verify was called

    For each stuck order older than 30 minutes, this job:
      1. Queries Razorpay API to get the actual payment status
      2. If Razorpay reports 'captured' → grants credits and marks SETTLED
      3. If Razorpay reports 'failed' / not found → marks order FAILED
      4. If Razorpay reports pending → logs for next cycle

    Note on receipt email: unlike the Celery version which used
    send_payment_receipt_task.delay(), this function calls send_payment_receipt_email()
    directly in a try/except block. Email failure does not affect reconciliation
    success — the credits are already granted.

    Ported from: tasks/payment_tasks.py::reconcile_payments_task (Celery @celery_app.task)
    """
    from datetime import timedelta

    from database import SessionLocal
    from models.payment import PaymentOrder, PaymentOrderStatus
    from core.config import get_settings

    settings = get_settings()
    logger.info("reconcile_payments: starting payment reconciliation")
    db = SessionLocal()

    reconciled = 0
    stuck = 0

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

        stuck_orders = (
            db.query(PaymentOrder)
            .filter(
                PaymentOrder.status.in_([
                    PaymentOrderStatus.CREATED,
                    PaymentOrderStatus.VERIFIED,
                ]),
                PaymentOrder.created_at < cutoff,
            )
            .all()
        )

        if not stuck_orders:
            logger.info("reconcile_payments: no stuck orders found")
            return

        stuck = len(stuck_orders)
        logger.warning(
            "reconcile_payments: found %d stuck orders older than 30 minutes", stuck,
        )

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            logger.error("reconcile_payments: Razorpay credentials not configured — cannot reconcile")
            return

        import razorpay
        rzp_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        for order in stuck_orders:
            try:
                _reconcile_single_order(db, rzp_client, order)
                reconciled += 1
            except Exception as exc:
                logger.error(
                    "reconcile_payments: failed for order_id=%s: %s",
                    order.id, str(exc), exc_info=True,
                )

        try:
            db.commit()
        except Exception as exc:
            logger.error("reconcile_payments: commit failed: %s", exc)
            db.rollback()

        logger.info(
            "reconcile_payments: complete: reconciled=%d stuck=%d",
            reconciled, stuck,
        )

        remaining = stuck - reconciled
        if remaining > 0:
            try:
                import sentry_sdk
                sentry_sdk.capture_message(
                    f"Payment reconciliation: {remaining} orders still unresolved after Razorpay lookup",
                    level="warning",
                )
            except Exception:
                pass

    except Exception as exc:
        logger.error("reconcile_payments: task failed: %s", str(exc), exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass


def _reconcile_single_order(db, rzp_client, order) -> None:
    """
    Query Razorpay for the actual status of a stuck order and heal the DB record.

    Ported 1:1 from tasks/payment_tasks.py::_reconcile_single_order.
    The only change: receipt email is sent directly (not via Celery task).
    """
    from models.payment import PaymentOrderStatus
    from models.wallet import LedgerEntryType
    from services.wallet_service import WalletService
    from services.email import send_payment_receipt_email

    logger.info(
        "reconcile_payments: reconciling order internal_id=%s rzp_order_id=%s status=%s",
        order.id, order.razorpay_order_id, order.status.value,
    )

    try:
        payments_response = rzp_client.order.payments(order.razorpay_order_id)
        payments = payments_response.get("items", [])
    except Exception as exc:
        logger.error(
            "reconcile_payments: Razorpay API error for order %s: %s",
            order.razorpay_order_id, exc,
        )
        return

    if not payments:
        logger.info(
            "reconcile_payments: no payments found for order %s — marking FAILED", order.id
        )
        order.status = PaymentOrderStatus.FAILED
        order.failure_reason = "Reconciliation: no payment attempt found after 30 minutes"
        order.failed_at = datetime.now(timezone.utc)
        db.flush()
        return

    for payment in payments:
        payment_id     = payment.get("id")
        payment_status = payment.get("status")
        payment_amount = payment.get("amount")

        logger.info(
            "reconcile_payments: payment_id=%s status=%s amount=%s for order %s",
            payment_id, payment_status, payment_amount, order.id,
        )

        if payment_status == "captured":
            if order.status == PaymentOrderStatus.SETTLED:
                logger.info("reconcile_payments: order %s already settled — skip", order.id)
                return

            if payment_amount != order.amount_paise:
                logger.critical(
                    "RECONCILE AMOUNT MISMATCH: order=%s expected=%d got=%d",
                    order.id, order.amount_paise, payment_amount,
                )
                return

            wallet_service  = WalletService(db)
            idempotency_key = f"payment:{order.id}"
            wallet_service.grant_credits(
                user_id=order.user_id,
                amount_microcredits=order.credits_to_grant,
                entry_type=LedgerEntryType.TOPUP_PAYMENT,
                idempotency_key=idempotency_key,
                description=(
                    f"Reconciled: {order.credits_to_grant // 100} credits "
                    f"(Plan: {order.plan_id})"
                ),
                payment_order_id=order.id,
            )

            order.status              = PaymentOrderStatus.SETTLED
            order.razorpay_payment_id = payment_id
            order.captured_at         = datetime.now(timezone.utc)
            order.settled_at          = datetime.now(timezone.utc)
            db.flush()

            logger.info(
                "reconcile_payments: SUCCESS order=%s credits=%d",
                order.id, order.credits_to_grant // 100,
            )

            # Send receipt email directly (no BackgroundTasks context available here).
            # Email failure is non-fatal — credits are already granted.
            try:
                from models.user import User
                user = db.query(User).filter_by(id=order.user_id).first()
                if user:
                    send_payment_receipt_email(
                        to_email=user.email,
                        to_name=user.name,
                        credits_granted=order.credits_to_grant // 100,
                        amount_inr=order.amount_paise / 100.0,
                        order_id=order.id,
                    )
            except Exception as email_exc:
                logger.warning(
                    "reconcile_payments: receipt email failed for order %s: %s",
                    order.id, email_exc,
                )
            return

        elif payment_status == "failed":
            if order.status not in (PaymentOrderStatus.SETTLED, PaymentOrderStatus.FAILED):
                error_desc = payment.get("error_description", "Payment failed")
                order.status         = PaymentOrderStatus.FAILED
                order.failure_reason = f"Reconciled: {error_desc}"[:300]
                order.failed_at      = datetime.now(timezone.utc)
                db.flush()
                logger.info("reconcile_payments: order %s marked FAILED", order.id)
            return

    logger.info(
        "reconcile_payments: order %s has %d payment(s) but none captured or failed yet",
        order.id, len(payments),
    )


# ── 3. Cleanup Expired Refresh Tokens ─────────────────────────────────────────

async def cleanup_expired_refresh_tokens() -> None:
    """
    Daily job — purge expired refresh tokens (> 7 days old).

    RefreshToken rows expire after 7 days but are not auto-deleted.
    This cleanup prevents the refresh_tokens table from growing indefinitely.

    Ported from: tasks/maintenance_tasks.py::cleanup_expired_refresh_tokens
    """
    from database import SessionLocal
    from models.user import RefreshToken

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        deleted_count = (
            db.query(RefreshToken)
            .filter(RefreshToken.expires_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()

        if deleted_count > 0:
            logger.info(
                "cleanup_expired_refresh_tokens: deleted %d expired tokens (cutoff=%s)",
                deleted_count, cutoff,
            )
        else:
            logger.debug("cleanup_expired_refresh_tokens: no expired tokens found")

    except Exception as exc:
        logger.error("cleanup_expired_refresh_tokens: failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass


# ── 4. Cleanup Old Login Attempts ─────────────────────────────────────────────

async def cleanup_old_login_attempts() -> None:
    """
    Daily job — purge login attempt records older than 30 days.

    LoginAttempt records are used for brute-force protection (checks last N minutes).
    Records older than 30 days are never consulted and should be purged to prevent
    table bloat.

    Ported from: tasks/maintenance_tasks.py::cleanup_old_login_attempts
    """
    from database import SessionLocal
    from models.user import LoginAttempt

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        deleted_count = (
            db.query(LoginAttempt)
            .filter(LoginAttempt.attempted_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()

        if deleted_count > 0:
            logger.info(
                "cleanup_old_login_attempts: deleted %d records (cutoff=%s)",
                deleted_count, cutoff,
            )
        else:
            logger.debug("cleanup_old_login_attempts: no old records found")

    except Exception as exc:
        logger.error("cleanup_old_login_attempts: failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass


# ── 5. Cleanup Expired Password Resets ────────────────────────────────────────

async def cleanup_expired_password_resets() -> None:
    """
    Hourly job — purge expired password reset tokens (> 24 hours old).

    Password reset tokens expire after 1 hour, but unused tokens accumulate
    if users don't complete the reset flow. This cleanup runs hourly.

    Ported from: tasks/maintenance_tasks.py::cleanup_expired_password_resets
    """
    from database import SessionLocal
    from models.user import PasswordReset

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        deleted_count = (
            db.query(PasswordReset)
            .filter(PasswordReset.expires_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()

        if deleted_count > 0:
            logger.info(
                "cleanup_expired_password_resets: deleted %d tokens (cutoff=%s)",
                deleted_count, cutoff,
            )
        else:
            logger.debug("cleanup_expired_password_resets: no expired tokens found")

    except Exception as exc:
        logger.error("cleanup_expired_password_resets: failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass


# ── 6. Reconcile All Wallets ──────────────────────────────────────────────────

async def reconcile_all_wallets() -> None:
    """
    Daily job — verify wallet.balance == SUM(ledger.amount) for every user.
    Logs CRITICAL if any discrepancy is found. Logging-only; no auto-correction.

    Ported from: tasks/analytics_tasks.py::reconcile_all_wallets
    """
    from database import SessionLocal
    from models.wallet import Wallet
    from services.wallet_service import WalletService

    db = SessionLocal()
    try:
        wallets = db.query(Wallet).all()
        wallet_service = WalletService(db)
        inconsistent = []

        for wallet in wallets:
            try:
                result = wallet_service.reconcile(wallet.user_id)
                if not result["consistent"]:
                    inconsistent.append({
                        "user_id": wallet.user_id,
                        "delta":   result["delta"],
                    })
            except Exception as exc:
                logger.error(
                    "reconcile_all_wallets: error checking user_id=%s: %s",
                    wallet.user_id, exc,
                )

        if inconsistent:
            logger.critical(
                "Wallet reconciliation found %d inconsistencies: %s",
                len(inconsistent), inconsistent,
            )
        else:
            logger.info(
                "reconcile_all_wallets: passed — %d wallets checked", len(wallets)
            )

    except Exception as exc:
        logger.error("reconcile_all_wallets: failed: %s", exc)
    finally:
        try:
            db.close()
        except Exception:
            pass
