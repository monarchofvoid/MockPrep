/**
 * VYAS v2.0 — API Client
 * =======================
 * v2.0 security changes:
 *
 * 1. Access token stored in MEMORY only (React context), not localStorage.
 *    This eliminates XSS token theft from localStorage.
 *
 * 2. Refresh token is in an httpOnly cookie — JS cannot read it.
 *    The browser sends it automatically to /auth/refresh.
 *
 * 3. Silent refresh: on any 401, the client automatically calls
 *    /auth/refresh to get a new access token, then retries the
 *    original request. Completely transparent to the user.
 *
 * 4. One in-flight refresh at a time: concurrent 401 responses
 *    queue behind a single refresh promise to avoid race conditions.
 *
 * 5. Legacy localStorage helpers kept as no-ops for safe removal.
 *    User info still cached in localStorage for page-refresh UX
 *    (non-sensitive: just name/email/id).
 */

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── In-memory access token ────────────────────────────────────────────────────
// The token lives here, NOT in localStorage. It is wiped on page reload,
// which triggers a silent refresh from the httpOnly cookie on startup.

let _accessToken = null;

export const getToken   = ()       => _accessToken;
export const setToken   = (token)  => { _accessToken = token; };
export const clearToken = ()       => { _accessToken = null; };

// ── Non-sensitive user cache (localStorage) ───────────────────────────────────
// Storing only public info (name, email, id) in localStorage for instant
// UI hydration on page load (before the async /auth/refresh completes).

export const getStoredUser = () => {
  try {
    const raw = localStorage.getItem("vyas_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};
export const setStoredUser  = (user) => localStorage.setItem("vyas_user", JSON.stringify(user));
export const clearStoredUser = ()    => localStorage.removeItem("vyas_user");

// Combined helpers for backward compat
export const saveAuth = ({ access_token, user }) => {
  setToken(access_token);
  setStoredUser(user);
};
export const clearAuth = () => {
  clearToken();
  clearStoredUser();
};

// ── Refresh coordination ──────────────────────────────────────────────────────
// Ensures only ONE /auth/refresh call runs at a time.
// Concurrent requests that hit 401 queue behind it.

let _refreshPromise = null;

async function _doRefresh() {
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    credentials: "include",   // sends httpOnly refresh cookie
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    clearAuth();
    return null;
  }

  const data = await res.json();
  setToken(data.access_token);
  setStoredUser(data.user);
  return data.access_token;
}

async function refreshOnce() {
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = _doRefresh().finally(() => {
    _refreshPromise = null;
  });
  return _refreshPromise;
}

// ── Core request helper ───────────────────────────────────────────────────────

async function request(method, path, body = null, requiresAuth = true, _retry = false) {
  const headers = { "Content-Type": "application/json" };

  if (requiresAuth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const opts = { method, headers, credentials: "include" };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${BASE}${path}`, opts);

  // ── Silent refresh on 401 ─────────────────────────────────────────────────
  if (res.status === 401 && requiresAuth && !_retry) {
    const newToken = await refreshOnce();
    if (newToken) {
      // Retry the original request with the new token
      return request(method, path, body, requiresAuth, true);
    } else {
      // Refresh failed → session expired, force re-login
      clearAuth();
      window.dispatchEvent(new CustomEvent("vyas:session-expired"));
      throw new Error("Session expired. Please log in again.");
    }
  }

  if (!res.ok) {
    let message;
    try {
      const err = await res.json();
      if (Array.isArray(err.detail)) {
        message = err.detail
          .map((e) => {
            const loc = Array.isArray(e.loc) ? e.loc.join(" → ") : "";
            return loc ? `${loc}: ${e.msg}` : e.msg;
          })
          .join("; ");
      } else {
        message = err.detail || "Request failed";
      }
    } catch {
      message = res.statusText || "Request failed";
    }
    throw new Error(message);
  }

  // 204 No Content — don't try to parse JSON
  if (res.status === 204) return null;
  return res.json();
}

// ── Auth endpoints ────────────────────────────────────────────────────────────

export const signup = (name, email, password) =>
  request("POST", "/auth/signup", { name, email, password }, false);

export const login = (email, password) =>
  request("POST", "/auth/login", { email, password }, false);

export const refresh = () => refreshOnce();

export const logout = () => request("POST", "/auth/logout", null, true);

export const getMe = () => request("GET", "/auth/me");

// ── Papers ────────────────────────────────────────────────────────────────────

export const getMocks = () => request("GET", "/mocks");

// ── Test session ──────────────────────────────────────────────────────────────

export const startAttempt = (mockId) =>
  request("POST", "/start-attempt", { mock_id: mockId });

export const submitAttempt = (attemptId, timeTakenSeconds, questionStates) =>
  request("POST", "/submit-attempt", {
    attempt_id: attemptId,
    time_taken_seconds: timeTakenSeconds,
    question_states: questionStates,
  });

// ── Results & analytics ───────────────────────────────────────────────────────

export const getResults    = (attemptId) => request("GET", `/results/${attemptId}`);
export const getMyAnalytics = ()         => request("GET", "/analytics/me");
export const getMyAttempts  = ()         => request("GET", "/users/me/attempts");

// ── Password Reset ────────────────────────────────────────────────────────────

export const forgotPassword = (email) =>
  request("POST", "/auth/forgot-password", { email }, false);

export const resetPassword = (token, new_password) =>
  request("POST", "/auth/reset-password", { token, new_password }, false);

// ── Proficiency ───────────────────────────────────────────────────────────────

export const getMyProficiency = () => request("GET", "/tutor/proficiency");

// ── Tutor ─────────────────────────────────────────────────────────────────────

export const getTutorExplanation = (attemptId, questionId, forceRefresh = false) =>
  request("POST", "/tutor/explain", {
    attempt_id:    attemptId,
    question_id:   questionId,
    force_refresh: forceRefresh,
  });

export const rateTutorExplanation = (interactionId, rating) =>
  request("POST", "/tutor/rate", { interaction_id: interactionId, rating });

// ── AI Mock ───────────────────────────────────────────────────────────────────

export const generateAIMock = (exam, subject, difficulty, questionCount, useProficiency = true) =>
  request("POST", "/ai-mock/generate", {
    exam,
    subject,
    difficulty,
    question_count:  questionCount,
    use_proficiency: useProficiency,
  });

export const getAIMockHistory = () => request("GET", "/ai-mock/history");

// ── Recommendations ───────────────────────────────────────────────────────────

export const getRecommendations = () => request("GET", "/recommendations");

// ── Profile ───────────────────────────────────────────────────────────────────

export const getProfile    = ()            => request("GET", "/profile/me");
export const updateProfile = (profileData) => request("PUT", "/profile/me", profileData);
