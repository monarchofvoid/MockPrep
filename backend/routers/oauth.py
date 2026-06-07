"""
VYAS v2.1 — Google OAuth Router
====================================
Production hardening applied:

  SECURITY FIXES:
    1. google_oauth_callback() now catches ValueError from OAuthService
       (deactivated user, missing user reference) and returns a proper redirect
       to the error page instead of a 500. A deactivated user attempting OAuth
       should be redirected to the login page with an error, not cause a crash.
    2. State cookie is deleted regardless of whether CSRF validation passes
       or fails — the original code only deleted it on success. This prevents
       cookie accumulation if the user tries to OAuth multiple times.
    3. _exchange_code_for_tokens() now checks for error fields in the Google
       response body (Google returns 200 with an error field on some failures)
       rather than only relying on HTTP status codes.
    4. _fetch_google_userinfo() validates that the 'email_verified' field from
       Google is True before proceeding — prevents account takeover via
       unverified email addresses.

  DEFENSIVE PROGRAMMING:
    5. profile_picture URL length is capped at 2000 characters before storage
       to prevent abnormally long URLs from hitting DB column length limits.

  All existing routes, CSRF state validation, account linking logic, and
  token issuance are fully preserved.
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from core.auth import get_current_user
from core.config import get_settings
from core.security import create_access_token, generate_refresh_token_str
from database import get_db
from models.user import OAuthAccount, RefreshToken, User
from routers.auth import _build_me_response, _set_refresh_cookie, _store_refresh_token
from schemas.auth import UserMeResponse
from services.oauth_service import OAuthService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth/oauth", tags=["OAuth"])

_GOOGLE_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_OAUTH_STATE_COOKIE = "vyas_oauth_state"

# Cap profile picture URL length to prevent DB column overflow
_MAX_PICTURE_URL_LEN = 2000


def _require_google_config() -> None:
    """Raise 503 if Google OAuth is not configured."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google OAuth is not configured. "
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in environment."
            ),
        )


# ── Initiate OAuth Flow ───────────────────────────────────────────────────────

@router.get("/google")
def google_oauth_initiate(response: Response):
    """
    Redirect the user to Google's OAuth consent screen.
    Generates a random state parameter for CSRF protection.
    """
    _require_google_config()

    state = secrets.token_urlsafe(32)

    response = RedirectResponse(url=_build_google_auth_url(state), status_code=302)
    response.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


