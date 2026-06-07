"""
VYAS v2.2.0 — Application Configuration
==========================================
v2.2.0 Changes (Celery → APScheduler migration):
  - Removed: CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TASK_SERIALIZER,
             CELERY_RESULT_SERIALIZER, CELERY_ACCEPT_CONTENT, CELERY_WORKER_CONCURRENCY
  - Added:   SCHEDULER_ENABLED (bool) — allows disabling APScheduler in tests
  - Renamed: CELERY_TASK_SOFT_TIME_LIMIT → AI_TASK_TIMEOUT (compat alias provided)
             CELERY_TASK_TIME_LIMIT      → AI_TASK_HARD_TIMEOUT (compat alias provided)

All other settings are unchanged from v2.1.5.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    APP_NAME: str = "VYAS"
    APP_VERSION: str = "2.2.0"
    DEBUG: bool = True

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    # ── Auth — Access Tokens ─────────────────────────────────────────────────
    SECRET_KEY: str = "vyas-insecure-dev-only-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # ── Auth — Refresh Tokens ────────────────────────────────────────────────
    REFRESH_SECRET_KEY: str = "vyas-refresh-insecure-dev-only"
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_COOKIE_NAME: str = "vyas_refresh"
    REFRESH_TOKEN_COOKIE_SECURE: bool = False
    REFRESH_TOKEN_COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: Optional[str] = None

    # ── Auth — Brute Force Protection ────────────────────────────────────────
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # ── Google OAuth ─────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/oauth/google/callback"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./vyas_dev.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    @field_validator("DATABASE_URL")
    @classmethod
    def warn_sqlite(cls, v: str) -> str:
        if v.startswith("sqlite"):
            import warnings
            warnings.warn(
                "[VYAS] SQLite detected — FOR DEV ONLY. Use PostgreSQL in production.",
                stacklevel=2,
            )
        return v

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_DB: int = 0
    REDIS_JOB_TTL: int = 86400

    # ── APScheduler ──────────────────────────────────────────────────────────
    # Set SCHEDULER_ENABLED=False in test environments (prevents scheduler from
    # starting and interfering with test isolation or Redis state).
    SCHEDULER_ENABLED: bool = True

    # ── AI Task Timeouts ─────────────────────────────────────────────────────
    # Previously named CELERY_TASK_SOFT_TIME_LIMIT / CELERY_TASK_TIME_LIMIT.
    # Backward-compat properties provided below for any code that uses the old names.
    AI_TASK_TIMEOUT: int = 600       # seconds — soft timeout for asyncio AI task
    AI_TASK_HARD_TIMEOUT: int = 720  # seconds — hard timeout for asyncio AI task

    @property
    def CELERY_TASK_TIME_LIMIT(self) -> int:
        """Backward-compat alias for AI_TASK_HARD_TIMEOUT."""
        return self.AI_TASK_HARD_TIMEOUT

    @property
    def CELERY_TASK_SOFT_TIME_LIMIT(self) -> int:
        """Backward-compat alias for AI_TASK_TIMEOUT."""
        return self.AI_TASK_TIMEOUT

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def ALLOWED_ORIGINS_LIST(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── Question Bank ────────────────────────────────────────────────────────
    QB_ROOT: Optional[str] = None

    @property
    def QB_ROOT_PATH(self) -> Path:
        if self.QB_ROOT:
            return Path(self.QB_ROOT)
        return Path(__file__).parent.parent / "question_bank"

    # ── Groq / AI ────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_TPM_LIMIT: int = 8000
    AI_TIMEOUT: float = 90.0
    AI_MAX_RETRIES: int = 3
    AI_TEMPERATURE_MOCK: float = 0.5
    AI_TEMPERATURE_TUTOR: float = 0.3
    AI_MAX_TOKENS_MOCK: int = 7500
    AI_MAX_TOKENS_TUTOR: int = 2048
    AI_MOCK_BATCH_SIZE: int = 3
    AI_BATCH_DELAY: float = 22.0
    AI_RATE_LIMIT_BACKOFF: float = 30.0
    AI_TOKEN_SAFETY_MARGIN: float = 0.80
    AI_TOKENS_PER_QUESTION: int = 600
    AI_OUTPUT_TOKEN_OVERHEAD: float = 1.20
    AI_PROMPT_TOKEN_ESTIMATE: int = 350

    # ── Gemini (legacy) ───────────────────────────────────────────────────────
    GEMINI_API_KEY_TUTOR: str = ""
    GEMINI_API_KEY_MOCK: str = ""
    GEMINI_MODEL_TUTOR: str = "gemini-2.0-flash"
    GEMINI_MODEL_MOCK: str = "gemini-2.0-flash"

    # ── Razorpay Payments ────────────────────────────────────────────────────
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RAZORPAY_CURRENCY: str = "INR"

    # ── Wallet / Credit System ───────────────────────────────────────────────
    SIGNUP_BONUS_MICROCREDITS: int = 500
    MICROCREDITS_PER_CREDIT: int = 100
    COST_PER_QUESTION_MICROCREDITS: int = 15
    COST_TUTOR_EXPLAIN_MICROCREDITS: int = 50
    LOW_CREDIT_WARN_MICROCREDITS: int = 150

    # ── Email (Brevo) ────────────────────────────────────────────────────────
    BREVO_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@vyas.app"
    OWNER_EMAIL: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_AI_REQUESTS: int = 5
    RATE_LIMIT_AI_WINDOW: int = 3600
    RATE_LIMIT_AUTH_REQUESTS: int = 10
    RATE_LIMIT_AUTH_WINDOW: int = 60
    RATE_LIMIT_PAYMENT_REQUESTS: int = 20
    RATE_LIMIT_PAYMENT_WINDOW: int = 60

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: str = ""

    # ── Sentry ───────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # ── Production Safety Validators ─────────────────────────────────────────
    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        # BUG-GUARD: Prevent the "OAuth/login always goes back to landing page"
        # failure mode in local development.
        #
        # Root cause: when REFRESH_TOKEN_COOKIE_SECURE=True but the server is
        # running on plain HTTP (localhost), browsers silently discard the Set-Cookie
        # header. The refresh cookie is never saved, so:
        #   • Email/password login: the /auth/refresh call on the next page load
        #     finds no cookie → user is not authenticated.
        #   • Google OAuth: the callback page calls refreshSession() immediately
        #     after redirect, the cookie is gone, refreshSession() returns null,
        #     and router.replace('/login?error=oauth_failed') fires.
        #
        # Fix: in non-production environments, force REFRESH_TOKEN_COOKIE_SECURE
        # to False and log a prominent warning so developers know what happened
        # instead of debugging silently broken auth for hours.
        if not self.is_production and self.REFRESH_TOKEN_COOKIE_SECURE:
            import warnings
            warnings.warn(
                "[VYAS] REFRESH_TOKEN_COOKIE_SECURE is True but ENVIRONMENT is not "
                "'production'. Cookies with Secure=True are silently dropped by "
                "browsers on plain HTTP (localhost). Forcing REFRESH_TOKEN_COOKIE_SECURE "
                "= False for local development. Set ENVIRONMENT=production to allow "
                "Secure cookies.",
                stacklevel=2,
            )
            # Pydantic Settings fields are frozen after init, so we use object.__setattr__
            object.__setattr__(self, "REFRESH_TOKEN_COOKIE_SECURE", False)

        if self.is_production:
            if self.SECRET_KEY == "vyas-insecure-dev-only-change-in-production":
                raise ValueError("SECRET_KEY must be changed in production!")
            if self.REFRESH_SECRET_KEY == "vyas-refresh-insecure-dev-only":
                raise ValueError("REFRESH_SECRET_KEY must be changed in production!")
            if self.ACCESS_TOKEN_EXPIRE_MINUTES > 30:
                raise ValueError(
                    f"ACCESS_TOKEN_EXPIRE_MINUTES cannot exceed 30 in production! "
                    f"Current value: {self.ACCESS_TOKEN_EXPIRE_MINUTES}."
                )
            if not self.RAZORPAY_KEY_ID:
                import warnings
                warnings.warn("[VYAS] RAZORPAY_KEY_ID not set in production", stacklevel=2)
            if self.RAZORPAY_WEBHOOK_SECRET in ("", "your_webhook_secret"):
                raise ValueError(
                    "RAZORPAY_WEBHOOK_SECRET must be set to the actual Razorpay webhook "
                    "secret in production."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance. Use this everywhere instead of instantiating Settings()."""
    return Settings()


AppConfig = get_settings()