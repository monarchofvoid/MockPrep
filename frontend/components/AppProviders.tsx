/**
 * VYAS v2.0 — App Providers (Next.js)
 * ====================================
 * Client-side providers wrapper.
 *
 * Responsibilities:
 * 1. Silent session restore on every page load (calls /auth/refresh)
 * 2. Listens for vyas:session-expired event and logs out
 * 3. Restores Zustand state from localStorage
 *
 * BUG FIX (v2.0.3): Race condition — dashboard & other pages fired API calls
 * before refreshMe() finished, getting 401 for every request.
 *
 * Fix: render a neutral loading screen until sessionChecked = true.
 * sessionChecked is set by refreshMe() in its `finally` block, so it always
 * becomes true regardless of whether the refresh succeeded or failed.
 * Child pages reading `sessionChecked` from authStore can trust that the
 * access token (if any) is already in memory before they fire their fetches.
 */

'use client'

import { useEffect } from 'react'
import { useAuthStore } from '@/stores/authStore'

export function AppProviders({ children }: { children: React.ReactNode }) {
  const refreshMe      = useAuthStore((s) => s.refreshMe)
  const logout         = useAuthStore((s) => s.logout)
  const sessionChecked = useAuthStore((s) => s.sessionChecked)

  // Silent session restore on mount — sets sessionChecked when done
  useEffect(() => {
    refreshMe()
  }, [refreshMe])

  // Listen for session-expired events (emitted by api.ts on refresh failure)
  useEffect(() => {
    const handler = () => logout()
    window.addEventListener('vyas:session-expired', handler)
    return () => window.removeEventListener('vyas:session-expired', handler)
  }, [logout])

  // Block rendering until we know whether the user has a valid session.
  // This prevents child pages from firing authenticated API calls before
  // the access token is restored from the refresh cookie.
  // The spinner is shown for ~200-400 ms on a local dev server.
  if (!sessionChecked) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg, #0a0a0a)',
        }}
      >
        <svg
          width="40"
          height="40"
          viewBox="0 0 40 40"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          style={{ animation: 'spin 0.9s linear infinite' }}
        >
          <circle cx="20" cy="20" r="17" stroke="#2a2a2a" strokeWidth="4" />
          <path
            d="M20 3 A17 17 0 0 1 37 20"
            stroke="#c9a84c"
            strokeWidth="4"
            strokeLinecap="round"
          />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </svg>
      </div>
    )
  }

  return <>{children}</>
}