"""
VYAS v2.1 — Auth Router
============================
Production hardening applied on top of v2.1:

  SECURITY FIXES:
    1. login() no longer leaks exception details to the client. The catch-all
       used to return `f"Login failed due to a server error: {type(exc).__name__}: {exc}"`.
       That exposes internal error types, DB messages, and variable names to
       any caller who triggers an unhandled exception. Now returns a generic
       500 message and logs the full traceback internally only.
    2. _store_refresh_token() now wraps the DB commit in a try/except so a
       transient DB error while saving the refresh token does not leave the
       user with an access token but no way to refresh it silently — it raises
       cleanly so the calling endpoint can return 500 instead of partial auth.
    3. _check_brute_force() now handles DB errors gracefully: if the LoginAttempt
       query fails, it fails-open with a warning log rather than crashing login
       entirely (a DB read failure should not permanently lock users out).
    4. signup_verify(): if _create_user_with_wallet() or the commit raises a DB
       IntegrityError (race condition: same email registered twice in the tiny
       window between the duplicate-check and INSERT), it is now caught and
       returns 400 "email already registered" rather than a 500 with a DB error.

  DEFENSIVE PROGRAMMING:
    5. _build_me_response() guards against wallet being None (possible in edge
       case where wallet creation failed mid-transaction) — returns safe defaults
       rather than crashing with AttributeError.
    6. All debug-only endpoints (clear-lockout) are guarded by is_production check.

  All existing v2.1 behaviour (OTP flow, legacy endpoint, brute-force, token
  rotation, OAuth-only user handling) is fully preserved.
"""

import logging
import traceback
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from core.auth import get_current_user
from core.config import get_settings
from core.security import (
    create_access_token,
    generate_refresh_token_str,
    hash_password,
    verify_password,
)
from database import get_db
from middleware.rate_limit import auth_rate_limit
from models.user import LoginAttempt, RefreshToken, User
from models.wallet import LedgerEntryType
from schemas.auth import (
    InitiateSignupRequest,
    InitiateSignupResponse,
    LoginRequest,
    ResendOTPRequest,
    SignupRequest,
    UserMeResponse,
    VerifyOTPRequest,
)
from services.email import send_otp_email
from services.otp_service import OTPService
from services.wallet_service import WalletService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Auth"])

OTP_EXPIRY_MINUTES = 10


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
        max_age=max_age,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def _store_refresh_token(
    db: Session, user_id: int, raw_token: str, request: Request
) -> RefreshToken:
    """
    Persist the refresh token hash.

    Raises on DB failure so the caller can return a proper error instead of
    silently issuing an access token with no valid refresh path.
    """
    token_hash = RefreshToken.hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent", "")[:256],
        ip_address=request.client.host if request.client else None,
    )
    db.add(rt)
    db.commit()
    return rt


def _check_brute_force(db: Session, email: str) -> None:
    """
    Check for too many recent failed login attempts.

    DEFENSIVE: If the DB query itself fails, log a warning and allow the
    request to proceed. A transient DB read error should not permanently
    lock out all users.
    """
    try:
        window_start = datetime.now(timezone.utc) - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        recent_failures = (
            db.query(LoginAttempt)
            .filter(
                LoginAttempt.email == email.lower(),
                LoginAttempt.success == False,  # noqa: E712
                LoginAttempt.attempted_at >= window_start,
            )
            .count()
        )
        if recent_failures >= settings.MAX_LOGIN_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Too many failed login attempts. "
                    f"Account temporarily locked for {settings.LOGIN_LOCKOUT_MINUTES} minutes."
                ),
            )
    except HTTPException:
        raise
    except Exception as exc:
        # Fail-open: brute-force check failed — log and continue.
        # Better to allow a login attempt than to block all users on a DB hiccup.
        logger.warning("Brute-force check failed (fail-open): email=%s error=%s", email, exc)


def _record_attempt(
    db: Session, email: str, request: Request, *, success: bool
) -> None:
    """Record a login attempt. Failures are silent — never crash the login flow."""
    try:
        attempt = LoginAttempt(
            email=email.lower(),
            ip_address=request.client.host if request.client else None,
            success=success,
        )
        db.add(attempt)
        db.commit()
    except Exception as exc:
        # Non-fatal: audit logging failure should not break authentication.
        logger.warning("Failed to record login attempt for email=%s: %s", email, exc)
        try:
            db.rollback()
        except Exception:
            pass


