/**
 * VYAS v2.1 — Auth Store (Zustand) for Next.js
 * ==============================================
 * Updated to match the hardened api.ts (v2.1.5):
 *
 *   WHAT CHANGED (and why):
 *   1. Import shape: api.ts no longer exports an `api` namespace object.
 *      All functions are named exports. Replaced `api.auth.*` calls with
 *      direct named imports: login(), logout(), getMe(), refreshSession(),
 *      initiateSignup(), verifySignupOTP(), resendOTP(), signup().
 *
 *   2. Token management: api.ts renamed `setToken` → `setAccessToken` and
 *      `clearAuth` → `clearAccessToken` (access token only — it does not
 *      touch the httpOnly refresh cookie). Updated all call sites.
 *      logout() still calls the server-side /auth/logout via the api function.
 *
 *   3. `AuthResponse` type removed from api.ts exports — the response type
 *      for all auth endpoints is `UserMe` (which includes `access_token?`).
 *      Replaced `AuthResponse` casts with `UserMe`.
 *
 *   WHAT IS UNCHANGED:
 *   - All store state fields and their types
 *   - All action signatures (login, signup, initiateSignup, verifyOTP, etc.)
 *   - Zustand persist shape and partialize — localStorage key and fields unchanged
 *   - All component imports of this store continue to work without changes
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import {
  // Auth functions
  login        as apiLogin,
  logout       as apiLogout,
  refreshSession,
  initiateSignup as apiInitiateSignup,
  verifySignupOTP,
  resendOTP    as apiResendOTP,
  signup       as apiSignup,

  // Token management (renamed in hardened api.ts)
  setAccessToken,
  clearAccessToken,

  // Types
  type UserMe,
} from '@/lib/api'

// ── Types ──────────────────────────────────────────────────────────────────

interface AuthState {
  user: UserMe | null
  isAuthenticated: boolean
  isLoading: boolean
  sessionChecked: boolean

  // v2.1: email address held between signup initiate and OTP verify steps
  pendingSignupEmail: string | null

  // Quick accessors (derived from user)
  walletBalanceCredits: number
  profileCompletenessPercent: number
  lowCreditWarning: boolean

  // Actions
  login: (email: string, password: string) => Promise<void>

  /** Legacy direct signup — preserved for backward compat and tests */
  signup: (name: string, email: string, password: string) => Promise<void>

  /** v2.1 Step 1: sends OTP to email, returns expires_in_seconds */
  initiateSignup: (name: string, email: string, password: string) => Promise<number>

  /** v2.1 Step 2: validates OTP, creates account, logs in */
  verifyOTP: (email: string, otp: string) => Promise<void>

  /** v2.1: resend OTP for in-progress signup */
  resendOTP: (email: string) => Promise<void>

  logout: () => Promise<void>
  refreshMe: () => Promise<void>
  updateWalletBalance: (newBalanceCredits: number) => void
  markPremiumPopupSeen: () => void
  setUser: (user: UserMe | null) => void
  setPendingSignupEmail: (email: string | null) => void
}

