/**
 * VYAS v2.1 — Frontend API Client (lib/api.ts)
 * ===============================================
 * Production hardening applied:
 *
 * SECURITY FIXES:
 *   1. API_BASE_URL is validated at module init — if NEXT_PUBLIC_API_URL is empty
 *      in production, every request would silently go to the current origin
 *      (which could be the frontend itself, leaking auth tokens to the wrong host).
 *      Now logs a console.error in dev mode.
 *
 *   2. getAuthToken() / clearAuth(): Previously read/wrote localStorage directly.
 *      localStorage is accessible by any JS on the page (XSS risk). Access tokens
 *      are now kept in memory (module-level variable) — they survive page navigation
 *      via the /auth/refresh flow but are cleared on tab close.
 *      IMPORTANT: The refresh token remains in an httpOnly cookie (server-side) —
 *      this is already handled correctly by the backend. Only the short-lived
 *      access token needs to move to memory.
 *
 *   3. fetchWithAuth() no longer logs the Authorization header value to the console.
 *      The original code had a debug console.log that could leak tokens in prod.
 *
 *   4. Error messages from the API are sanitised before being surfaced to the UI
 *      to prevent reflected-content injection (e.g. a crafted API error containing
 *      HTML being rendered raw in a toast/alert). The sanitise function strips tags.
 *
 * DEFENSIVE PROGRAMMING:
 *   5. All API functions now have explicit return types and handle network errors
 *      (fetch throws on network failure, not just on non-2xx) with a typed error.
 *   6. pollJobStatus now has a maximum timeout so it can't loop forever if the
 *      backend gets stuck — raises ApiError after maxWaitMs.
 *   7. request() enforces an AbortController timeout (30 s) on every call.
 *
 * All existing function signatures, endpoints, and return types are preserved.
 */

// ── Types ──────────────────────────────────────────────────────────────────

export interface ApiError {
  status: number;
  message: string;
  code?: string;
  details?: Record<string, unknown>;
}

export interface UserProfile {
  preparing_exam?: string;
  target_year?: number;
  subject_focus?: string;
  avatar?: string;
  daily_goal_mins?: number;
  bio?: string;
}

export interface WalletInfo {
  balance_microcredits: number;
  balance_credits: number;
}

export interface UserMe {
  id: number;
  name: string;
  email: string;
  created_at: string;
  has_seen_premium_popup: boolean;
  profile: UserProfile | null;
  profile_completeness_percent: number;
  wallet: WalletInfo | null;
  low_credit_warning: boolean;
  profile_picture: string | null;
  access_token?: string;
}

export interface CreditPlan {
  id: number;
  name: string;
  /**
   * Backend field name is `credits_granted` (CreditPlanOut schema).
   * Aliased here so components use plan.credits_granted consistently.
   */
  credits_granted: number;
  amount_inr: number;
  amount_paise: number;
  is_popular?: boolean;
  description?: string;
  sort_order?: number;
}

export interface PaymentOrder {
  /** Backend type: str (not int). Stored and compared as string throughout. */
  internal_order_id: string;
  razorpay_order_id: string;
  razorpay_key_id: string;
  amount_paise: number;
  currency: string;
  credits_to_grant: number;
}

export interface PaymentStatus {
  /** Backend type: str (not int). Stored and compared as string throughout. */
  internal_order_id: string;
  razorpay_order_id: string;
  status: 'created' | 'verified' | 'settled' | 'failed';
  credits_granted: number | null;
  amount_inr: number;
  failure_reason: string | null;
}

export interface AIJob {
  job_id: string;
  // BUG FIX: status values come from AIJobStatus enum in models/ai_job.py.
  // 'processing' does not exist — the running state is 'running'.
  // Full set: pending | queued | running | completed | failed | refunded | cancelled
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'refunded' | 'cancelled';
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  mock_test_id: string | null;
  progress_message: string | null;
}

export interface MockTestRequest {
  subject: string;
  topic: string;
  /** Backend also accepts 'auto' — not restricted to the three literal values */
  difficulty: 'easy' | 'medium' | 'hard' | 'auto';
  num_questions: number;
  exam_type: string;
}

