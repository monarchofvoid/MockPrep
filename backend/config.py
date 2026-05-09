"""
VYAS v2.0 — Environment Configuration & Validation
=====================================================
Single source of truth for ALL environment variables.

v2.0 changes:
  - REFRESH_TOKEN_EXPIRE_DAYS  (default: 7)
  - ACCESS_TOKEN_EXPIRE_MINUTES now 15 (down from 7 days — proper security)
  - REFRESH_TOKEN_COOKIE_NAME, REFRESH_TOKEN_COOKIE_SECURE, SAMESITE
  - MAX_LOGIN_ATTEMPTS / LOGIN_LOCKOUT_MINUTES (brute force protection)
  - COOKIE_DOMAIN (for cross-subdomain refresh)
  - DB connection pool settings
  - All Groq / AI tuning knobs preserved from v0.11
"""

import os
import warnings
from pathlib import Path


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class _AppConfig:
    """Lazy-loading application configuration."""

    # ── Auth — Access Tokens ──────────────────────────────────────────────────
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
            warnings.warn("[VYAS] SECRET_KEY not set — insecure fallback.", stacklevel=2)
            return "vyas-insecure-dev-only-change-in-production"
        return val

    @property
    def ALGORITHM(self) -> str:
        return "HS256"

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        # v2.0: 15 minutes (was 7 days). Short-lived + refresh token is proper security.
        return int(_optional("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

    # ── Auth — Refresh Tokens (v2.0 NEW) ─────────────────────────────────────
    @property
    def REFRESH_SECRET_KEY(self) -> str:
        val = os.getenv("REFRESH_SECRET_KEY", "").strip()
        if not val:
            env = os.getenv("ENVIRONMENT", "development").lower()
            if env in ("production", "prod"):
                raise RuntimeError("REFRESH_SECRET_KEY must be set in production.")
            warnings.warn("[VYAS] REFRESH_SECRET_KEY not set — insecure fallback.", stacklevel=2)
            return "vyas-refresh-insecure-dev-only"
        return val

    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        return int(_optional("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    @property
    def REFRESH_TOKEN_COOKIE_NAME(self) -> str:
        return _optional("REFRESH_TOKEN_COOKIE_NAME", "vyas_refresh")

    @property
    def REFRESH_TOKEN_COOKIE_SECURE(self) -> bool:
        val = _optional("REFRESH_TOKEN_COOKIE_SECURE", "")
        if val:
            return val.lower() in ("true", "1", "yes")
        return self.is_production

    @property
    def REFRESH_TOKEN_COOKIE_SAMESITE(self) -> str:
        return _optional("REFRESH_TOKEN_COOKIE_SAMESITE", "lax")

    @property
    def COOKIE_DOMAIN(self):
        val = _optional("COOKIE_DOMAIN", "")
        return val if val else None

    # ── Brute Force Protection (v2.0 NEW) ────────────────────────────────────
    @property
    def MAX_LOGIN_ATTEMPTS(self) -> int:
        return int(_optional("MAX_LOGIN_ATTEMPTS", "5"))

    @property
    def LOGIN_LOCKOUT_MINUTES(self) -> int:
        return int(_optional("LOGIN_LOCKOUT_MINUTES", "15"))

    # ── Database ──────────────────────────────────────────────────────────────
    @property
    def DATABASE_URL(self) -> str:
        return _optional("DATABASE_URL", "sqlite:///./vyas_dev.db")

    @property
    def DB_POOL_SIZE(self) -> int:
        return int(_optional("DB_POOL_SIZE", "5"))

    @property
    def DB_MAX_OVERFLOW(self) -> int:
        return int(_optional("DB_MAX_OVERFLOW", "10"))

    @property
    def DB_POOL_TIMEOUT(self) -> int:
        return int(_optional("DB_POOL_TIMEOUT", "30"))

    # ── CORS ──────────────────────────────────────────────────────────────────
    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        raw = _optional("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        if self.is_production and "*" in origins:
            warnings.warn("[VYAS] ALLOWED_ORIGINS contains '*' in production.", stacklevel=2)
        return origins

    # ── Question Bank ─────────────────────────────────────────────────────────
    @property
    def QB_ROOT(self):
        raw = _optional("QB_ROOT", "")
        if raw:
            return Path(raw)
        return Path(__file__).parent.parent / "question_bank"

    # ── Groq / AI ─────────────────────────────────────────────────────────────
    @property
    def GROQ_API_KEY(self) -> str:
        return _optional("GROQ_API_KEY")

    @property
    def GROQ_MODEL(self) -> str:
        return _optional("GROQ_MODEL", "openai/gpt-oss-120b")

    @property
    def GROQ_BASE_URL(self) -> str:
        return _optional("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

    @property
    def GROQ_TPM_LIMIT(self) -> int:
        return int(_optional("GROQ_TPM_LIMIT", "8000"))

    @property
    def AI_TIMEOUT(self) -> float:
        return float(_optional("AI_TIMEOUT", "60.0"))

    @property
    def AI_MAX_RETRIES(self) -> int:
        return int(_optional("AI_MAX_RETRIES", "3"))

    @property
    def AI_TEMPERATURE_MOCK(self) -> float:
        return float(_optional("AI_TEMPERATURE_MOCK", "0.5"))

    @property
    def AI_TEMPERATURE_TUTOR(self) -> float:
        return float(_optional("AI_TEMPERATURE_TUTOR", "0.3"))

    @property
    def AI_MAX_TOKENS_MOCK(self) -> int:
        return int(_optional("AI_MAX_TOKENS_MOCK", "7500"))

    @property
    def AI_MAX_TOKENS_TUTOR(self) -> int:
        return int(_optional("AI_MAX_TOKENS_TUTOR", "2048"))

    @property
    def AI_MOCK_BATCH_SIZE(self) -> int:
        return int(_optional("AI_MOCK_BATCH_SIZE", "4"))

    @property
    def AI_BATCH_DELAY(self) -> float:
        return float(_optional("AI_BATCH_DELAY", "42.0"))

    @property
    def AI_RATE_LIMIT_BACKOFF(self) -> float:
        return float(_optional("AI_RATE_LIMIT_BACKOFF", "30.0"))

    @property
    def AI_TOKEN_SAFETY_MARGIN(self) -> float:
        return float(_optional("AI_TOKEN_SAFETY_MARGIN", "0.80"))

    @property
    def AI_TOKENS_PER_QUESTION(self) -> int:
        return int(_optional("AI_TOKENS_PER_QUESTION", "1400"))

    @property
    def AI_OUTPUT_TOKEN_OVERHEAD(self) -> float:
        return float(_optional("AI_OUTPUT_TOKEN_OVERHEAD", "1.20"))

    @property
    def AI_PROMPT_TOKEN_ESTIMATE(self) -> int:
        return int(_optional("AI_PROMPT_TOKEN_ESTIMATE", "262"))

    # ── Gemini (backward compat) ──────────────────────────────────────────────
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
