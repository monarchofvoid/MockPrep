/**
 * VYAS v2.0 — Next.js Middleware
 * ================================
 * Route protection for authenticated pages.
 *
 * BUG-003 FIX: Cookie name was 'refresh_token' but backend sets 'vyas_refresh'.
 * This mismatch caused every authenticated user to be redirected to the landing
 * page on every protected route load, because the middleware never found the
 * cookie it was checking for. Auth was completely broken at the route-protection
 * layer despite the backend setting the cookie correctly.
 *
 * How it works:
 * 1. Checks for refresh token cookie named 'vyas_refresh' (httpOnly, not readable by JS)
 * 2. If missing → redirects to / (landing page), preserving intended destination
 * 3. If present → allows access (AppProviders will call /auth/refresh to verify)
 *
 * Note: The cookie name is defined in backend/core/config.py as:
 *   REFRESH_TOKEN_COOKIE_NAME = "vyas_refresh"
 * It must match exactly here. If you ever change the backend cookie name,
 * update NEXT_PUBLIC_REFRESH_COOKIE_NAME in your .env.local and use it here.
 *
 * Protected routes:
 * - /dashboard
 * - /mocks
 * - /test/:attemptId
 * - /results/:attemptId
 * - /ai-mock
 * - /profile
 * - /wallet
 * - /purchase
 */

import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Cookie name must match backend/core/config.py: REFRESH_TOKEN_COOKIE_NAME = "vyas_refresh"
const REFRESH_COOKIE_NAME = process.env.NEXT_PUBLIC_REFRESH_COOKIE_NAME || 'vyas_refresh'

export function middleware(request: NextRequest) {
  // Allow /auth/* routes through without cookie check.
  // The OAuth callback page (/auth/oauth/google/callback) must be reachable
  // before the refresh cookie is readable cross-origin.
  if (request.nextUrl.pathname.startsWith('/auth/')) {
    return NextResponse.next()
  }

  const refreshToken = request.cookies.get(REFRESH_COOKIE_NAME)

  if (!refreshToken) {
    const url = request.nextUrl.clone()
    url.pathname = '/'
    url.searchParams.set('from', request.nextUrl.pathname)
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/mocks/:path*',
    '/test/:path*',
    '/results/:path*',
    '/ai-mock/:path*',
    '/profile/:path*',
    '/wallet/:path*',
    '/purchase/:path*',
  ],
}