// ── Store ──────────────────────────────────────────────────────────────────

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      sessionChecked: false,
      pendingSignupEmail: null,
      walletBalanceCredits: 0,
      profileCompletenessPercent: 0,
      lowCreditWarning: false,

      setUser: (user) => {
        set({
          user,
          isAuthenticated: !!user,
          walletBalanceCredits: user?.wallet?.balance_credits ?? 0,
          profileCompletenessPercent: user?.profile_completeness_percent ?? 0,
          lowCreditWarning: user?.low_credit_warning ?? false,
        })
      },

      setPendingSignupEmail: (email) => set({ pendingSignupEmail: email }),

      // ── v2.1: Two-step OTP signup ────────────────────────────────────────

      initiateSignup: async (name, email, password) => {
        set({ isLoading: true })
        try {
          // FIX: was api.auth.initiateSignup — now a direct named import
          const response = await apiInitiateSignup({ name, email, password })
          set({ pendingSignupEmail: email })
          return response.expires_in_seconds
        } finally {
          set({ isLoading: false })
        }
      },

      verifyOTP: async (email, otp) => {
        set({ isLoading: true })
        try {
          // FIX: was api.auth.verifyOTP — now verifySignupOTP({ email, otp })
          // FIX: was cast to AuthResponse — UserMe already has access_token?
          const user = await verifySignupOTP({ email, otp })
          if (user.access_token) {
            // FIX: was setToken() — renamed to setAccessToken() in hardened api.ts
            setAccessToken(user.access_token)
          }
          get().setUser(user)
          set({ pendingSignupEmail: null, sessionChecked: true })
        } finally {
          set({ isLoading: false })
        }
      },

      resendOTP: async (email) => {
        // FIX: was api.auth.resendOTP — now a direct named import
        await apiResendOTP(email)
      },

      // ── Login ────────────────────────────────────────────────────────────

      login: async (email, password) => {
        set({ isLoading: true })
        try {
          // FIX: was api.auth.login — now direct import
          // FIX: was cast to AuthResponse — UserMe already has access_token?
          const user = await apiLogin({ email, password })
          if (user.access_token) {
            // FIX: was setToken() — renamed to setAccessToken()
            setAccessToken(user.access_token)
          }
          get().setUser(user)
          set({ sessionChecked: true })
        } finally {
          set({ isLoading: false })
        }
      },

      // ── Legacy direct signup (preserved) ────────────────────────────────

      signup: async (name, email, password) => {
        set({ isLoading: true })
        try {
          // FIX: was api.auth.signup — now the named apiSignup export from api.ts
          const user = await apiSignup({ name, email, password })
          if (user.access_token) {
            setAccessToken(user.access_token)
          }
          get().setUser(user)
          set({ sessionChecked: true })
        } finally {
          set({ isLoading: false })
        }
      },

      // ── Logout ───────────────────────────────────────────────────────────

      logout: async () => {
        try {
          // FIX: was api.auth.logout — now direct import
          await apiLogout()
        } catch {
          // Ignore server errors — clear local state regardless
        }
        // FIX: was clearAuth() which cleared both token + stored user.
        // Now clearAccessToken() clears only the in-memory access token.
        // The httpOnly refresh cookie is cleared server-side by apiLogout().
        clearAccessToken()
        set({
          user: null,
          isAuthenticated: false,
          walletBalanceCredits: 0,
          sessionChecked: true,
          pendingSignupEmail: null,
        })
      },

      // ── Session refresh ──────────────────────────────────────────────────

      refreshMe: async () => {
        try {
          // FIX: was api.auth.refresh + api.auth.me as separate calls.
          // refreshSession() now handles both: refreshes the httpOnly cookie,
          // sets the new access token internally, and returns UserMe.
          // If the refresh token is expired it returns null (no throw).
          const user = await refreshSession()
          if (user) {
            get().setUser(user)
          } else {
            clearAccessToken()
            set({ user: null, isAuthenticated: false })
          }
        } catch {
          clearAccessToken()
          set({ user: null, isAuthenticated: false })
        } finally {
          set({ sessionChecked: true })
        }
      },

      // ── Wallet helpers ───────────────────────────────────────────────────

      updateWalletBalance: (newBalanceCredits) => {
        set((state) => ({
          walletBalanceCredits: newBalanceCredits,
          user: state.user
            ? {
                ...state.user,
                wallet: {
                  ...(state.user.wallet ?? { balance_microcredits: 0 }),
                  balance_credits: newBalanceCredits,
                  balance_microcredits: Math.round(newBalanceCredits * 100),
                },
              }
            : null,
        }))
      },

      markPremiumPopupSeen: () => {
        set((state) => ({
          user: state.user ? { ...state.user, has_seen_premium_popup: true } : null,
        }))
      },
    }),
    {
      name: 'vyas-auth',
      // SSR-safe: only use localStorage on client
      storage: typeof window !== 'undefined'
        ? createJSONStorage(() => localStorage)
        : createJSONStorage(() => ({
            getItem: () => null,
            setItem: () => {},
            removeItem: () => {},
          })),
      // Only persist non-sensitive display data.
      // Access token is in-memory only (never persisted — by design).
      // pendingSignupEmail intentionally excluded — if the page reloads
      // mid-signup the user should start over, not land on a dangling OTP
      // screen for a potentially-expired code.
      partialize: (state) => ({
        user: state.user
          ? {
              id: state.user.id,
              name: state.user.name,
              email: state.user.email,
              has_seen_premium_popup: state.user.has_seen_premium_popup,
            }
          : null,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