export interface WalletTransaction {
  id: number;
  amount_microcredits: number;
  balance_after_microcredits: number;
  entry_type: string;
  description: string | null;
  payment_order_id: string | null;
  ai_job_id: string | null;
  created_at: string;
}

export interface WalletResponse {
  balance_microcredits: number;
  balance_credits: number;
  lifetime_earned_credits: number;
  lifetime_spent_credits: number;
  recent_transactions: WalletTransaction[];
}

export interface MockTest {
  id: string;
  exam: string;
  subject: string;
  year?: number;
  is_ai_generated: boolean;
  name?: string;
  duration_minutes?: number;
  num_questions?: number;
  question_count?: number;
  total_marks?: number;
  created_at?: string;
}

// Type aliases for backward compatibility
export type Mock = MockTest;
export type LedgerEntry = WalletTransaction;
export type WalletState = WalletResponse;
export type PaymentStatusResponse = PaymentStatus;
export type CreateOrderResponse = PaymentOrder;

export interface Attempt {
  id: number;
  user_id: number;
  mock_test_id: string;
  started_at: string;
  submitted_at: string | null;
  score: number | null;
  total_marks: number | null;
  raw_answers: Record<string, unknown>;
  // Extended fields for mock test start response
  attempt_id?: number;
  questions?: Array<{
    id: string;
    text: string;
    options: Record<string, string>;
    type?: string;
    difficulty?: string;
    topic?: string;
    [key: string]: unknown;
  }>;
  duration_minutes?: number;
  mock_id?: string;
}

export interface AttemptResult {
  id: number;
  score: number;
  total_marks: number;
  percentage: number;
  score_percentage?: number;
  summary: string;
  subject?: string;
  year?: number | string;
  correct_count?: number;
  wrong_count?: number;
  skipped_count?: number;
  accuracy?: number;
  attempt_rate?: number;
  time_taken_seconds?: number;
  avg_time_per_question?: number;
  topic_performance?: Array<{
    topic: string;
    accuracy: number;
    correct: number;
    total: number;
  }>;
  question_results?: Array<{
    question_id: string;
    user_answer: string;
    correct_answer: string;
    is_correct: boolean;
    explanation?: string;
  }>;
  question_reviews?: Array<{
    question_id: number | string;
    question_text: string;
    options: Record<string, string>;
    type?: string;
    passage?: string;
    passage_title?: string;
    columns?: unknown;
    difficulty: string;
    topic: string;
    is_correct: boolean;
    selected_option?: string | null;
    correct_option: string;
    marks_awarded: number;
    explanation?: string;
    time_spent_seconds: number;
    visit_count: number;
    answer_changed_count: number;
    was_marked_for_review: boolean;
  }>;
}

export interface TutorExplanation {
  opening: string;
  core_concept: string;
  why_correct: string;
  memory_anchor: string;
  why_wrong?: string | null;
  follow_up?: string | null;
  steps?: string[] | null;
  formula?: string | null;
  [key: string]: unknown;
}

export interface TutorProficiency {
  proficiency_level: string;
  proficiency_score: number;
  subject_breakdown?: Record<string, { level: string; score: number }>;
  overall_accuracy?: number;
}

export interface TutorData {
  interaction_id: number;
  question_id: string;
  proficiency_level: string;
  proficiency_score: number;
  was_cache_hit: boolean;
  behavioral_note?: string | null;
  explanation: TutorExplanation;
}

export interface Recommendations {
  // Fields returned by GET /recommendations (backend: routers/recommendations.py)
  has_proficiency_data: boolean;
  overall_level: string;
  overall_score: number;
  total_signals: number;
  weak_topics: Array<{
    topic: string;
    subject: string;
    proficiency: number;
    level: string;
  }>;
  recommended_mocks: MockTest[];
  ai_mock_suggestion: { reason: string } | null;
  onboarding_card: {
    title: string;
    message: string;
    cta: string;
    cta_url: string;
  } | null;
}

export interface Analytics {
  // Fields returned by GET /analytics/me (backend: routers/analytics.py)
  total_attempts: number;
  avg_score_percentage: number;
  avg_accuracy: number;
  topic_mastery: Array<{
    topic: string;
    subject: string;
    accuracy: number;
    total: number;
  }>;
}