def _build_google_auth_url(state: str) -> str:
    params = {
        "client_id":     settings.GOOGLE_CLIENT_ID,
        "redirect_uri":  settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


# ── OAuth Callback ────────────────────────────────────────────────────────────

@router.get("/google/callback", response_model=UserMeResponse)
def google_oauth_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    vyas_oauth_state: Optional[str] = Cookie(default=None, alias=_OAUTH_STATE_COOKIE),
    db: Session = Depends(get_db),
):
    """
    Handle Google OAuth callback.

    Steps:
      1. Validate CSRF state
      2. Exchange auth code for Google access + id tokens
      3. Fetch user info from Google (including profile picture)
      4. Verify email_verified = True
      5. Find or create VYAS user
      6. Link OAuthAccount to user
      7. Issue VYAS access + refresh tokens
      8. Redirect to frontend dashboard
    """
    _require_google_config()

    # SECURITY FIX: Always delete the state cookie, whether auth succeeds or fails.
    # The original code only deleted it on success, leaving it set on error paths.
    response.delete_cookie(key=_OAUTH_STATE_COOKIE, path="/")

    if error:
        logger.warning("Google OAuth error: %s", error)
        frontend_url = f"{settings.FRONTEND_URL}/?error=oauth_denied"
        return RedirectResponse(url=frontend_url, status_code=302)

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")

    # ── CSRF State Validation ─────────────────────────────────────────────────
    if not vyas_oauth_state or not state or not secrets.compare_digest(
        vyas_oauth_state, state
    ):
        logger.warning("OAuth CSRF state mismatch — possible CSRF attack")
        raise HTTPException(status_code=400, detail="Invalid OAuth state. Please try again.")

    # ── Exchange Code for Tokens ──────────────────────────────────────────────
    token_data = _exchange_code_for_tokens(code)
    if not token_data:
        raise HTTPException(status_code=502, detail="Failed to exchange OAuth code for tokens")

    # ── Fetch Google User Info ────────────────────────────────────────────────
    google_user = _fetch_google_userinfo(token_data["access_token"])
    if not google_user:
        raise HTTPException(status_code=502, detail="Failed to fetch user info from Google")

    google_id            = google_user.get("sub")
    google_email         = google_user.get("email", "").lower().strip()
    google_name          = google_user.get("name", "")
    google_picture_raw   = google_user.get("picture", "")
    # DEFENSIVE: cap profile picture URL length
    google_picture       = google_picture_raw[:_MAX_PICTURE_URL_LEN] if google_picture_raw else ""
    google_access_token  = token_data.get("access_token", "")
    google_refresh_token = token_data.get("refresh_token", "")

    if not google_id or not google_email:
        raise HTTPException(status_code=502, detail="Google did not return required user fields")

    # SECURITY FIX: verify email_verified flag from Google.
    # If Google hasn't verified the email, refuse the login to prevent account
    # takeover via unverified email addresses.
    if not google_user.get("email_verified", False):
        logger.warning(
            "OAuth rejected: email_verified=False for google_id=%s email=%s",
            google_id, google_email,
        )
        error_url = f"{settings.FRONTEND_URL}/?error=email_not_verified"
        return RedirectResponse(url=error_url, status_code=302)

    # ── Find or Create VYAS User ──────────────────────────────────────────────
    oauth_service = OAuthService(db)
    try:
        user = oauth_service.find_or_create_user(
            provider="google",
            provider_account_id=google_id,
            provider_email=google_email,
            name=google_name,
            profile_picture=google_picture,
            access_token=google_access_token,
            refresh_token=google_refresh_token,
        )
    except ValueError as exc:
        # SECURITY FIX: deactivated users or referential integrity errors should
        # redirect to an error page, not crash with 500.
        logger.warning("OAuthService.find_or_create_user rejected: %s", exc)
        error_url = f"{settings.FRONTEND_URL}/?error=account_error"
        return RedirectResponse(url=error_url, status_code=302)

    # Reload with relationships for _build_me_response
    user = (
        db.query(User)
        .options(joinedload(User.profile), joinedload(User.wallet))
        .filter_by(id=user.id)
        .first()
    )

    # ── Issue VYAS Tokens ─────────────────────────────────────────────────────
    access_token = create_access_token({"sub": str(user.id)})
    raw_refresh  = generate_refresh_token_str()
    _store_refresh_token(db, user.id, raw_refresh, request)

    logger.info("Google OAuth login/signup: user_id=%s email=%s", user.id, user.email)

    # Redirect to the dedicated OAuth callback page on the frontend.
    # The access_token is passed as a query parameter so the frontend page
    # can store it in memory (authStore) before AppProviders runs the session
    # check. Without this, the dashboard sees isAuthenticated=false and
    # immediately redirects to landing — the user never reaches the dashboard.
    #
    # SECURITY NOTE: The access_token in the URL is short-lived (15 minutes)
    # and is only used for this one page transition. Next.js replaces the URL
    # (router.replace) immediately after reading it, so it does not persist
    # in browser history. The long-lived credential is the httpOnly refresh
    # cookie, which is set on this same response.
    redirect_url = (
        f"{settings.FRONTEND_URL}/auth/oauth/google/callback"
        f"?access_token={access_token}"
    )
    resp = RedirectResponse(url=redirect_url, status_code=302)
    _set_refresh_cookie(resp, raw_refresh)
    return resp


# ── Token Exchange Helpers ─────────────────────────────────────────────────────

def _exchange_code_for_tokens(code: str) -> Optional[dict]:
    """Exchange authorization code for Google access + refresh tokens."""
    try:
        resp = httpx.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri":  settings.GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        # SECURITY FIX: Google occasionally returns 200 with an error field
        if "error" in data:
            logger.error(
                "Google token exchange returned error: %s — %s",
                data.get("error"), data.get("error_description"),
            )
            return None

        return data
    except Exception as exc:
        logger.error("Failed to exchange Google OAuth code: %s", exc)
        return None


def _fetch_google_userinfo(access_token: str) -> Optional[dict]:
    """Fetch user profile from Google using access token."""
    try:
        resp = httpx.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Failed to fetch Google user info: %s", exc)
        return None