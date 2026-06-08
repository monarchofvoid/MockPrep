/**
 * VYAS v2.0 — Next.js Middleware
 * ================================
 * Route protection for authenticated pages.
 *
 * PRODUCTION FIX: The previous middleware checked for the `vyas_refresh`
 * httpOnly cookie on the incoming request to vyasmock.online. This worked
 * locally because frontend and backend shared the same origin (localhost).
 *
 * In production the backend runs on api.vyasmock.online and the frontend on
 * vyasmock.online — two different subdomains. The browser only sends the
 * cookie back to api.vyasmock.online requests, not to vyasmock.online page
 * requests. So the middleware edge function never saw the cookie and always
 * redirected to /, even for fully authenticated users.
 *
 * Fix: Remove the cookie check from middleware entirely. Auth protection is
 * handled client-side by AppProviders, which calls refreshSession() on every
 * page load. If the session is invalid, AppProviders redirects to /.
 * Protected pages show a loading spinner while the session check runs —
 * this is already implemented and working in the existing AppProviders.
 *
 * Only /auth/* pass-through is kept (required for the OAuth callback route).
 */

import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  // Always allow /auth/* routes through — the OAuth callback page must be
  // reachable before any session is established.
  if (request.nextUrl.pathname.startsWith('/auth/')) {
    return NextResponse.next()
  }

  // Pass all other routes through — auth is enforced client-side by
  // AppProviders via the /auth/refresh endpoint.
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