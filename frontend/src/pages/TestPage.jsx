import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import { startAttempt, submitAttempt } from "../api/client";
import styles from "../styles/TestPage.module.css";
import QuestionRenderer from "../components/QuestionRenderer";

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUS = {
  NOT_VISITED:     "not_visited",
  NOT_ANSWERED:    "not_answered",
  ANSWERED:        "answered",
  MARKED:          "marked",
  MARKED_ANSWERED: "marked_answered",
};

const STATUS_COLORS = {
  [STATUS.NOT_VISITED]:     { bg: "#f3f4f6", color: "#6b7280", border: "#e5e7eb" },
  [STATUS.NOT_ANSWERED]:    { bg: "#fee2e2", color: "#dc2626", border: "#fca5a5" },
  [STATUS.ANSWERED]:        { bg: "#d1fae5", color: "#059669", border: "#6ee7b7" },
  [STATUS.MARKED]:          { bg: "#ede9fe", color: "#7c3aed", border: "#c4b5fd" },
  [STATUS.MARKED_ANSWERED]: { bg: "#dbeafe", color: "#2563eb", border: "#93c5fd" },
};

// ── localStorage helpers ──────────────────────────────────────────────────────

const STORAGE_KEY = (attemptId) => `vyas_attempt_${attemptId}`;

function saveSession(attemptId, data) {
  try {
    localStorage.setItem(STORAGE_KEY(attemptId), JSON.stringify(data));
  } catch {}
}

