const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

// Papers
export const getMocks = () => request("GET", "/mocks");

// Test session
export const startAttempt = (userId, mockId) =>
  request("POST", "/start-attempt", { user_id: userId, mock_id: mockId });

export const submitAttempt = (attemptId, timeTakenSeconds, questionStates) =>
  request("POST", "/submit-attempt", {
    attempt_id: attemptId,
    time_taken_seconds: timeTakenSeconds,
    question_states: questionStates,
  });

// Results
export const getResults = (attemptId) =>
  request("GET", `/results/${attemptId}`);

// Analytics
export const getUserAnalytics = (userId) =>
  request("GET", `/analytics/${userId}`);

export const getUserAttempts = (userId) =>
  request("GET", `/users/${userId}/attempts`);

// Users
export const createUser = (name, email) =>
  request("POST", "/users", { name, email });
