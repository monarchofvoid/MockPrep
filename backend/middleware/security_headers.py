"""
VYAS v2.1 — Security Headers Middleware
==========================================
v2.1 FIX: Rewrote from BaseHTTPMiddleware to pure ASGI middleware.

ROOT CAUSE OF "Internal Server Error":
  Starlette's BaseHTTPMiddleware has a well-known bug where any unhandled
  exception raised inside a route handler is swallowed and converted to a
  plain-text "Internal Server Error" response, bypassing FastAPI's entire
  exception handling chain — including custom @app.exception_handler(),
  HTTPException handlers, and route-level try/except blocks.

  This meant every SQLAlchemy error, ValueError, or any non-HTTPException
  raised in /tutor/explain (after Groq returned successfully) was silently
  converted to a featureless 500 with no detail, making debugging impossible
  and preventing proper error messages from reaching the frontend.

  The fix is to use a pure ASGI middleware (no BaseHTTPMiddleware), which
  does NOT intercept exceptions — they propagate normally through FastAPI's
  ServerErrorMiddleware and all registered exception handlers.

Headers applied (unchanged from v2.0):
  X-Content-Type-Options:   nosniff
  X-Frame-Options:          DENY
  X-XSS-Protection:         1; mode=block
  Referrer-Policy:          strict-origin-when-cross-origin
  Permissions-Policy:       restricts dangerous browser features
  Content-Security-Policy:  production only
  Strict-Transport-Security: production only
"""

from typing import Callable
from starlette.types import ASGIApp, Receive, Scope, Send

from core.config import get_settings


class SecurityHeadersMiddleware:
    """
    Pure ASGI middleware that injects security headers into every HTTP response.

    Unlike BaseHTTPMiddleware, this implementation wraps only the ASGI
    send callable — it never intercepts exceptions, so FastAPI's error
    handling chain remains fully intact.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._settings = get_settings()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # Pass through WebSocket, lifespan, and other ASGI event types unchanged.
            await self.app(scope, receive, send)
            return

        send = self._inject_headers(send)
        await self.app(scope, receive, send)

    def _inject_headers(self, send: Send) -> Callable:
        middleware = self

        async def send_with_security_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                # Collect existing headers (list of [name_bytes, value_bytes] pairs)
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))

                # Always-on security headers
                security_headers = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy",
                     b"camera=(), microphone=(), geolocation=(), payment=()"),
                ]

                # Production-only headers
                if middleware._settings.is_production:
                    security_headers.append((
                        b"strict-transport-security",
                        b"max-age=31536000; includeSubDomains",
                    ))
                    security_headers.append((
                        b"content-security-policy",
                        (
                            b"default-src 'self'; "
                            b"script-src 'self' 'unsafe-inline'; "
                            b"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                            b"font-src 'self' https://fonts.gstatic.com; "
                            b"img-src 'self' data: https:; "
                            b"connect-src 'self' https://api.razorpay.com https://lumberjack.razorpay.com; "
                            b"script-src 'self' 'unsafe-inline' https://checkout.razorpay.com; "
                            b"frame-src https://api.razorpay.com"
                        ),
                    ))

                # Append security headers (don't overwrite existing ones from route handlers)
                existing_names = {name.lower() for name, _ in headers}
                for name, value in security_headers:
                    if name not in existing_names:
                        headers.append((name, value))

                message = {**message, "headers": headers}

            await send(message)

        return send_with_security_headers