function loadSession(attemptId) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY(attemptId));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function clearSession(attemptId) {
  try {
    localStorage.removeItem(STORAGE_KEY(attemptId));
  } catch {}
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildInitialState(questions) {
  return questions.map((q) => ({
    question_id:           q.id,
    selected_option:       null,
    time_spent_seconds:    0,
    visit_count:           0,
    answer_changed_count:  0,
    was_marked_for_review: false,
  }));
}

function getStatus(qs) {
  const { selected_option, was_marked_for_review, visit_count } = qs;
  if (was_marked_for_review && selected_option) return STATUS.MARKED_ANSWERED;
  if (was_marked_for_review)                    return STATUS.MARKED;
  if (selected_option)                          return STATUS.ANSWERED;
  if (visit_count > 0)                          return STATUS.NOT_ANSWERED;
  return STATUS.NOT_VISITED;
}

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function TestPage() {
  const { attemptId }       = useParams();
  const { state: navState } = useLocation();
  const navigate            = useNavigate();

  // ── State ─────────────────────────────────────────────────────────────────

  const [questions,   setQuestions]   = useState(null);   // null = still loading
  const [mockMeta,    setMockMeta]    = useState(null);
  const [currentIdx,  setCurrentIdx]  = useState(0);
  const [qStates,     setQStates]     = useState(null);   // null = still loading
  const [timeLeft,    setTimeLeft]    = useState(null);   // null = still loading
  const [totalElapsed,setTotalElapsed]= useState(0);
  const [submitting,  setSubmitting]  = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [showPalette, setShowPalette] = useState(false);
  const [timeWarning, setTimeWarning] = useState(false);
  const [isOnline,    setIsOnline]    = useState(navigator.onLine);
  const [loadError,   setLoadError]   = useState("");
  const [recovering,  setRecovering]  = useState(false);

  const timerRef = useRef(null);
  const numId    = parseInt(attemptId);

  // ── Step 1: Hydrate from localStorage OR navState OR re-fetch ────────────

  useEffect(() => {
    const saved = loadSession(numId);

    if (saved && saved.questions && saved.qStates && saved.timeLeft != null) {
      // ── Restored from localStorage after refresh ──────────────
      setQuestions(saved.questions);
      setMockMeta(saved.mockMeta);
      setQStates(saved.qStates);
      setCurrentIdx(saved.currentIdx || 0);
      setTotalElapsed(saved.totalElapsed || 0);

      // Adjust time: account for seconds elapsed since last save
      const secondsGone = Math.floor((Date.now() - saved.savedAt) / 1000);
      const adjusted = Math.max(0, saved.timeLeft - secondsGone);
      setTimeLeft(adjusted);
      if (adjusted <= 300) setTimeWarning(true);
      setRecovering(true);
      return;
    }

    if (navState?.attemptData) {
      // ── Fresh start from MockBrowser navigation ───────────────
      const { questions, duration_minutes, total_marks, mock_id } = navState.attemptData;
      const initialQStates = buildInitialState(questions);
      const initialTime    = duration_minutes * 60;

      setQuestions(questions);
      setMockMeta({ mock_id, total_marks, duration_minutes });
      setQStates(initialQStates);
      setTimeLeft(initialTime);

      // Mark Q1 as visited immediately
      const withVisit = [...initialQStates];
      withVisit[0] = { ...withVisit[0], visit_count: 1 };
      setQStates(withVisit);
      return;
    }

    // ── No local state and no navState: re-fetch from backend ────
    // This handles the case where the user navigated directly to /test/:id
    setLoadError("Session data missing — attempting to restore from server…");
  }, []);

  // ── Step 2: Persist to localStorage whenever key state changes ───────────

  useEffect(() => {
    if (!questions || !qStates || timeLeft == null) return;

    saveSession(numId, {
      questions,
      mockMeta,
      qStates,
      currentIdx,
      timeLeft,
      totalElapsed,
      savedAt: Date.now(),
    });
  }, [qStates, timeLeft, currentIdx]);

  // ── Step 3: Countdown timer ───────────────────────────────────────────────

  useEffect(() => {
    if (timeLeft == null || submitting) return;

    if (timeLeft <= 0) {
      handleAutoSubmit();
      return;
    }

    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          return 0;
        }
        if (prev === 300) setTimeWarning(true);
        return prev - 1;
      });

      setTotalElapsed((prev) => prev + 1);

      // Accumulate time on current question
      setQStates((prev) => {
        if (!prev) return prev;
        const updated = [...prev];
        updated[currentIdx] = {
          ...updated[currentIdx],
          time_spent_seconds: updated[currentIdx].time_spent_seconds + 1,
        };
        return updated;
      });
    }, 1000);

    return () => clearInterval(timerRef.current);
  }, [timeLeft === null, submitting, currentIdx]);
  // ^ Only re-run when loading finishes, submitting changes, or question changes.
  // Intentionally NOT re-running on every timeLeft tick.

  // Auto-submit when timeLeft hits 0
  useEffect(() => {
    if (timeLeft === 0 && !submitting) {
      handleAutoSubmit();
    }
  }, [timeLeft]);

  // ── Step 4: Online/offline detection ─────────────────────────────────────

  useEffect(() => {
    const goOnline  = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener("online",  goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online",  goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  // ── Step 5: Warn before unload (tab close / refresh) ─────────────────────

  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (submitting) return;
      e.preventDefault();
      e.returnValue = "Your test is still in progress. Your answers are saved and will resume when you return.";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [submitting]);

  // ── Navigation helpers ────────────────────────────────────────────────────

  const goToQuestion = (idx) => {
    setQStates((prev) => {
      const updated = [...prev];
      updated[idx] = {
        ...updated[idx],
        visit_count: updated[idx].visit_count + 1,
      };
      return updated;
    });
    setCurrentIdx(idx);
    setShowPalette(false);
  };

  const handleSelect = (option) => {
    setQStates((prev) => {
      const updated = [...prev];
      const cur = updated[currentIdx];
      const changed = cur.selected_option !== null && cur.selected_option !== option;
      updated[currentIdx] = {
        ...cur,
        selected_option:      option,
        answer_changed_count: cur.answer_changed_count + (changed ? 1 : 0),
      };
      return updated;
    });
  };

  const handleClear = () => {
    setQStates((prev) => {
      const updated = [...prev];
      updated[currentIdx] = { ...updated[currentIdx], selected_option: null };
      return updated;
    });
  };

  const handleMarkReview = () => {
    setQStates((prev) => {
      const updated = [...prev];
      updated[currentIdx] = {
        ...updated[currentIdx],
        was_marked_for_review: !updated[currentIdx].was_marked_for_review,
      };
      return updated;
    });
  };

  // ── Submit logic ──────────────────────────────────────────────────────────

  const doSubmit = useCallback(async () => {
    clearInterval(timerRef.current);
    setSubmitting(true);

    const payload = qStates.map(({ ...rest }) => rest);

    try {
      await submitAttempt(numId, totalElapsed, payload);
      clearSession(numId);        // wipe localStorage on successful submit
      navigate(`/results/${attemptId}`);
    } catch (e) {
      // If offline, don't give up — keep state in localStorage and retry
      if (!navigator.onLine) {
        setSubmitting(false);
        // show a message; the data is safe in localStorage
        alert(
          "You are offline. Your answers are saved locally.\n\n" +
          "Please reconnect and click 'Submit test' again."
        );
      } else {
        alert("Submission failed: " + e.message + "\n\nPlease try again.");
        setSubmitting(false);
      }
    }
  }, [numId, qStates, totalElapsed, navigate, attemptId]);

  const handleAutoSubmit = useCallback(() => {
    clearInterval(timerRef.current);
    doSubmit();
  }, [doSubmit]);

  // ── Render guards ─────────────────────────────────────────────────────────

  if (loadError && !questions) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
                    justifyContent: "center", height: "100vh", gap: 16, padding: 24 }}>
        <p style={{ color: "#dc2626", fontSize: 15 }}>⚠️ {loadError}</p>
        <button
          style={{ background: "#2563eb", color: "#fff", border: "none",
                   borderRadius: 9, padding: "10px 22px", fontSize: 14, cursor: "pointer" }}
          onClick={() => navigate("/mocks")}
        >
          Back to Mock Browser
        </button>
      </div>
    );
  }

  if (!questions || !qStates || timeLeft == null) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                    height: "100vh", flexDirection: "column", gap: 12 }}>
        <div className="spinner" />
        <p style={{ color: "#6b7280", fontSize: 14 }}>
          {recovering ? "Restoring your session…" : "Loading test…"}
        </p>
      </div>
    );
  }

  const currentQ     = questions[currentIdx];
  const currentState = qStates[currentIdx];

  const answered     = qStates.filter((s) => s.selected_option !== null).length;
  const markedReview = qStates.filter((s) => s.was_marked_for_review).length;
  const notVisited   = qStates.filter((s) => s.visit_count === 0).length;

  return (
    <div className={styles.page}>

      {/* ── Offline banner ───────────────────────────────────────── */}
      {!isOnline && (
        <div className={styles.offlineBanner}>
          ⚠️ You are offline — your answers are saved locally and the timer continues.
          Reconnect before submitting.
        </div>
      )}

      {/* ── Session restored banner ──────────────────────────────── */}
      {recovering && (
        <div className={styles.recoveryBanner}>
          ✅ Session restored after refresh — your answers and remaining time were saved.
          <button onClick={() => setRecovering(false)}>✕</button>
        </div>
      )}

      {/* ── Top bar ──────────────────────────────────────────────── */}
      <header className={styles.topBar}>
        <div className={styles.topLeft}>
          <span className={styles.topLogo}>VY</span>
          <div>
            <p className={styles.topSubject}>
              {mockMeta?.mock_id?.replace(/_/g, " ").toUpperCase()}
            </p>
            <p className={styles.topDetail}>
              {questions.length} questions · {mockMeta?.total_marks} marks
            </p>
          </div>
        </div>

        <div className={`${styles.timer} ${timeWarning ? styles.timerWarning : ""}`}>
          <span className={styles.timerIcon}>⏱</span>
          {formatTime(timeLeft)}
        </div>

        <div className={styles.topRight}>
          <button
            className={styles.paletteToggle}
            onClick={() => setShowPalette((p) => !p)}
          >
            {showPalette ? "Hide palette" : "Question palette"}
          </button>
          <button
            className={styles.submitTopBtn}
            onClick={() => setShowConfirm(true)}
            disabled={submitting || !isOnline}
            title={!isOnline ? "You must be online to submit" : ""}
          >
            Submit test
          </button>
        </div>
      </header>

      <div className={styles.body}>

        {/* ── Question panel ───────────────────────────────────────── */}
        <div className={styles.questionPanel}>
          <div className={styles.qHeader}>
            <span className={styles.qNum}>
              Question {currentIdx + 1} / {questions.length}
            </span>
            <div className={styles.qMeta}>
              <span className={styles.qDiff} data-diff={currentQ.difficulty}>
                {currentQ.difficulty}
              </span>
              <span className={styles.qTopic}>{currentQ.topic}</span>
              <span className={styles.qMarks}>
                +{currentQ.marks} / −{currentQ.negative_marking}
              </span>
            </div>
          </div>

          <QuestionRenderer
            question={currentQ}
            selectedOption={currentState.selected_option}
            onSelect={handleSelect}
          />

          <div className={styles.actionBar}>
            <div className={styles.actionLeft}>
              <button
                className={`${styles.actionBtn} ${styles.markBtn} ${
                  currentState.was_marked_for_review ? styles.markActive : ""
                }`}
                onClick={handleMarkReview}
              >
                🔖 {currentState.was_marked_for_review ? "Unmark review" : "Mark for review"}
              </button>
              <button
                className={`${styles.actionBtn} ${styles.clearBtn}`}
                onClick={handleClear}
                disabled={!currentState.selected_option}
              >
                Clear response
              </button>
            </div>
            <div className={styles.actionRight}>
              <button
                className={styles.navBtn}
                onClick={() => goToQuestion(currentIdx - 1)}
                disabled={currentIdx === 0}
              >
                ← Previous
              </button>
              <button
                className={`${styles.navBtn} ${styles.nextBtn}`}
                onClick={() => goToQuestion(currentIdx + 1)}
                disabled={currentIdx === questions.length - 1}
              >
                Next →
              </button>
            </div>
          </div>
        </div>

        {/* ── Palette sidebar ──────────────────────────────────────── */}
        <aside className={`${styles.palette} ${showPalette ? styles.paletteOpen : ""}`}>
          <div className={styles.paletteSummary}>
            {[
              { label: "Answered",    color: "#059669", count: answered },
              { label: "Not answered",color: "#dc2626",
                count: qStates.filter(s => s.visit_count > 0 && !s.selected_option).length },
              { label: "For review",  color: "#7c3aed", count: markedReview },
              { label: "Not visited", color: "#e5e7eb", count: notVisited },
            ].map(({ label, color, count }) => (
              <div key={label} className={styles.summaryItem}>
                <span className={styles.summaryDot} style={{ background: color }} />
                <span>{count} {label}</span>
              </div>
            ))}
          </div>

          <div className={styles.paletteGrid}>
            {qStates.map((qs, idx) => {
              const st     = getStatus(qs);
              const colors = STATUS_COLORS[st] || STATUS_COLORS[STATUS.NOT_VISITED];
              return (
                <button
                  key={qs.question_id}
                  className={`${styles.paletteBtn} ${idx === currentIdx ? styles.paletteCurrent : ""}`}
                  style={{ background: colors.bg, color: colors.color, borderColor: colors.border }}
                  onClick={() => goToQuestion(idx)}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>

          <button
            className={styles.submitSideBtn}
            onClick={() => setShowConfirm(true)}
            disabled={submitting || !isOnline}
            title={!isOnline ? "You must be online to submit" : ""}
          >
            {!isOnline ? "Offline — can't submit" : "Submit test"}
          </button>
        </aside>
      </div>

      {/* ── Confirm submit modal ─────────────────────────────────── */}
      {showConfirm && (
        <div className={styles.overlay} onClick={() => !submitting && setShowConfirm(false)}>
          <div className={styles.confirmModal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.confirmTitle}>Submit test?</h2>
            <p className={styles.confirmSub}>
              Once submitted, you cannot change your answers.
            </p>
            <div className={styles.confirmStats}>
              <div className={styles.confirmStat}>
                <span className={styles.csVal} style={{ color: "#059669" }}>{answered}</span>
                <span className={styles.csLbl}>Answered</span>
              </div>
              <div className={styles.confirmStat}>
                <span className={styles.csVal} style={{ color: "#dc2626" }}>
                  {questions.length - answered}
                </span>
                <span className={styles.csLbl}>Unanswered</span>
              </div>
              <div className={styles.confirmStat}>
                <span className={styles.csVal} style={{ color: "#7c3aed" }}>{markedReview}</span>
                <span className={styles.csLbl}>For review</span>
              </div>
            </div>
            <div className={styles.confirmActions}>
              <button
                className={styles.cancelBtn}
                onClick={() => setShowConfirm(false)}
                disabled={submitting}
              >
                Go back
              </button>
              <button
                className={styles.confirmBtn}
                onClick={doSubmit}
                disabled={submitting}
              >
                {submitting ? "Submitting…" : "Yes, submit →"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
