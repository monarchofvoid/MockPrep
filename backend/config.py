"""
VYAS v0.6 — Environment Configuration & Validation
=====================================================
Single source of truth for all env variables.
Import AppConfig from here instead of reading os.getenv() scattered everywhere.

Usage:
    from config import AppConfig
    print(AppConfig.GEMINI_API_KEY_TUTOR)
"""

import os
import secrets
import warnings
from pathlib import Path


def _require(name: str) -> str:
    """Return env var value or raise RuntimeError in production."""
    val = os.getenv(name, "").strip()
    if not val:
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env in ("production", "prod"):
            raise RuntimeError(
                f"Required environment variable '{name}' is not set. "
                "Cannot start in production without it."
            )
        warnings.warn(
            f"[VYAS] '{name}' is not set — this is unsafe in production.",
            stacklevel=2,
        )
    return val


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class _AppConfig:
    """Lazy-loading application configuration. Reads env vars on first access."""

    # ── Auth ──────────────────────────────────────────────────────────────────
    @property
    def SECRET_KEY(self) -> str:
        val = os.getenv("SECRET_KEY", "").strip()
        if not val:
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env in ("production", "prod"):
                raise RuntimeError(
                    "SECRET_KEY must be set in production. "
                    "Generate: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            warnings.warn(
                "[VYAS] SECRET_KEY not set — using insecure fallback. DO NOT deploy this.",
                stacklevel=2,
            )
            return "vyas-insecure-dev-only-change-in-production"
        return val

    @property
    def ALGORITHM(self) -> str:
        return "HS256"

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        # NOTE: No refresh token system exists yet.
        # Tokens expire after 7 days. Users must re-login after expiry.
        # TODO v0.7: implement refresh token endpoint for seamless renewal.
        return int(_optional("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days

    # ── Database ──────────────────────────────────────────────────────────────
    @property
    def DATABASE_URL(self) -> str:
        return _optional(
            "DATABASE_URL",
            "sqlite:///./vyas_dev.db",
        )

    # ── CORS ──────────────────────────────────────────────────────────────────
    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        raw = _optional(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://localhost:3000",
        )
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        env = _optional("ENVIRONMENT", "development")
        if env in ("production", "prod") and "*" in origins:
            warnings.warn(
                "[VYAS] ALLOWED_ORIGINS contains '*' in production — this is unsafe.",
                stacklevel=2,
            )
        return origins

    # ── Question Bank ─────────────────────────────────────────────────────────
    @property
    def QB_ROOT(self) -> Path:
        raw = _optional("QB_ROOT", "")
        if raw:
            return Path(raw)
        # Deterministic fallback: relative to THIS file's location
        return Path(__file__).parent.parent / "question_bank"

    # ── Gemini / AI ───────────────────────────────────────────────────────────
    @property
    def GEMINI_API_KEY_TUTOR(self) -> str:
        return _optional("GEMINI_API_KEY_TUTOR")

    @property
    def GEMINI_API_KEY_MOCK(self) -> str:
        return _optional("GEMINI_API_KEY_MOCK")

    @property
    def GEMINI_MODEL_TUTOR(self) -> str:
        return _optional("GEMINI_MODEL_TUTOR", "gemini-2.0-flash")

    @property
    def GEMINI_MODEL_MOCK(self) -> str:
        return _optional("GEMINI_MODEL_MOCK", "gemini-2.0-flash")

    # ── Email ─────────────────────────────────────────────────────────────────
    @property
    def BREVO_API_KEY(self) -> str:
        return _optional("BREVO_API_KEY")

    @property
    def FROM_EMAIL(self) -> str:
        return _optional("FROM_EMAIL", "noreply@vyas.app")

    @property
    def OWNER_EMAIL(self) -> str:
        return _optional("OWNER_EMAIL")

    @property
    def FRONTEND_URL(self) -> str:
        return _optional("FRONTEND_URL", "http://localhost:5173")

    # ── Rate limiting ─────────────────────────────────────────────────────────
    @property
    def RATE_LIMIT_AI_PER_MINUTE(self) -> str:
        """SlowAPI rate limit string for AI endpoints."""
        return _optional("RATE_LIMIT_AI_PER_MINUTE", "10/minute")

    @property
    def RATE_LIMIT_AUTH_PER_MINUTE(self) -> str:
        return _optional("RATE_LIMIT_AUTH_PER_MINUTE", "20/minute")

    # ── Logging ───────────────────────────────────────────────────────────────
    @property
    def LOG_LEVEL(self) -> str:
        return _optional("LOG_LEVEL", "INFO").upper()

    @property
    def ENVIRONMENT(self) -> str:
        return _optional("ENVIRONMENT", "development").lower()

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT in ("production", "prod")


AppConfig = _AppConfig()
