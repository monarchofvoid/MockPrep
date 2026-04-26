import { useState, useEffect, useRef, useCallback } from "react";
import Timer from "./Timer";
import QuestionPalette from "./QuestionPalette";
import { submitAttempt } from "../api/client";
import styles from "../styles/TestEngine.module.css";

const DIFF_COLOR = { easy: "#15803d", medium: "#92400e", hard: "#991b1b" };
const DIFF_BG   = { easy: "#dcfce7", medium: "#fef3c7", hard: "#fee2e2" };

function initQuestionStates(questions) {
  return questions.map((q) => ({
    questionId: q.id,
    selectedOption: null,
    timeSpentSeconds: 0,
    visitCount: 0,
    answerChangedCount: 0,
    markedForReview: false,
  }));
}

export default function TestEngine({
  attemptId,
  mockId,
  questions,
  durationMinutes,
  totalMarks,
  onResults,
}) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [qStates, setQStates] = useState(() => initQuestionStates(questions));
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Per-question timer
  const qStartRef = useRef(Date.now());
  const durationSeconds = durationMinutes * 60;

  // Record time spent on current question before navigation
  const flushTime = useCallback(
    (idx) => {
      const elapsed = Math.round((Date.now() - qStartRef.current) / 1000);
      setQStates((prev) => {
        const next = [...prev];
        next[idx] = {
          ...next[idx],
          timeSpentSeconds: next[idx].timeSpentSeconds + elapsed,
        };
        return next;
      });
      qStartRef.current = Date.now();
    },
    []
  );

  // Mark current question as visited on mount / index change
  useEffect(() => {
    setQStates((prev) => {
      const next = [...prev];
      next[currentIndex] = {
        ...next[currentIndex],
        visitCount: next[currentIndex].visitCount + 1,
      };
      return next;
    });
    qStartRef.current = Date.now();
  }, [currentIndex]);

  const navigateTo = (idx) => {
    flushTime(currentIndex);
    setCurrentIndex(idx);
  };

  const selectOption = (key) => {
    setQStates((prev) => {
      const next = [...prev];
      const current = next[currentIndex];
      const changed = current.selectedOption !== null && current.selectedOption !== key;
      next[currentIndex] = {
        ...current,
        selectedOption: key,
        answerChangedCount: current.answerChangedCount + (changed ? 1 : 0),
      };
      return next;
    });
  };

  const clearResponse = () => {
    setQStates((prev) => {
      const next = [...prev];
      const current = next[currentIndex];
      if (!current.selectedOption) return prev;
      next[currentIndex] = {
        ...current,
        selectedOption: null,
        answerChangedCount: current.answerChangedCount + 1,
      };
      return next;
    });
  };

  const toggleMark = () => {
    setQStates((prev) => {
      const next = [...prev];
      next[currentIndex] = {
        ...next[currentIndex],
        markedForReview: !next[currentIndex].markedForReview,
      };
      return next;
    });
  };

  const handleSubmit = async () => {
    flushTime(currentIndex);
    setSubmitting(true);
    setError(null);
    try {
      const timeTaken = durationSeconds - (Timer.getSecondsLeft?.() ?? 0);
      const states = qStates.map((qs) => ({
        question_id: qs.questionId,
        selected_option: qs.selectedOption,
        time_spent_seconds: qs.timeSpentSeconds,
        visit_count: qs.visitCount,
        answer_changed_count: qs.answerChangedCount,
        was_marked_for_review: qs.markedForReview,
      }));
      const results = await submitAttempt(attemptId, timeTaken, states);
      onResults(results);
    } catch (e) {
      setError(e.message);
      setSubmitting(false);
    }
  };

  const q = questions[currentIndex];
  const qs = qStates[currentIndex];
  const answered = qStates.filter((s) => s.selectedOption).length;
  const marked = qStates.filter((s) => s.markedForReview).length;
  const unattempted = questions.length - answered;

  return (
    <div className={styles.shell}>
      {/* ── Topbar ─────────────────────────────────────────────── */}
      <header className={styles.topbar}>
        <div>
          <div className={styles.topTitle}>
            {mockId.replace(/_/g, " ").toUpperCase()}
          </div>
          <div className={styles.topSub}>
            Question {currentIndex + 1} / {questions.length} &nbsp;·&nbsp; {totalMarks} marks total
          </div>
        </div>
        <Timer
          durationSeconds={durationSeconds}
          onExpire={handleSubmit}
        />
        <button
          className={styles.submitBtn}
          onClick={() => { flushTime(currentIndex); setShowModal(true); }}
        >
          Submit Test
        </button>
      </header>

      {/* ── Body ───────────────────────────────────────────────── */}
      <div className={styles.body}>
        {/* Sidebar */}
        <QuestionPalette
          questions={questions}
          questionStates={qStates}
          currentIndex={currentIndex}
          onJump={navigateTo}
        />

        {/* Main question area */}
        <main className={styles.main}>
          {/* Question header */}
          <div className={styles.qHeader}>
            <span className={styles.qNum}>Q{currentIndex + 1}</span>
            <span
              className={styles.diffTag}
              style={{
                background: DIFF_BG[q.difficulty],
                color: DIFF_COLOR[q.difficulty],
              }}
            >
              {q.difficulty}
            </span>
            <span className={styles.topicTag}>{q.topic}</span>
            <span className={styles.marksInfo}>
              +{q.marks} / −{q.negative_marking}
            </span>
          </div>

          {/* Question text */}
          <div className={styles.questionCard}>
            <p className={styles.questionText}>{q.question}</p>

            {/* Options */}
            <div className={styles.options} role="radiogroup" aria-label="Options">
              {Object.entries(q.options).map(([key, text]) => (
                <button
                  key={key}
                  role="radio"
                  aria-checked={qs.selectedOption === key}
                  className={`${styles.option} ${
                    qs.selectedOption === key ? styles.selected : ""
                  }`}
                  onClick={() => selectOption(key)}
                >
                  <span className={styles.optKey}>{key}</span>
                  <span className={styles.optText}>{text}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Navigation */}
          <div className={styles.nav}>
            <button
              className={styles.navBtn}
              disabled={currentIndex === 0}
              onClick={() => navigateTo(currentIndex - 1)}
            >
              ← Previous
            </button>
            <div className={styles.navCenter}>
              <button className={styles.markBtn} onClick={toggleMark}>
                {qs.markedForReview ? "★ Marked" : "☆ Mark for Review"}
              </button>
              <button className={styles.clearBtn} onClick={clearResponse}>
                Clear
              </button>
            </div>
            <button
              className={styles.navBtn}
              disabled={currentIndex === questions.length - 1}
              onClick={() => navigateTo(currentIndex + 1)}
            >
              Next →
            </button>
          </div>

          {error && <p className={styles.error}>⚠ {error}</p>}
        </main>
      </div>

      {/* ── Submit confirmation modal ───────────────────────────── */}
      {showModal && (
        <div className={styles.overlay} role="dialog" aria-modal="true">
          <div className={styles.modal}>
            <h3>Submit test?</h3>
            <p>You cannot change answers after submitting.</p>
            <div className={styles.modalStats}>
              <div className={styles.modalStat}>
                <span className={styles.modalVal} style={{ color: "#059669" }}>
                  {answered}
                </span>
                <span className={styles.modalLbl}>Answered</span>
              </div>
              <div className={styles.modalStat}>
                <span className={styles.modalVal} style={{ color: "#d97706" }}>
                  {marked}
                </span>
                <span className={styles.modalLbl}>Marked</span>
              </div>
              <div className={styles.modalStat}>
                <span className={styles.modalVal} style={{ color: "#6b7280" }}>
                  {unattempted}
                </span>
                <span className={styles.modalLbl}>Unattempted</span>
              </div>
            </div>
            <div className={styles.modalBtns}>
              <button
                className={styles.modalBtnSecondary}
                onClick={() => setShowModal(false)}
                disabled={submitting}
              >
                Review
              </button>
              <button
                className={styles.modalBtnPrimary}
                onClick={handleSubmit}
                disabled={submitting}
              >
                {submitting ? "Submitting…" : "Submit Final"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
