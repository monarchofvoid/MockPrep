"""
VYAS v0.11 — Environment Configuration & Validation
=====================================================
Single source of truth for all env variables.
Import AppConfig from here instead of reading os.getenv() scattered everywhere.

Usage:
    from config import AppConfig
    print(AppConfig.GROQ_API_KEY)

v0.11 changes (413 / TPM fix):
  ROOT CAUSE: Groq counts (input_tokens + max_tokens_param) against the TPM
  limit, NOT just output tokens. Sending max_tokens=16384 per batch consumed
  16,646 "requested" tokens — more than double the 8,000 TPM ceiling → 413.

  FIX: max_tokens is now computed *dynamically per batch* in the service layer
  as (batch_count × AI_TOKENS_PER_QUESTION × AI_OUTPUT_TOKEN_OVERHEAD).
  AI_MAX_TOKENS_MOCK is now a hard upper-cap / fallback only.

  New knobs added:
    GROQ_TPM_LIMIT            — your plan's TPM ceiling (default 8000)
    AI_PROMPT_TOKEN_ESTIMATE  — estimated input tokens per batch prompt (~350)
    AI_OUTPUT_TOKEN_OVERHEAD  — multiplier on top of per-question estimate (1.20)

  Tuning defaults adjusted:
    AI_MOCK_BATCH_SIZE  3  → 3 × 600 × 1.20 + 350 = 2,510 tokens per batch
    AI_BATCH_DELAY     22  → ≥ (2510/8000)×60 s  = 18.8 s minimum; 22 s safe
    AI_MAX_TOKENS_MOCK 7500 → hard cap (< 8000 TPM floor, safety net only)

v0.8 changes:
  - Added Groq AI provider settings (GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL)
  - Added provider-agnostic AI tuning knobs.
  - Kept all Gemini settings for backward compatibility during transition.
"""

import os
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

    @property
    def GROQ_TPM_LIMIT(self) -> int:
        # v0.11: your Groq plan's Tokens Per Minute ceiling.
        # Groq counts (input_tokens + max_tokens_param) against this limit.
        # Free tier = 8000. Dev/paid tiers are higher — raise accordingly.
        return int(_optional("GROQ_TPM_LIMIT", "8000"))

    # ── Provider-agnostic AI tuning knobs ─────────────────────────────────────
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
        # v0.11: This is now a HARD CAP / SAFETY NET only.
        # The service layer computes a tighter dynamic value per batch.
        # Must stay below GROQ_TPM_LIMIT - AI_PROMPT_TOKEN_ESTIMATE (≈ 7500).
        return int(_optional("AI_MAX_TOKENS_MOCK", "7500"))

    @property
    def AI_MAX_TOKENS_TUTOR(self) -> int:
        return int(_optional("AI_MAX_TOKENS_TUTOR", "2048"))

    @property
    def AI_MOCK_BATCH_SIZE(self) -> int:
        # v0.11: lowered from 5 → 3.
        # Per-batch token budget: 3 × 600 × 1.20 + 350 input ≈ 2 510 tokens.
        # 2 510 < 8 000 TPM limit → no more 413 errors.
        # Raising this above 5 will likely exceed the 8 000 TPM ceiling again.
        return int(_optional("AI_MOCK_BATCH_SIZE", "4"))

    @property
    def AI_BATCH_DELAY(self) -> float:
        # v0.11: raised from 2.0 → 22.0 seconds.
        # Minimum safe delay = (2510 / 8000) × 60 = 18.8 s.
        # 22 s adds a 17% safety margin on top of that.
        # Formula if you tune this yourself:
        #   delay = ((batch_size × TPQ × overhead + prompt_est) / TPM_limit) × 60 × 1.2
        return float(_optional("AI_BATCH_DELAY", "42.0"))

    @property
    def AI_RATE_LIMIT_BACKOFF(self) -> float:
        # Base backoff seconds when Groq returns HTTP 429.
        # Actual wait = AI_RATE_LIMIT_BACKOFF * (attempt + 1).
        return float(_optional("AI_RATE_LIMIT_BACKOFF", "30.0"))

    @property
    def AI_TOKEN_SAFETY_MARGIN(self) -> float:
        return float(_optional("AI_TOKEN_SAFETY_MARGIN", "0.80"))

    @property
    def AI_TOKENS_PER_QUESTION(self) -> int:
        # Estimated *output* tokens per generated question.
        # JEE Math/Physics full explanation: 500-700. CUET/simpler: 300-450.
        return int(_optional("AI_TOKENS_PER_QUESTION", "1400"))

    @property
    def AI_OUTPUT_TOKEN_OVERHEAD(self) -> float:
        # v0.11: multiplier applied to (batch_count × AI_TOKENS_PER_QUESTION)
        # when computing the dynamic max_tokens to send in the API request.
        # 1.20 = 20% buffer above the per-question estimate.
        return float(_optional("AI_OUTPUT_TOKEN_OVERHEAD", "1.20"))

    @property
    def AI_PROMPT_TOKEN_ESTIMATE(self) -> int:
        # v0.11: estimated input tokens consumed by the system + user prompt
        # per batch. Used in pre-flight budget check and delay calculation.
        # 350 is a conservative upper bound; actual is typically ~250-300.
        return int(_optional("AI_PROMPT_TOKEN_ESTIMATE", "262"))

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
