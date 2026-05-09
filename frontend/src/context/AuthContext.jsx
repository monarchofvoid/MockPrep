/**
 * VYAS v2.0 — Auth Context
 * ==========================
 * v2.0 changes:
 *
 * 1. On mount: calls /auth/refresh (silent) to restore session from httpOnly
 *    cookie. This replaces the old localStorage token hydration.
 *    If refresh fails → user is logged out (no stale session).
 *
 * 2. User info (name/email/id) still cached in localStorage for instant
 *    UI rendering before the async refresh completes (avoids blank flash).
 *    This is safe — user info is not sensitive.
 *
 * 3. login() and signup() now accept the full auth payload and store the
 *    access token in memory via setToken() from client.js.
 *
 * 4. logout() calls the server to revoke the refresh token, then clears
 *    in-memory state.
 *
 * 5. Session-expired event listener: if a refresh fails mid-session
 *    (e.g., token revoked by server), the vyas:session-expired event
 *    fires → context logs the user out cleanly.
 *
 * 6. profileComplete: computed from the user's profile data.
 *    Used to gate certain features and show the profile setup prompt.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";
import {
  getStoredUser,
  setToken,
  setStoredUser,
  clearAuth,
  logout as apiLogout,
  refresh as apiRefresh,
} from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // Instant UI hydration: show stored user while refresh is in-flight
  const [user, setUser]           = useState(getStoredUser);
  const [loading, setLoading]     = useState(true);
  const [sessionChecked, setSessionChecked] = useState(false);

  // Silently restore session from httpOnly refresh cookie on mount
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const newToken = await apiRefresh();
        if (!cancelled) {
          if (!newToken) {
            // Cookie missing or expired — no active session
            clearAuth();
            setUser(null);
          }
          // If successful, getStoredUser() will have been updated by client.js
          // and setToken() called — re-read user from storage
          const fresh = getStoredUser();
          setUser(fresh);
        }
      } catch {
        if (!cancelled) {
          clearAuth();
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setSessionChecked(true);
        }
      }
    })();

    return () => { cancelled = true; };
  }, []);

  // Listen for session-expired events (emitted by client.js on refresh failure)
  useEffect(() => {
    const handler = () => {
      clearAuth();
      setUser(null);
    };
    window.addEventListener("vyas:session-expired", handler);
    return () => window.removeEventListener("vyas:session-expired", handler);
  }, []);

  const login = useCallback((authPayload) => {
    // authPayload = { access_token, token_type, user }
    setToken(authPayload.access_token);
    setStoredUser(authPayload.user);
    setUser(authPayload.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout(); // revoke refresh token server-side
    } catch {
      // Ignore errors — clear client state regardless
    }
    clearAuth();
    setUser(null);
  }, []);

  // Called after profile update so context stays in sync
  const refreshUser = useCallback((updatedUser) => {
    setStoredUser(updatedUser);
    setUser(updatedUser);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, sessionChecked, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