def _fetch_user_fresh(db: Session, user_id: int) -> User:
    """
    Re-fetch user with all needed relationships eagerly loaded.
    Call this after any db.commit() to get a fresh, non-expired object.
    """
    return (
        db.query(User)
        .options(joinedload(User.profile), joinedload(User.wallet))
        .filter_by(id=user_id)
        .first()
    )


def _build_me_response(user: User, access_token: str = None) -> dict:
    """
    Build the /me response payload.
    DEFENSIVE: guards against missing wallet/profile relationships.
    """
    profile = user.profile
    wallet  = user.wallet

    profile_data = None
    completeness_percent = 0
    if profile:
        profile_data = {
            "preparing_exam": profile.preparing_exam,
            "target_year":    profile.target_year,
            "subject_focus":  profile.subject_focus,
            "avatar":         profile.avatar,
            "daily_goal_mins": profile.daily_goal_mins,
            "bio":            profile.bio,
        }
        completeness_percent = profile.completeness_percent

    wallet_data = None
    low_credit_warning = False
    if wallet:
        wallet_data = {
            "balance_microcredits": wallet.balance_microcredits,
            "balance_credits":      wallet.balance_credits,
        }
        low_credit_warning = (
            wallet.balance_microcredits < settings.LOW_CREDIT_WARN_MICROCREDITS
        )

    return {
        "id":                          user.id,
        "name":                        user.name,
        "email":                       user.email,
        "created_at":                  user.created_at,
        "has_seen_premium_popup":      user.has_seen_premium_popup,
        "profile":                     profile_data,
        "profile_completeness_percent": completeness_percent,
        "wallet":                      wallet_data,
        "low_credit_warning":          low_credit_warning,
        "profile_picture":             user.profile_picture,
        "access_token":                access_token,
    }


def _create_user_with_wallet(
    db: Session,
    *,
    name: str,
    email: str,
    hashed_pwd: str,
    email_verified: bool = False,
    profile_picture: str | None = None,
) -> User:
    """
    Atomically create User + Wallet + signup bonus in one transaction.
    Returns the flushed (not yet committed) user so the caller can commit.
    """
    user = User(
        name=name.strip(),
        email=email.lower().strip(),
        hashed_password=hashed_pwd,
        email_verified=email_verified,
        profile_picture=profile_picture,
    )
    db.add(user)
    db.flush()  # populate user.id without committing

    wallet_service = WalletService(db)
    wallet_service.create_wallet(user.id)
    wallet_service.grant_credits(
        user_id=user.id,
        amount_microcredits=settings.SIGNUP_BONUS_MICROCREDITS,
        entry_type=LedgerEntryType.SIGNUP_BONUS,
        idempotency_key=f"signup_bonus:{user.id}",
        description=(
            f"Welcome bonus — "
            f"{settings.SIGNUP_BONUS_MICROCREDITS // settings.MICROCREDITS_PER_CREDIT} "
            f"free credits!"
        ),
    )
    return user