// ── Config ─────────────────────────────────────────────────────────────────

const API_BASE_URL = (() => {
  const url = process.env.NEXT_PUBLIC_API_URL || '';
  if (!url && typeof window !== 'undefined') {
    // SECURITY FIX: warn in dev if API URL is not configured
    if (process.env.NODE_ENV !== 'production') {
      console.error('[VYAS API] NEXT_PUBLIC_API_URL is not set. Requests will go to current origin.');
    }
  }
  return url;
})();

const DEFAULT_TIMEOUT_MS = 30_000;

// ── In-memory token store ──────────────────────────────────────────────────
// SECURITY FIX: access tokens live in memory, not localStorage.
// They are lost on tab close, but the refresh token (httpOnly cookie) allows
// silent re-auth via /auth/refresh on next load.

let _accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

export function clearAccessToken(): void {
  _accessToken = null;
}

// ── Error helpers ──────────────────────────────────────────────────────────

export function isApiError(err: unknown): err is ApiError {
  return (
    typeof err === 'object' &&
    err !== null &&
    'status' in err &&
    'message' in err
  );
}

/**
 * Strip HTML tags from a string to prevent reflected-content injection.
 * Used when rendering API error messages in the UI.
 */
export function sanitizeMessage(raw: unknown): string {
  if (typeof raw !== 'string') return 'An unexpected error occurred.';
  return raw.replace(/<[^>]*>/g, '').trim().slice(0, 500) || 'An unexpected error occurred.';
}

function buildApiError(status: number, body: unknown, fallback: string): ApiError {
  if (typeof body === 'object' && body !== null) {
    const b = body as Record<string, unknown>;
    const rawMessage =
      (typeof b.detail === 'string' ? b.detail : null) ||
      (typeof b.message === 'string' ? b.message : null) ||
      fallback;
    return {
      status,
      message: sanitizeMessage(rawMessage),
      code:    typeof b.error === 'string' ? b.error : undefined,
      details: typeof b === 'object' ? (b as Record<string, unknown>) : undefined,
    };
  }
  return { status, message: fallback };
}

// ── Core request helper ────────────────────────────────────────────────────

async function request<T>(
  path: string,
  options: RequestInit & { timeoutMs?: number } = {}
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const url = `${API_BASE_URL}${path}`;

  // Attach Authorization header if we have a token
  // SECURITY FIX: never log this header
  const token = getAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...fetchOptions,
      headers,
      credentials: 'include',   // send httpOnly refresh token cookie
      signal: controller.signal,
    });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw { status: 408, message: 'Request timed out. Please check your connection.' } as ApiError;
    }
    throw { status: 0, message: 'Network error. Please check your connection.' } as ApiError;
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 204) {
    return undefined as unknown as T;
  }

  let body: unknown;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    body = await response.json().catch(() => null);
  } else {
    body = await response.text().catch(() => null);
  }

  if (!response.ok) {
    throw buildApiError(
      response.status,
      body,
      `Request failed with status ${response.status}`
    );
  }

  return body as T;
}

// ── Auth ───────────────────────────────────────────────────────────────────

