"""
VYAS v2.0 — Security Headers Middleware
==========================================
Adds production-standard security headers to every response.

Headers applied:
  X-Content-Type-Options:   nosniff (prevent MIME sniffing)
  X-Frame-Options:          DENY (prevent clickjacking)
  X-XSS-Protection:         1; mode=block (legacy browser protection)
  Referrer-Policy:          strict-origin-when-cross-origin
  Permissions-Policy:       restricts dangerous browser features
  Content-Security-Policy:  restricts sources in production
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import AppConfig


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        if AppConfig.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self'"
            )

        return response
