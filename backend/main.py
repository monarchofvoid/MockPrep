"""
VYAS v2.2.0 — Main Application
================================
v2.2.0 Migration: Celery → APScheduler + AsyncIO + FastAPI BackgroundTasks

Changes from v2.1.5:
  1. Removed: `import celery_app as _celery_module` (Celery registration side-effect)
  2. Removed: Celery broker log line in lifespan
  3. Added: APScheduler startup/shutdown in lifespan context manager
  4. Added: app.state.scheduler for testability
  5. SCHEDULER_ENABLED setting allows disabling scheduler in tests

All security hardening, middleware, routers, and exception handlers from
v2.1.5 are fully preserved and unchanged.

Production hardening preserved from v2.1.5:
  SECURITY FIXES:
    1. 500 responses no longer leak exception class names or stack traces to clients.
    2. VYASBaseException handler maps each subtype to the correct HTTP status code.
    3. BodySizeLimitMiddleware handles chunked transfer encoding.
    4. X-Forwarded-For sanitized against header injection.
    5. Docs/ReDoc disabled in production.
  DEFENSIVE PROGRAMMING:
    6. DB health-check logs the specific error without raising.
    7. Redis health check result is logged at WARNING.
"""

import json
import logging
import sys
import time
import traceback
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings
from logging_config import configure_logging

settings = get_settings()
configure_logging(settings)

from core.redis import ping_redis                                   # noqa: E402
from middleware.security_headers import SecurityHeadersMiddleware   # noqa: E402

logger = logging.getLogger("vyas.main")

# ── Sentry (production only) ──────────────────────────────────────────────────
if settings.SENTRY_DSN and settings.is_production:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            environment=settings.ENVIRONMENT,
            release=f"vyas@{settings.APP_VERSION}",
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        )
        logger.info("Sentry initialized: env=%s", settings.ENVIRONMENT)
    except ImportError:
        logger.warning("sentry-sdk not installed — Sentry disabled")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings)

    print(
        ">>> [VYAS] lifespan started — logging handler count: "
        + str(len(logging.getLogger().handlers)),
        flush=True,
    )

    scheduler = None

    try:
        logger.info(
            "VYAS v%s starting — env=%s log_level=%s",
            settings.APP_VERSION, settings.ENVIRONMENT, settings.LOG_LEVEL,
        )

        # Redis health check — warn but do not crash startup on failure
        if ping_redis():
            logger.info("✓ Redis OK")
        else:
            logger.warning(
                "✗ Redis unreachable at %s — start with: redis-server", settings.REDIS_URL
            )

        # DB health check — warn but do not crash startup on failure
        try:
            from database import engine
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✓ Database OK")
        except Exception as exc:
            # DEFENSIVE: log the specific error; do not re-raise.
            # A brief DB hiccup at startup should not prevent the server from
            # accepting requests that don't need the DB.
            logger.error("✗ Database health check FAILED (server will still start): %s", exc)

        # ── APScheduler startup ───────────────────────────────────────────────
        # Replaces Celery Beat + RedBeat.
        # Scheduler is disabled in test environments (SCHEDULER_ENABLED=False)
        # to prevent interference with test isolation.
        if settings.SCHEDULER_ENABLED:
            try:
                from scheduler.setup import create_scheduler, register_jobs

                scheduler = create_scheduler(settings.REDIS_URL)
                register_jobs(scheduler)
                scheduler.start()

                # Store on app.state for testability (e.g. app.state.scheduler.get_jobs())
                app.state.scheduler = scheduler

                logger.info(
                    "✓ APScheduler started with %d jobs: %s",
                    len(scheduler.get_jobs()),
                    [j.id for j in scheduler.get_jobs()],
                )
            except Exception as exc:
                # Scheduler failure is non-fatal: the API continues serving
                # requests. The cleanup_stale_jobs safety net will be unavailable
                # until the next restart, but AI generation still works.
                logger.error(
                    "✗ APScheduler failed to start (API will still serve requests): %s",
                    exc, exc_info=True,
                )
                scheduler = None
        else:
            logger.info("APScheduler disabled (SCHEDULER_ENABLED=False)")
            app.state.scheduler = None

        logger.info("✓ VYAS startup complete")

    except Exception:
        print(
            ">>> [VYAS] LIFESPAN STARTUP CRASHED:\n" + traceback.format_exc(),
            flush=True,
        )
        raise

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("VYAS shutting down")

    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
            logger.info("✓ APScheduler stopped")
        except Exception as exc:
            logger.warning("APScheduler shutdown error (non-fatal): %s", exc)