export async function initiateSignup(data: {
  name: string;
  email: string;
  password: string;
}): Promise<{ message: string; email: string; expires_in_seconds: number }> {
  return request('/auth/signup/initiate', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function verifySignupOTP(data: {
  email: string;
  otp: string;
}): Promise<UserMe> {
  const result = await request<UserMe>('/auth/signup/verify', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (result.access_token) {
    setAccessToken(result.access_token);
  }
  return result;
}

export async function resendOTP(email: string): Promise<{ message: string; expires_in_seconds: number }> {
  return request('/auth/signup/resend-otp', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

/**
 * Legacy direct signup — preserved for backward compatibility and tests.
 * The main frontend flow now uses initiateSignup + verifySignupOTP.
 */
export async function signup(data: {
  name: string;
  email: string;
  password: string;
}): Promise<UserMe> {
  const result = await request<UserMe>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (result.access_token) {
    setAccessToken(result.access_token);
  }
  return result;
}

export async function login(data: {
  email: string;
  password: string;
}): Promise<UserMe> {
  const result = await request<UserMe>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (result.access_token) {
    setAccessToken(result.access_token);
  }
  return result;
}

export async function logout(): Promise<void> {
  try {
    await request<void>('/auth/logout', { method: 'POST' });
  } finally {
    // Always clear local token even if server request fails
    clearAccessToken();
  }
}

export async function refreshSession(): Promise<UserMe | null> {
  try {
    const result = await request<UserMe>('/auth/refresh', { method: 'POST' });
    if (result.access_token) {
      setAccessToken(result.access_token);
    }
    return result;
  } catch (err) {
    if (isApiError(err) && (err.status === 401 || err.status === 403)) {
      clearAccessToken();
      return null;
    }
    throw err;
  }
}

export async function getMe(): Promise<UserMe> {
  return request<UserMe>('/auth/me');
}

export async function acknowledgePopup(): Promise<void> {
  return request<void>('/auth/ack-popup', { method: 'POST' });
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  return request('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(data: {
  token: string;
  new_password: string;
}): Promise<{ message: string }> {
  return request('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ── Payments ───────────────────────────────────────────────────────────────

export async function getCreditPlans(): Promise<CreditPlan[]> {
  return request<CreditPlan[]>('/api/v1/payments/plans');
}

export async function createPaymentOrder(planId: number): Promise<PaymentOrder> {
  return request<PaymentOrder>('/api/v1/payments/create-order', {
    method: 'POST',
    body: JSON.stringify({ plan_id: planId }),
  });
}

export async function verifyPayment(data: {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}): Promise<{ status: string; order_id: number; razorpay_order_id: string; message: string }> {
  return request('/api/v1/payments/verify', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getPaymentStatus(razorpayOrderId: string): Promise<PaymentStatus> {
  return request<PaymentStatus>(`/api/v1/payments/status/${encodeURIComponent(razorpayOrderId)}`);
}

/**
 * Poll payment status until settled/failed or timeout.
 * DEFENSIVE: maxWaitMs prevents infinite polling if the backend gets stuck.
 */
export async function pollPaymentStatus(
  razorpayOrderId: string,
  intervalMs = 3_000,
  maxWaitMs  = 120_000
): Promise<PaymentStatus> {
  const deadline = Date.now() + maxWaitMs;

  while (Date.now() < deadline) {
    const status = await getPaymentStatus(razorpayOrderId);
    if (status.status === 'settled' || status.status === 'failed') {
      return status;
    }
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  throw {
    status: 408,
    message: 'Payment status check timed out. Please check your wallet for credit update.',
    code: 'poll_timeout',
  } as ApiError;
}

// ── AI Mock Tests ──────────────────────────────────────────────────────────

export async function generateMockTest(data: MockTestRequest): Promise<{
  job_id: string;
  status: string;
  estimated_seconds: number;
  credits_deducted: number | null;
}> {
  return request('/api/v1/mock-tests/generate', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getJobStatus(jobId: string): Promise<AIJob> {
  return request<AIJob>(`/api/v1/ai-jobs/${encodeURIComponent(jobId)}`);
}

export async function getJobResult(jobId: string): Promise<unknown> {
  return request(`/api/v1/ai-jobs/${encodeURIComponent(jobId)}/result`);
}

export async function cancelJob(jobId: string): Promise<{
  job_id: string;
  cancelled: boolean;
  refunded_credits: number | null;
}> {
  return request(`/api/v1/ai-jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
}

export async function listMyJobs(): Promise<AIJob[]> {
  return request<AIJob[]>('/api/v1/ai-jobs/');
}

/**
 * Poll job status until completed/failed or timeout.
 * DEFENSIVE: maxWaitMs prevents infinite polling.
 */
export async function pollJobStatus(
  jobId: string,
  onProgress?: (job: AIJob) => void,
  intervalMs = 3_000,
  maxWaitMs  = 300_000
): Promise<AIJob> {
  const deadline = Date.now() + maxWaitMs;

  while (Date.now() < deadline) {
    const job = await getJobStatus(jobId);
    onProgress?.(job);

    if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled' || job.status === 'refunded') {
      return job;
    }
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  throw {
    status: 408,
    message: 'Mock test generation is taking longer than expected. Please check back in a moment.',
    code: 'poll_timeout',
  } as ApiError;
}

// ── Wallet ─────────────────────────────────────────────────────────────────

export async function getWallet(): Promise<WalletResponse> {
  return request<WalletResponse>('/api/v1/wallet/me');
}

export async function getTransactions(params?: {
  page?: number;
  per_page?: number;
  entry_type?: string;
}): Promise<{
  transactions: WalletTransaction[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}> {
  const qs = new URLSearchParams();
  if (params?.page)       qs.set('page',       String(params.page));
  if (params?.per_page)   qs.set('per_page',    String(params.per_page));
  if (params?.entry_type) qs.set('entry_type',  params.entry_type);
  const query = qs.toString() ? `?${qs.toString()}` : '';
  return request(`/api/v1/wallet/transactions${query}`);
}

// ── Contact ────────────────────────────────────────────────────────────────

export async function sendContactMessage(data: {
  name: string;
  email: string;
  message: string;
}): Promise<{ success: boolean; message: string }> {
  return request('/api/contact', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ── Profile ────────────────────────────────────────────────────────────────

export async function getProfile(): Promise<UserProfile> {
  return request<UserProfile>('/profile/me');
}

export async function updateProfile(data: Partial<UserProfile>): Promise<UserProfile> {
  return request<UserProfile>('/profile/me', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function getProfileAvatars(): Promise<{ avatars: string[] }> {
  // Backend returns { avatars: string[] } — not a bare array
  return request<{ avatars: string[] }>('/profile/avatars');
}

export async function getProfileExams(): Promise<{ exams: string[] }> {
  // Backend returns { exams: string[] } — not a bare array
  return request<{ exams: string[] }>('/profile/exams');
}

// ── Mock Tests ──────────────────────────────────────────────────────────────

export async function listMocks(): Promise<MockTest[]> {
  return request<MockTest[]>('/mocks');
}

// ── Attempts ────────────────────────────────────────────────────────────────

export async function getMyAttempts(): Promise<Attempt[]> {
  return request<Attempt[]>('/users/me/attempts');
}

export async function startAttempt(mockTestId: string): Promise<Attempt> {
  return request<Attempt>('/attempts', {
    method: 'POST',
    // BUG FIX: backend reads body.get("mock_id") — was incorrectly sending mock_test_id
    body: JSON.stringify({ mock_id: mockTestId }),
  });
}

export async function getAttempt(attemptId: number): Promise<Attempt> {
  return request<Attempt>(`/attempts/${attemptId}`);
}

export async function submitAttempt(
  attemptId: number,
  timeSpentSeconds: number,
  answers: Array<{
    question_id: string | number;
    selected_option: string | null;
    time_spent_seconds: number;
    visit_count: number;
    answer_changed_count: number;
    was_marked_for_review: boolean;
  }>
): Promise<Attempt> {
  return request<Attempt>(`/attempts/${attemptId}/submit`, {
    method: 'POST',
    body: JSON.stringify({
      raw_answers: answers,
      time_spent_seconds: timeSpentSeconds,
    }),
  });
}

export async function getAttemptResult(attemptId: number): Promise<AttemptResult> {
  return request<AttemptResult>(`/attempts/${attemptId}/result`);
}

// ── Tutor ───────────────────────────────────────────────────────────────────

export async function getTutorProficiency(): Promise<TutorProficiency> {
  return request<TutorProficiency>('/tutor/proficiency');
}

export async function getTutorExplanation(attemptId: number, questionId: string, forceRefresh: boolean = false): Promise<TutorData> {
  return request<TutorData>('/tutor/explain', {
    method: 'POST',
    body: JSON.stringify({
      attempt_id: attemptId,
      question_id: questionId,
      force_refresh: forceRefresh,
    }),
  });
}

// ── Recommendations ────────────────────────────────────────────────────────

export async function getRecommendations(): Promise<Recommendations> {
  return request<Recommendations>('/recommendations');
}

// ── Analytics ───────────────────────────────────────────────────────────────

export async function getAnalytics(): Promise<Analytics> {
  return request<Analytics>('/analytics/me');
}