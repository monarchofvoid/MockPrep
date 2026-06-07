'use client'

/**
 * VYAS v2.2.0 — Google OAuth Callback Handler
 * =============================================
 * This page receives the OAuth redirect from the backend and bootstraps
 * the auth session before handing off to /dashboard.
 *
 * WHY THIS PAGE EXISTS:
 * The backend OAuth callback sets the httpOnly refresh cookie and redirects
 * here with the short-lived access_token in the URL. Without storing the
 * access_token in memory first, the dashboard's useEffect sees
 * isAuthenticated=false (auth store is empty) and immediately kicks the
 * user back to the landing page — before AppProviders can call /auth/refresh.
 *
 * FLOW:
 *   1. Backend redirects → /auth/oauth/google/callback?access_token=eyJ...
 *   2. This page reads access_token from URL search params
 *   3. Calls setAccessToken() to store it in memory (same as normal login)
 *   4. Calls refreshSession() → GET /auth/refresh → returns UserMe
 *   5. Populates auth store (setUser, sessionChecked=true)
 *   6. router.replace('/dashboard') — replaces URL so token is gone from history
 *
 * If the token is missing or refreshSession fails, redirects to /?error=oauth_failed.
 *
 * The middleware.ts allows /auth/* routes through without cookie check,
 * so no redirect loop occurs even though the cookie may not be readable
 * cross-origin on the first request.
 */

import { useEffect, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { setAccessToken, refreshSession } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'

export default function GoogleOAuthCallback() {
  const router      = useRouter()
  const params      = useSearchParams()
  const { setUser } = useAuthStore()
  const didRun      = useRef(false)

  useEffect(() => {
    // Strict mode runs effects twice in dev — guard with ref
    if (didRun.current) return
    didRun.current = true

    const accessToken = params.get('access_token')

    if (!accessToken) {
      console.error('[OAuth] No access_token in callback URL')
      router.replace('/?error=oauth_failed')
    }

    ;(async () => {
      try {
        // 1. Store access token in memory exactly as login() does
        setAccessToken(accessToken)

        // 2. Refresh session — verifies the httpOnly cookie and returns UserMe
        //    This populates wallet, profile, credits etc.
        const user = await refreshSession()

        if (!user) {
          throw new Error('refreshSession returned null — refresh cookie missing or expired')
        }

        // 3. Populate auth store
        setUser(user)
        useAuthStore.setState({ sessionChecked: true, isAuthenticated: true })

        // 4. Replace URL (removes access_token from browser history) and go to dashboard
        router.replace('/dashboard')

      } catch (err) {
        console.error('[OAuth] Session bootstrap failed:', err)
        router.replace('/?error=oauth_failed')
      }
    })()
  }, [params, router, setUser])

  // Show a brief loading state — this page is visible for <500ms typically
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      background: '#0a0a0a',
      color: '#d4a843',
      fontFamily: 'sans-serif',
      gap: '16px',
    }}>
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <circle cx="16" cy="16" r="14" stroke="#d4a843" strokeWidth="2" opacity="0.3"/>
        <path d="M16 2 A14 14 0 0 1 30 16" stroke="#d4a843" strokeWidth="2" strokeLinecap="round">
          <animateTransform
            attributeName="transform"
            type="rotate"
            from="0 16 16"
            to="360 16 16"
            dur="0.8s"
            repeatCount="indefinite"
          />
        </path>
      </svg>
      <span style={{ fontSize: '14px', opacity: 0.7 }}>Signing you in…</span>
    </div>
  )
}