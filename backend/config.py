"""
VYAS v0.8 — Environment Configuration & Validation
=====================================================
Single source of truth for all env variables.
Import AppConfig from here instead of reading os.getenv() scattered everywhere.

Usage:
    from config import AppConfig
    print(AppConfig.GROQ_API_KEY)

v0.8 changes:
  - Added Groq AI provider settings (GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL)
  - Added provider-agnostic AI tuning knobs (AI_TIMEOUT, AI_MAX_RETRIES,
    AI_TEMPERATURE_MOCK, AI_TEMPERATURE_TUTOR, AI_MAX_TOKENS_MOCK,
    AI_MAX_TOKENS_TUTOR)
  - Kept all Gemini settings for backward compatibility during transition.
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

    # ── Groq / AI (v0.8 — primary AI provider) ───────────────────────────────
    @property
    def GROQ_API_KEY(self) -> str:
        return _optional("GROQ_API_KEY")

    @property
    def GROQ_MODEL(self) -> str:
        return _optional("GROQ_MODEL", "openai/gpt-oss-120b")

    @property
    def GROQ_BASE_URL(self) -> str:
        return _optional("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

    # ── Provider-agnostic AI tuning knobs ─────────────────────────────────────
    @property
    def AI_TIMEOUT(self) -> float:
        return float(_optional("AI_TIMEOUT", "50.0"))

    @property
    def AI_MAX_RETRIES(self) -> int:
        return int(_optional("AI_MAX_RETRIES", "2"))

    @property
    def AI_TEMPERATURE_MOCK(self) -> float:
        return float(_optional("AI_TEMPERATURE_MOCK", "0.5"))

    @property
    def AI_TEMPERATURE_TUTOR(self) -> float:
        return float(_optional("AI_TEMPERATURE_TUTOR", "0.3"))

    @property
    def AI_MAX_TOKENS_MOCK(self) -> int:
        return int(_optional("AI_MAX_TOKENS_MOCK", "8192"))

    @property
    def AI_MAX_TOKENS_TUTOR(self) -> int:
        return int(_optional("AI_MAX_TOKENS_TUTOR", "2048"))

    # ── Gemini / AI (kept for backward compatibility — not used in v0.8) ──────
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
