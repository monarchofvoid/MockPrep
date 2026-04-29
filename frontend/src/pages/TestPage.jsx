import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import { submitAttempt } from "../api/client";
import styles from "../styles/TestPage.module.css";

// Question status constants
const STATUS = {
  NOT_VISITED:    "not_visited",
  NOT_ANSWERED:   "not_answered",
  ANSWERED:       "answered",
  MARKED:         "marked",          // marked for review without answer
  MARKED_ANSWERED:"marked_answered", // marked for review WITH answer
};

function buildInitialState(questions) {
  return questions.map((q) => ({
    question_id:          q.id,
    selected_option:      null,
    time_spent_seconds:   0,
    visit_count:          0,
    answer_changed_count: 0,
    was_marked_for_review:false,
    status:               STATUS.NOT_VISITED,
  }));
}

function getStatus(state) {
  const { selected_option, was_marked_for_review } = state;
  if (was_marked_for_review && selected_option) return STATUS.MARKED_ANSWERED;
  if (was_marked_for_review) return STATUS.MARKED;
  if (selected_option) return STATUS.ANSWERED;
  if (state.visit_count > 0) return STATUS.NOT_ANSWERED;
  return STATUS.NOT_VISITED;
}

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
  return `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
}

const STATUS_COLORS = {
  [STATUS.NOT_VISITED]:    { bg: "#f3f4f6", color: "#6b7280", border: "#e5e7eb" },
  [STATUS.NOT_ANSWERED]:   { bg: "#fee2e2", color: "#dc2626", border: "#fca5a5" },
  [STATUS.ANSWERED]:       { bg: "#d1fae5", color: "#059669", border: "#6ee7b7" },
  [STATUS.MARKED]:         { bg: "#ede9fe", color: "#7c3aed", border: "#c4b5fd" },
  [STATUS.MARKED_answered]:{bg: "#dbeafe", color: "#2563eb", border: "#93c5fd" },
  [STATUS.MARKED_ANSWERED]:{ bg: "#dbeafe", color: "#2563eb", border: "#93c5fd" },
};

export default function TestPage() {
  const { attemptId }  = useParams();
  const { state: navState } = useLocation();
  const navigate       = useNavigate();

  const attemptData    = navState?.attemptData;

  const [questions,     setQuestions]     = useState(attemptData?.questions || []);
  const [currentIdx,    setCurrentIdx]    = useState(0);
  const [qStates,       setQStates]       = useState(() =>
    buildInitialState(attemptData?.questions || [])
  );
  const [timeLeft,      setTimeLeft]      = useState(
    (attemptData?.duration_minutes || 30) * 60
  );
  const [totalElapsed,  setTotalElapsed]  = useState(0);
  const [submitting,    setSubmitting]    = useState(false);
  const [showConfirm,   setShowConfirm]   = useState(false);
  const [showPalette,   setShowPalette]   = useState(false);
  const [timeWarning,   setTimeWarning]   = useState(false);

  // Track time spent on current question
  const questionStartRef = useRef(Date.now());
  const timerRef         = useRef(null);

  // If navigated without state (e.g. direct URL), redirect
  useEffect(() => {
    if (!attemptData) {
      navigate("/mocks", { replace: true });
    }
  }, []);

  // Mark current question as visited on first load
  useEffect(() => {
    setQStates((prev) => {
      const updated = [...prev];
      if (updated[0] && updated[0].visit_count === 0) {
        updated[0] = { ...updated[0], visit_count: 1 };
      }
      return updated;
    });
  }, []);

  // Countdown timer
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          handleAutoSubmit();
          return 0;
        }
        if (prev === 300) setTimeWarning(true); // 5 min warning
        return prev - 1;
      });
      setTotalElapsed((prev) => prev + 1);

      // Accumulate time on current question
      setQStates((prev) => {
        const updated = [...prev];
        updated[currentIdx] = {
          ...updated[currentIdx],
          time_spent_seconds: updated[currentIdx].time_spent_seconds + 1,
        };
        return updated;
      });
    }, 1000);

    return () => clearInterval(timerRef.current);
  }, [currentIdx]);

  // Navigate to a question
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
    questionStartRef.current = Date.now();
    setShowPalette(false);
  };

  // Select/change answer
  const handleSelect = (option) => {
    setQStates((prev) => {
      const updated = [...prev];
      const cur = updated[currentIdx];
      const changed = cur.selected_option !== null && cur.selected_option !== option;
      updated[currentIdx] = {
        ...cur,
        selected_option: option,
        answer_changed_count: cur.answer_changed_count + (changed ? 1 : 0),
      };
      return updated;
    });
  };

  // Clear response
  const handleClear = () => {
    setQStates((prev) => {
      const updated = [...prev];
      updated[currentIdx] = { ...updated[currentIdx], selected_option: null };
      return updated;
    });
  };

  // Mark for review
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

  const handleNext = () => {
    if (currentIdx < questions.length - 1) goToQuestion(currentIdx + 1);
  };

  const handlePrev = () => {
    if (currentIdx > 0) goToQuestion(currentIdx - 1);
  };

  // Submit
  const doSubmit = useCallback(async () => {
    clearInterval(timerRef.current);
    setSubmitting(true);
    const payload = qStates.map(({ status: _, ...rest }) => rest);
    try {
      await submitAttempt(parseInt(attemptId), totalElapsed, payload);
      navigate(`/results/${attemptId}`);
    } catch (e) {
      alert("Submission failed: " + e.message);
      setSubmitting(false);
    }
  }, [attemptId, qStates, totalElapsed, navigate]);

  const handleAutoSubmit = useCallback(() => {
    doSubmit();
  }, [doSubmit]);

  // Summary counts
  const answered     = qStates.filter((s) => s.selected_option !== null).length;
  const markedReview = qStates.filter((s) => s.was_marked_for_review).length;
  const notVisited   = qStates.filter((s) => s.visit_count === 0).length;

  const currentQ     = questions[currentIdx];
  const currentState = qStates[currentIdx];
  if (!currentQ) return null;

  return (
    <div className={styles.page}>
      {/* ── Top bar ─────────────────────────────────────────────── */}
      <header className={styles.topBar}>
        <div className={styles.topLeft}>
          <span className={styles.topLogo}>VY</span>
          <div>
            <p className={styles.topSubject}>{attemptData?.mock_id?.replace(/_/g, " ")}</p>
            <p className={styles.topDetail}>
              {questions.length} questions · {attemptData?.total_marks} marks
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
            disabled={submitting}
          >
            Submit test
          </button>
        </div>
      </header>

      <div className={styles.body}>
        {/* ── Question panel ──────────────────────────────────────── */}
        <div className={styles.questionPanel}>
          {/* Q number + mark for review */}
          <div className={styles.qHeader}>
            <span className={styles.qNum}>Question {currentIdx + 1} / {questions.length}</span>
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

          {/* Question text */}
          <div className={styles.qText}>{currentQ.question}</div>

          {/* Options */}
          <div className={styles.options}>
            {Object.entries(currentQ.options).map(([key, val]) => {
              const selected = currentState.selected_option === key;
              return (
                <button
                  key={key}
                  className={`${styles.option} ${selected ? styles.selectedOption : ""}`}
                  onClick={() => handleSelect(key)}
                >
                  <span className={`${styles.optKey} ${selected ? styles.optKeySelected : ""}`}>
                    {key}
                  </span>
                  <span className={styles.optVal}>{val}</span>
                </button>
              );
            })}
          </div>

          {/* Action bar */}
          <div className={styles.actionBar}>
            <div className={styles.actionLeft}>
              <button
                className={`${styles.actionBtn} ${styles.markBtn} ${currentState.was_marked_for_review ? styles.markActive : ""}`}
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
                onClick={handlePrev}
                disabled={currentIdx === 0}
              >
                ← Previous
              </button>
              <button
                className={`${styles.navBtn} ${styles.nextBtn}`}
                onClick={handleNext}
                disabled={currentIdx === questions.length - 1}
              >
                Next →
              </button>
            </div>
          </div>
        </div>

        {/* ── Question palette (sidebar) ─────────────────────────── */}
        <aside className={`${styles.palette} ${showPalette ? styles.paletteOpen : ""}`}>
          <div className={styles.paletteSummary}>
            <div className={styles.summaryItem}>
              <span className={styles.summaryDot} style={{ background: "#059669" }} />
              <span>{answered} answered</span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryDot} style={{ background: "#dc2626" }} />
              <span>{qStates.filter(s => s.visit_count > 0 && !s.selected_option).length} not answered</span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryDot} style={{ background: "#7c3aed" }} />
              <span>{markedReview} for review</span>
            </div>
            <div className={styles.summaryItem}>
              <span className={styles.summaryDot} style={{ background: "#e5e7eb" }} />
              <span>{notVisited} not visited</span>
            </div>
          </div>

          <div className={styles.paletteGrid}>
            {qStates.map((qs, idx) => {
              const st     = getStatus(qs);
              const colors = STATUS_COLORS[st] || STATUS_COLORS[STATUS.NOT_VISITED];
              return (
                <button
                  key={qs.question_id}
                  className={`${styles.paletteBtn} ${idx === currentIdx ? styles.paletteCurrent : ""}`}
                  style={{
                    background:   colors.bg,
                    color:        colors.color,
                    borderColor:  colors.border,
                  }}
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
            disabled={submitting}
          >
            Submit test
          </button>
        </aside>
      </div>

      {/* ── Confirm submit modal ─────────────────────────────────── */}
      {showConfirm && (
        <div className={styles.overlay} onClick={() => !submitting && setShowConfirm(false)}>
          <div className={styles.confirmModal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.confirmTitle}>Submit test?</h2>
            <p className={styles.confirmSub}>Once submitted, you cannot change your answers.</p>
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