# ── App Factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="VYAS API",
        version=settings.APP_VERSION,
        lifespan=lifespan,
        # Disable interactive docs in production — they expose your entire API surface
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        # Also disable the OpenAPI schema endpoint in production
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # ── Body size limit ───────────────────────────────────────────────────────
    _MAX_BODY = 1 * 1024 * 1024  # 1 MB

    class BodySizeLimitMiddleware:
        """
        Reject requests whose body exceeds MAX_BODY bytes.

        Handles both:
          - Content-Length header present: reject before reading body (fast path)
          - Chunked / no Content-Length: stream and cut off after MAX_BODY bytes
        """
        def __init__(self, app):
            self._app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self._app(scope, receive, send)
                return

            headers = {k.lower(): v for k, v in scope.get("headers", [])}

            # Fast path: Content-Length header present
            cl = headers.get(b"content-length")
            if cl:
                try:
                    if int(cl) > _MAX_BODY:
                        body = json.dumps({"error": "request_too_large"}).encode()
                        await send({"type": "http.response.start", "status": 413,
                                    "headers": [(b"content-type", b"application/json")]})
                        await send({"type": "http.response.body", "body": body})
                        return
                except (ValueError, TypeError):
                    pass

            # Streaming path: enforce limit while reading chunked body
            total_read = 0
            body_too_large = False

            async def limited_receive():
                nonlocal total_read, body_too_large
                message = await receive()
                if message["type"] == "http.request":
                    chunk = message.get("body", b"")
                    total_read += len(chunk)
                    if total_read > _MAX_BODY:
                        body_too_large = True
                        # Return empty body to signal termination
                        return {"type": "http.request", "body": b"", "more_body": False}
                return message

            async def checked_send(msg):
                if body_too_large and msg["type"] == "http.response.start":
                    # Override to 413 if body overflow was detected during read
                    body = json.dumps({"error": "request_too_large"}).encode()
                    await send({"type": "http.response.start", "status": 413,
                                "headers": [(b"content-type", b"application/json")]})
                    await send({"type": "http.response.body", "body": body})
                    return
                await send(msg)

            await self._app(scope, limited_receive, checked_send)

    app.add_middleware(BodySizeLimitMiddleware)

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS_LIST,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept",
                       "Origin", "X-Requested-With", "X-Request-Id"],
        expose_headers=["X-Request-Id", "Retry-After", "X-Response-Time"],
    )

    app.add_middleware(SecurityHeadersMiddleware)

    # ── Request logging ───────────────────────────────────────────────────────
    _SKIP = {"/health", "/favicon.ico"}

    class RequestLoggingMiddleware:
        def __init__(self, app):
            self._app = app
            self._log = logging.getLogger("vyas.requests")

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self._app(scope, receive, send)
                return

            rid   = str(uuid.uuid4())[:8]
            path  = scope.get("path", "?")
            meth  = scope.get("method", "?")
            start = time.perf_counter()

            hdr = {k.lower(): v.decode(errors="replace") for k, v in scope.get("headers", [])}

            # SECURITY: sanitize X-Forwarded-For — take only the first IP and
            # strip any control characters or unexpected content to prevent
            # log injection attacks.
            raw_xff = hdr.get("x-forwarded-for", "")
            first_xff = raw_xff.split(",")[0].strip()
            # Sanitize: keep only printable ASCII characters safe for logs
            ip = "".join(c for c in first_xff if c.isprintable() and c not in "\r\n")
            if not ip:
                ip = (scope.get("client") or ("?", 0))[0]

            async def _send(msg):
                if msg["type"] == "http.response.start":
                    ms     = int((time.perf_counter() - start) * 1000)
                    status = msg["status"]
                    hdrs   = list(msg.get("headers", []))
                    hdrs.append((b"x-request-id",    rid.encode()))
                    hdrs.append((b"x-response-time", f"{ms}ms".encode()))
                    msg = {**msg, "headers": hdrs}
                    if path not in _SKIP:
                        fn = self._log.warning if status >= 400 else self._log.info
                        fn("%s %s %d %dms ip=%s req=%s", meth, path, status, ms, ip, rid)
                await send(msg)

            await self._app(scope, receive, _send)

    app.add_middleware(RequestLoggingMiddleware)

    # ── Exception handlers ────────────────────────────────────────────────────
    from core.exceptions import (
        AIJobAlreadyActiveError,
        AIJobNotFoundError,
        DuplicateWebhookError,
        InsufficientCreditsError,
        InvalidPaymentSignatureError,
        PaymentNotFoundError,
        ProfileIncompleteError,
        VYASBaseException,
        WalletLockError,
        WalletNotFoundError,
    )

    @app.exception_handler(InsufficientCreditsError)
    async def _insufficient(request: Request, exc: InsufficientCreditsError):
        logger.warning("InsufficientCredits: %s %s", request.url.path, exc.message)
        return JSONResponse(
            status_code=402,
            content={"error": "insufficient_credits", "message": exc.message, **exc.details},
        )

    @app.exception_handler(WalletLockError)
    async def _wallet_lock(request: Request, exc: WalletLockError):
        logger.warning("WalletLock: %s user_id=%s", request.url.path, exc.details.get("user_id"))
        return JSONResponse(
            status_code=429,
            content={"error": "wallet_locked", "message": exc.message},
            headers={"Retry-After": "1"},
        )

    @app.exception_handler(WalletNotFoundError)
    async def _wallet_not_found(request: Request, exc: WalletNotFoundError):
        logger.error("WalletNotFound: %s user_id=%s", request.url.path, exc.details.get("user_id"))
        return JSONResponse(
            status_code=404,
            content={"error": "wallet_not_found", "message": exc.message},
        )

    @app.exception_handler(AIJobNotFoundError)
    async def _ai_job_not_found(request: Request, exc: AIJobNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "ai_job_not_found", "message": exc.message},
        )

    @app.exception_handler(AIJobAlreadyActiveError)
    async def _ai_job_active(request: Request, exc: AIJobAlreadyActiveError):
        return JSONResponse(
            status_code=400,
            content={
                "error": "active_job_exists",
                "message": exc.message,
                "existing_job_id": exc.details.get("existing_job_id"),
            },
        )

    @app.exception_handler(ProfileIncompleteError)
    async def _profile_incomplete(request: Request, exc: ProfileIncompleteError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "profile_incomplete",
                "message": exc.message,
                "missing_fields": exc.details.get("missing_fields", []),
            },
        )

    @app.exception_handler(DuplicateWebhookError)
    async def _duplicate_webhook(request: Request, exc: DuplicateWebhookError):
        # Return 200 so Razorpay stops retrying
        return JSONResponse(
            status_code=200,
            content={"status": "already_processed"},
        )

    @app.exception_handler(InvalidPaymentSignatureError)
    async def _invalid_sig(request: Request, exc: InvalidPaymentSignatureError):
        logger.warning("InvalidPaymentSignature: %s", request.url.path)
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_signature", "message": exc.message},
        )

    @app.exception_handler(PaymentNotFoundError)
    async def _payment_not_found(request: Request, exc: PaymentNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "payment_not_found", "message": exc.message},
        )

    @app.exception_handler(VYASBaseException)
    async def _vyas_exc(request: Request, exc: VYASBaseException):
        # Catch-all for any VYASBaseException subtype not handled above
        logger.warning("VYASException [%s] %s", type(exc).__name__, request.url.path)
        return JSONResponse(
            status_code=400,
            content={"error": "application_error", "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # SECURITY: Log full traceback internally but never expose it to the client.
        # The response body contains only a generic message — no class names,
        # no stack traces, no internal paths.
        logger.error(
            "UNHANDLED [%s] %s %s\n%s",
            type(exc).__name__, request.method, request.url.path,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error",
                     "message": "An unexpected error occurred. Please try again later."},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    logger.info("Loading core routers...")

    from routers.auth import router as auth_router
    app.include_router(auth_router)
    logger.info("  ✓ auth router")

    from routers.password_reset import router as password_reset_router
    app.include_router(password_reset_router)
    logger.info("  ✓ password_reset router")

    from routers.payments import router as payments_router
    app.include_router(payments_router)
    logger.info("  ✓ payments router")

    from routers.wallet import router as wallet_router
    app.include_router(wallet_router)
    logger.info("  ✓ wallet router")

    from routers.ai_mock import router as ai_mock_router, ai_jobs_router
    app.include_router(ai_mock_router)
    app.include_router(ai_jobs_router)
    logger.info("  ✓ ai_mock + ai_jobs routers")

    from routers.contact import router as contact_router
    app.include_router(contact_router)
    logger.info("  ✓ contact router")

    try:
        from routers.oauth import router as oauth_router
        app.include_router(oauth_router)
        logger.info("  ✓ oauth router")
    except ImportError as exc:
        logger.warning("  ✗ oauth router: %s", exc)

    _register_routers(app)

    @app.get("/health", tags=["System"])
    async def health():
        ok = ping_redis()
        return {"status": "healthy" if ok else "degraded",
                "version": settings.APP_VERSION, "redis": "ok" if ok else "unavailable"}

    return app


def _register_routers(app: FastAPI) -> None:
    for mod, attr, name in [
        ("routers.profile",         "router", "Profile"),
        ("routers.mock_tests",      "router", "Mock tests"),
        ("routers.attempts",        "router", "Attempts"),
        ("routers.analytics",       "router", "Analytics"),
        ("routers.tutor",           "router", "Tutor"),
        ("routers.recommendations", "router", "Recommendations"),
    ]:
        try:
            import importlib
            m = importlib.import_module(mod)
            app.include_router(getattr(m, attr))
            logger.info("  ✓ %s router", name)
        except ImportError as exc:
            logger.warning("  ✗ %s skipped: %s", name, exc)
        except Exception as exc:
            logger.error("  ✗ %s FAILED: %s", name, exc, exc_info=True)


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000,
                reload=not settings.is_production,
                log_level=settings.LOG_LEVEL.lower())