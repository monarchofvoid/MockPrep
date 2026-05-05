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

// ── Password Reset ────────────────────────────────────────────────────────────

export const forgotPassword = (email) =>
  request("POST", "/auth/forgot-password", { email }, false);

export const resetPassword = (token, new_password) =>
  request("POST", "/auth/reset-password", { token, new_password }, false);

// ── Phase 1: Proficiency ──────────────────────────────────────────────────────

export const getMyProficiency = () => request("GET", "/tutor/proficiency");

// ── Phase 2A: VYAS Tutor ──────────────────────────────────────────────────────

export const getTutorExplanation = (attemptId, questionId, forceRefresh = false) =>
  request("POST", "/tutor/explain", {
    attempt_id:    attemptId,
    question_id:   questionId,
    force_refresh: forceRefresh,
  });

export const rateTutorExplanation = (interactionId, rating) =>
  request("POST", "/tutor/rate", {
    interaction_id: interactionId,
    rating,
  });

// ── Phase 2B: AI Mock Generator ───────────────────────────────────────────────

export const generateAIMock = (exam, subject, difficulty, questionCount, useProficiency = true) =>
  request("POST", "/ai-mock/generate", {
    exam,
    subject,
    difficulty,
    question_count:  questionCount,
    use_proficiency: useProficiency,
  });

export const getAIMockHistory = () => request("GET", "/ai-mock/history");

// ── Phase 3: Recommendations ──────────────────────────────────────────────────

export const getRecommendations = () => request("GET", "/recommendations");

// ── User Profile (v0.6) ───────────────────────────────────────────────────────

export const getProfile = () => request("GET", "/profile/me");

export const updateProfile = (profileData) =>
  request("PUT", "/profile/me", profileData);