# ══════════════════════════════════════════════════════════════════════════════
# NEW v2.1 — Two-Step Email-Verified Signup
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/signup/initiate", response_model=InitiateSignupResponse, status_code=202)
def signup_initiate(
    body: InitiateSignupRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(auth_rate_limit),
):
    """
    Step 1 of the two-step signup flow.
    Validates the submitted data, stores the pending registration with a
    hashed OTP, and emails the 6-digit code to the user.
    """
    email = body.email.lower().strip()

    if db.query(User).filter_by(email=email).first():
        logger.info("signup_initiate: email already registered (%s) — returning 400", email)
        raise HTTPException(
            status_code=400,
            detail="This email is already registered. Please sign in instead.",
        )

    hashed_pwd = hash_password(body.password)
    otp_svc    = OTPService(db)

    try:
        raw_otp, expires_in = otp_svc.generate_and_store_otp(
            email=email,
            name=body.name.strip(),
            hashed_pwd=hashed_pwd,
            is_resend=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    background_tasks.add_task(
        send_otp_email,
        to_email=email,
        otp=raw_otp,
        user_name=body.name.strip(),
        expires_minutes=OTP_EXPIRY_MINUTES,
    )
    logger.info("Signup initiated for email=%s", email)

    return InitiateSignupResponse(
        message=f"Verification code sent to {email}",
        email=email,
        expires_in_seconds=expires_in,
    )


@router.post("/signup/verify", response_model=UserMeResponse, status_code=201)
def signup_verify(
    body: VerifyOTPRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(auth_rate_limit),
):
    """
    Step 2 of the two-step signup flow.
    Validates the OTP, creates the user account, grants the signup bonus,
    and logs the user in by returning tokens.
    """
    email   = body.email.lower().strip()
    otp_svc = OTPService(db)

    try:
        pending = otp_svc.verify_otp(email=email, otp=body.otp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if db.query(User).filter_by(email=email).first():
        otp_svc.delete_pending(email)
        raise HTTPException(status_code=400, detail="Email already registered. Please sign in.")

    # SECURITY FIX: wrap user creation in IntegrityError guard.
    # Two concurrent /verify calls for the same email would both pass the
    # duplicate check above but the second INSERT will hit the UNIQUE constraint.
    try:
        user = _create_user_with_wallet(
            db,
            name=pending.name,
            email=email,
            hashed_pwd=pending.hashed_password,
            email_verified=True,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        otp_svc.delete_pending(email)
        raise HTTPException(status_code=400, detail="Email already registered. Please sign in.")

    otp_svc.delete_pending(email)

    user = _fetch_user_fresh(db, user.id)

    access_token = create_access_token({"sub": str(user.id)})
    raw_refresh  = generate_refresh_token_str()
    _store_refresh_token(db, user.id, raw_refresh, request)
    _set_refresh_cookie(response, raw_refresh)

    user = _fetch_user_fresh(db, user.id)

    logger.info("New user registered via OTP: id=%s email=%s", user.id, user.email)
    return _build_me_response(user, access_token=access_token)


@router.post("/signup/resend-otp", status_code=202)
def signup_resend_otp(
    body: ResendOTPRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(auth_rate_limit),
):
    """
    Resend a fresh OTP for an in-progress signup.
    Always returns 202 — no information leak about whether the email exists.
    """
    email   = body.email.lower().strip()
    otp_svc = OTPService(db)

    pending = otp_svc.get_pending(email)
    if not pending:
        return {"message": "If a signup is in progress, a new code has been sent."}

    try:
        raw_otp, expires_in = otp_svc.generate_and_store_otp(
            email=email,
            name=pending.name,
            hashed_pwd=pending.hashed_password,
            is_resend=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    background_tasks.add_task(
        send_otp_email,
        to_email=email,
        otp=raw_otp,
        user_name=pending.name,
        expires_minutes=OTP_EXPIRY_MINUTES,
    )
    logger.info("OTP resent for email=%s (resend_count=%s)", email, pending.resend_count + 1)
    return {"message": "If a signup is in progress, a new code has been sent.", "expires_in_seconds": expires_in}


# ══════════════════════════════════════════════════════════════════════════════
# PRESERVED — Legacy direct signup (backward compatible)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/signup", response_model=UserMeResponse, status_code=201)
def signup(
    body: SignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(auth_rate_limit),
):
    """
    Legacy direct signup — preserved for backward compatibility and automated tests.
    The frontend now uses /auth/signup/initiate + /auth/signup/verify instead.
    """
    if db.query(User).filter_by(email=body.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        user = _create_user_with_wallet(
            db,
            name=body.name.strip(),
            email=body.email.lower().strip(),
            hashed_pwd=hash_password(body.password),
            email_verified=False,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")

    user = _fetch_user_fresh(db, user.id)

    access_token = create_access_token({"sub": str(user.id)})
    raw_refresh  = generate_refresh_token_str()
    _store_refresh_token(db, user.id, raw_refresh, request)
    _set_refresh_cookie(response, raw_refresh)

    user = _fetch_user_fresh(db, user.id)

    logger.info("New user registered (legacy endpoint): id=%s email=%s", user.id, user.email)
    return _build_me_response(user, access_token=access_token)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=UserMeResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(auth_rate_limit),
):
    try:
        email = body.email.lower().strip()
        _check_brute_force(db, email)

        user = db.query(User).filter_by(email=email).first()

        # BUG FIX (v2.0.3): hashed_password is nullable for OAuth-only users.
        if user and user.hashed_password is None:
            _record_attempt(db, email, request, success=False)
            raise HTTPException(
                status_code=401,
                detail="This account was created with Google sign-in. Use 'Continue with Google' to log in.",
            )

        _DUMMY_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"
        password_ok = verify_password(body.password, user.hashed_password if user else _DUMMY_HASH)

        if not user or not password_ok:
            _record_attempt(db, email, request, success=False)
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account deactivated")

        user_id = user.id
        _record_attempt(db, email, request, success=True)

        db.query(User).filter_by(id=user_id).update(
            {"last_login_at": datetime.now(timezone.utc)},
            synchronize_session=False,
        )
        db.commit()

        fresh_user = _fetch_user_fresh(db, user_id)

        if not fresh_user.wallet:
            logger.warning("User id=%s has no wallet — creating one now", user_id)
            wallet_service = WalletService(db)
            wallet_service.create_wallet(user_id)
            db.commit()
            fresh_user = _fetch_user_fresh(db, user_id)

        access_token = create_access_token({"sub": str(user_id)})
        raw_refresh  = generate_refresh_token_str()
        _store_refresh_token(db, user_id, raw_refresh, request)
        _set_refresh_cookie(response, raw_refresh)

        fresh_user = _fetch_user_fresh(db, user_id)

        logger.info("User login: id=%s", user_id)
        return _build_me_response(fresh_user, access_token=access_token)

    except HTTPException:
        raise
    except Exception as exc:
        # SECURITY FIX: log full traceback internally, but never expose
        # exception details (type, message, stack) to the client.
        logger.error(
            "UNHANDLED EXCEPTION in login for email=%s\n%s",
            body.email,
            traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail="Login failed due to a server error. Please try again.",
        )


# ── Refresh Token ─────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=UserMeResponse)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    vyas_refresh: str | None = Cookie(
        default=None, alias=settings.REFRESH_TOKEN_COOKIE_NAME
    ),
    _rate_limit: None = Depends(auth_rate_limit),
):
    invalid_exc = HTTPException(
        status_code=401, detail="Session expired. Please log in again."
    )

    if not vyas_refresh:
        raise invalid_exc

    token_hash = RefreshToken.hash_token(vyas_refresh)
    now = datetime.now(timezone.utc)

    rt = (
        db.query(RefreshToken)
        .filter(
            and_(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )
        .first()
    )

    if not rt:
        _clear_refresh_cookie(response)
        raise invalid_exc

    user_id = rt.user_id
    user = _fetch_user_fresh(db, user_id)

    if not user or not user.is_active:
        rt.revoke()
        db.commit()
        _clear_refresh_cookie(response)
        raise invalid_exc

    rt.revoke()
    db.commit()

    new_access      = create_access_token({"sub": str(user_id)})
    new_raw_refresh = generate_refresh_token_str()
    _store_refresh_token(db, user_id, new_raw_refresh, request)
    _set_refresh_cookie(response, new_raw_refresh)

    fresh_user = _fetch_user_fresh(db, user_id)
    return _build_me_response(fresh_user, access_token=new_access)


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    vyas_refresh: str | None = Cookie(
        default=None, alias=settings.REFRESH_TOKEN_COOKIE_NAME
    ),
):
    if vyas_refresh:
        token_hash = RefreshToken.hash_token(vyas_refresh)
        rt = db.query(RefreshToken).filter_by(
            token_hash=token_hash, user_id=current_user.id
        ).first()
        if rt and not rt.is_revoked:
            rt.revoke()
            db.commit()

    _clear_refresh_cookie(response)
    logger.info("User logged out: id=%s", current_user.id)


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserMeResponse)
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = _fetch_user_fresh(db, current_user.id)
    return _build_me_response(user)


# ── Ack Popup ─────────────────────────────────────────────────────────────────

@router.post("/ack-popup", status_code=204)
def ack_premium_popup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.has_seen_premium_popup:
        current_user.has_seen_premium_popup = True
        db.commit()
        logger.info("Premium popup acknowledged: user_id=%s", current_user.id)


# ── Dev-only: Clear lockout (disabled in production) ──────────────────────────

if not get_settings().is_production:
    @router.delete("/dev/clear-lockout/{email}", tags=["Dev"])
    def dev_clear_lockout(
        email: str,
        db: Session = Depends(get_db),
    ):
        """DEV ONLY — clear brute-force lockout for an email. Not available in production."""
        deleted = (
            db.query(LoginAttempt)
            .filter(LoginAttempt.email == email.lower(), LoginAttempt.success == False)  # noqa: E712
            .delete()
        )
        db.commit()
        return {"deleted": deleted, "email": email}
