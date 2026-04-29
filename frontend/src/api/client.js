const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Token management ──────────────────────────────────────────────────────────

export const getToken = () => localStorage.getItem("vyas_token");
export const setToken = (token) => localStorage.setItem("vyas_token", token);
export const clearToken = () => localStorage.removeItem("vyas_token");

export const getStoredUser = () => {
  try {
    const raw = localStorage.getItem("vyas_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};
export const setStoredUser = (user) =>
  localStorage.setItem("vyas_user", JSON.stringify(user));
export const clearStoredUser = () => localStorage.removeItem("vyas_user");

export const saveAuth = ({ access_token, user }) => {
  setToken(access_token);
  setStoredUser(user);
};

export const clearAuth = () => {
  clearToken();
  clearStoredUser();
};

// ── Core request helper ───────────────────────────────────────────────────────

async function request(method, path, body = null, requiresAuth = true) {
  const headers = { "Content-Type": "application/json" };

  if (requiresAuth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${BASE}${path}`, opts);

  // Auto-logout on 401
  if (res.status === 401 && requiresAuth) {
    clearAuth();
    window.location.href = "/";
    throw new Error("Session expired. Please log in again.");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }

  return res.json();
}

// ── Auth endpoints ────────────────────────────────────────────────────────────

export const signup = (name, email, password) =>
  request("POST", "/auth/signup", { name, email, password }, false);

export const login = (email, password) =>
  request("POST", "/auth/login", { email, password }, false);

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

export const getResults = (attemptId) => request("GET", `/results/${attemptId}`);

export const getMyAnalytics = () => request("GET", "/analytics/me");

export const getMyAttempts = () => request("GET", "/users/me/attempts");
