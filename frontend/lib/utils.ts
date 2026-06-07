// ── Time formatting ───────────────────────────────────────────────────────────

export function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function formatDuration(seconds: number): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const sec = seconds % 60;
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

// ── Score colour ──────────────────────────────────────────────────────────────

export function scoreColor(pct: number): string {
  if (pct >= 70) return "var(--success)";
  if (pct >= 40) return "var(--warning)";
  return "var(--danger)";
}

// ── Razorpay script loader (client-side only) ─────────────────────────────────

export function loadRazorpay(): Promise<unknown> {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined") {
      reject(new Error("Razorpay only works on client"))
      return
    }
    const checkoutWindow = window as Window & { Razorpay?: unknown }
    if (checkoutWindow.Razorpay) {
      resolve(checkoutWindow.Razorpay)
      return
    }
    const script = document.createElement("script")
    script.src = "https://checkout.razorpay.com/v1/checkout.js"
    script.onload = () => resolve(checkoutWindow.Razorpay)
    script.onerror = reject
    document.head.appendChild(script)
  })
}

// ── localStorage test-session helpers ────────────────────────────────────────
// These live in utils so both TestPage and the Zustand store can use them.

const SESSION_KEY = (id: number) => `vyas_attempt_${id}`;

export interface TestSession {
  questions: Question[];
  mockMeta: MockMeta | null;
  qStates: QuestionState[];
  currentIdx: number;
  timeLeft: number;
  totalElapsed: number;
  savedAt: number;
}

export interface Question {
  id: number;
  question: string;
  options: Record<string, string>;
  type?: string;
  difficulty?: string;
  topic?: string;
  marks: number;
  negative_marking: number;
  passage?: string;
  passage_title?: string;
  columns?: { left: Array<{ key: string; value: string }>; right: Array<{ key: string; value: string }> };
}

export interface MockMeta {
  mock_id: string | number;
  total_marks: number;
  duration_minutes: number;
}

export interface QuestionState {
  question_id: number;
  selected_option: string | null;
  time_spent_seconds: number;
  visit_count: number;
  answer_changed_count: number;
  was_marked_for_review: boolean;
}

export function saveSession(attemptId: number, data: TestSession): void {
  try {
    localStorage.setItem(SESSION_KEY(attemptId), JSON.stringify(data));
  } catch {
    // quota exceeded — silently fail
  }
}

export function loadSession(attemptId: number): TestSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY(attemptId));
    return raw ? (JSON.parse(raw) as TestSession) : null;
  } catch {
    return null;
  }
}

export function clearSession(attemptId: number): void {
  try {
    localStorage.removeItem(SESSION_KEY(attemptId));
  } catch {
    // ignore
  }
}

// ── Attempt-data handoff (MockBrowser → TestPage) ─────────────────────────────
// Next.js App Router doesn't support router.push state. We use sessionStorage
// as a one-shot transfer bag — write before navigate, read+clear on arrival.

const HANDOFF_KEY = "vyas_attempt_handoff";

export interface AttemptHandoff {
  questions: Question[];
  duration_minutes: number;
  total_marks: number;
  mock_id: string | number;
  attempt_id: number;
}

export function writeHandoff(data: AttemptHandoff): void {
  try {
    sessionStorage.setItem(HANDOFF_KEY, JSON.stringify(data));
  } catch {
    // ignore
  }
}

export function readHandoff(): AttemptHandoff | null {
  try {
    const raw = sessionStorage.getItem(HANDOFF_KEY);
    if (!raw) return null;
    sessionStorage.removeItem(HANDOFF_KEY); // one-shot
    return JSON.parse(raw) as AttemptHandoff;
  } catch {
    return null;
  }
}
