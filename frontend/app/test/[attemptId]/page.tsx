'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { submitAttempt } from '@/lib/api';
import {
  formatTime,
  saveSession,
  loadSession,
  clearSession,
  readHandoff,
  type Question,
  type MockMeta,
  type QuestionState,
} from '@/lib/utils';
import QuestionRenderer from '@/components/Questionrenderer';
import VyasLogo from '@/components/VyasLogo';
import styles from '@/styles/TestPage.module.css';

// ── Status constants ──────────────────────────────────────────────────────────

const STATUS = {
  NOT_VISITED:     'not_visited',
  NOT_ANSWERED:    'not_answered',
  ANSWERED:        'answered',
  MARKED:          'marked',
  MARKED_ANSWERED: 'marked_answered',
} as const;

const STATUS_COLORS: Record<string, { bg: string; color: string; border: string }> = {
  [STATUS.NOT_VISITED]:     { bg: '#1a1a1a',                    color: '#9a9080', border: '#2a2a2a' },
  [STATUS.NOT_ANSWERED]:    { bg: 'rgba(239,68,68,0.14)',       color: '#fca5a5', border: 'rgba(239,68,68,0.35)' },
  [STATUS.ANSWERED]:        { bg: 'rgba(212,168,67,0.16)',      color: '#f0c060', border: 'rgba(212,168,67,0.55)' },
  [STATUS.MARKED]:          { bg: 'rgba(239,68,68,0.18)',       color: '#fecaca', border: 'rgba(239,68,68,0.55)' },
  [STATUS.MARKED_ANSWERED]: { bg: 'rgba(212,168,67,0.22)',      color: '#f0c060', border: 'rgba(212,168,67,0.65)' },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildInitialState(questions: Question[]): QuestionState[] {
  return questions.map((q) => ({
    question_id:           q.id,
    selected_option:       null,
    time_spent_seconds:    0,
    visit_count:           0,
    answer_changed_count:  0,
    was_marked_for_review: false,
  }));
}

function getStatus(qs: QuestionState): string {
  const { selected_option, was_marked_for_review, visit_count } = qs;
  if (was_marked_for_review && selected_option) return STATUS.MARKED_ANSWERED;
  if (was_marked_for_review)                    return STATUS.MARKED;
  if (selected_option)                          return STATUS.ANSWERED;
  if (visit_count > 0)                          return STATUS.NOT_ANSWERED;
  return STATUS.NOT_VISITED;
}

// ── Page component ────────────────────────────────────────────────────────────

export default function TestPage() {
  const params    = useParams<{ attemptId: string }>();
  const router    = useRouter();
  const numId     = parseInt(params.attemptId, 10);

  const [questions,    setQuestions]    = useState<Question[] | null>(null);
  const [mockMeta,     setMockMeta]     = useState<MockMeta | null>(null);
  const [currentIdx,   setCurrentIdx]   = useState(0);
  const [qStates,      setQStates]      = useState<QuestionState[] | null>(null);
  const [timeLeft,     setTimeLeft]     = useState<number | null>(null);
  const [totalElapsed, setTotalElapsed] = useState(0);
  const [submitting,   setSubmitting]   = useState(false);
  const [showConfirm,  setShowConfirm]  = useState(false);
  const [showPalette,  setShowPalette]  = useState(false);
  const [isOnline,     setIsOnline]     = useState(true);
  const [loadError,    setLoadError]    = useState('');
  const [recovering,   setRecovering]   = useState(false);

  const timerRef      = useRef<ReturnType<typeof setInterval> | null>(null);
  const currentIdxRef = useRef(0);

  // Keep ref in sync
  useEffect(() => { currentIdxRef.current = currentIdx; }, [currentIdx]);

  // ── Step 1: Hydrate from localStorage OR sessionStorage handoff ──────────

  useEffect(() => {
    // Check for persisted session first
    const saved = loadSession(numId);
    if (saved && saved.questions && saved.qStates && saved.timeLeft != null) {
      setQuestions(saved.questions);
      setMockMeta(saved.mockMeta);
      setQStates(saved.qStates);
      setCurrentIdx(saved.currentIdx || 0);
      setTotalElapsed(saved.totalElapsed || 0);
      const secondsGone = Math.floor((Date.now() - saved.savedAt) / 1000);
      const adjusted = Math.max(0, saved.timeLeft - secondsGone);
      setTimeLeft(adjusted);
      setRecovering(true);
      return;
    }

    // Check for one-shot handoff from MockBrowser / AIMockPage
    const handoff = readHandoff();
    if (handoff) {
      const initialQStates = buildInitialState(handoff.questions);
      const initialTime    = handoff.duration_minutes * 60;
      const withVisit      = [...initialQStates];
      withVisit[0]         = { ...withVisit[0], visit_count: 1 };
      setQuestions(handoff.questions);
      setMockMeta({
        mock_id:          handoff.mock_id,
        total_marks:      handoff.total_marks,
        duration_minutes: handoff.duration_minutes,
      });
      setTimeLeft(initialTime);
      setQStates(withVisit);
      return;
    }

    // No data at all — direct URL navigation
    setLoadError('Session data missing. Please start the test from the Mock Browser.');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step 2: Persist to localStorage ──────────────────────────────────────

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
  }, [qStates, timeLeft, currentIdx]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step 3: Countdown timer ───────────────────────────────────────────────

  const doSubmit = useCallback(async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setSubmitting(true);
    const payload = (qStates || []).map(({ ...rest }) => rest);
    try {
      await submitAttempt(numId, totalElapsed, payload);
      clearSession(numId);
      router.push(`/results/${params.attemptId}`);
    } catch (e: unknown) {
      if (!navigator.onLine) {
        setSubmitting(false);
        alert('You are offline. Your answers are saved locally.\n\nPlease reconnect and click "Submit test" again.');
      } else {
        const msg = e instanceof Error ? e.message : 'Unknown error';
        alert(`Submission failed: ${msg}\n\nPlease try again.`);
        setSubmitting(false);
      }
    }
  }, [numId, qStates, totalElapsed, router, params.attemptId]);

  useEffect(() => {
    if (timeLeft == null || submitting) return;
    if (timeLeft <= 0) { doSubmit(); return; }

    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev == null || prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          return 0;
        }
        return prev - 1;
      });
      setTotalElapsed((prev) => prev + 1);
      setQStates((prev) => {
        if (!prev) return prev;
        const updated = [...prev];
        const idx     = currentIdxRef.current;
        updated[idx]  = { ...updated[idx], time_spent_seconds: updated[idx].time_spent_seconds + 1 };
        return updated;
      });
    }, 1000);

    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [timeLeft === null, submitting]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step 4: Online/offline ────────────────────────────────────────────────

  useEffect(() => {
    const goOnline  = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    if (typeof navigator !== 'undefined') setIsOnline(navigator.onLine);
    window.addEventListener('online',  goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online',  goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  // ── Step 5: Warn before unload ────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (submitting) return;
      e.preventDefault();
      e.returnValue = 'Your test is still in progress. Your answers are saved.';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [submitting]);

  // ── Navigation helpers ────────────────────────────────────────────────────

  const goToQuestion = (idx: number) => {
    setQStates((prev) => {
      if (!prev) return prev;
      const updated = [...prev];
      updated[idx]  = { ...updated[idx], visit_count: updated[idx].visit_count + 1 };
      return updated;
    });
    setCurrentIdx(idx);
    setShowPalette(false);
  };

  const handleSelect = (option: string) => {
    setQStates((prev) => {
      if (!prev) return prev;
      const updated = [...prev];
      const cur     = updated[currentIdx];
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
      if (!prev) return prev;
      const updated = [...prev];
      updated[currentIdx] = { ...updated[currentIdx], selected_option: null };
      return updated;
    });
  };

  const handleMarkReview = () => {
    setQStates((prev) => {
      if (!prev) return prev;
      const updated = [...prev];
      updated[currentIdx] = {
        ...updated[currentIdx],
        was_marked_for_review: !updated[currentIdx].was_marked_for_review,
      };
      return updated;
    });
  };

  // ── Render guards ─────────────────────────────────────────────────────────

  if (loadError && !questions) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
                    justifyContent: 'center', height: '100vh', gap: 16, padding: 24 }}>
        <p style={{ color: 'var(--danger)', fontSize: 15 }}>{loadError}</p>
        <button
          style={{ background: 'var(--vyas-gold)', color: '#141006', border: 'none',
                   borderRadius: 9, padding: '10px 22px', fontSize: 14, cursor: 'pointer' }}
          onClick={() => router.push('/mocks')}
        >
          Back to Mock Browser
        </button>
      </div>
    );
  }

  if (!questions || !qStates || timeLeft == null) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center',
                    height: '100vh', flexDirection: 'column', gap: 12 }}>
        <div className="spinner" />
        <p style={{ color: '#6b7280', fontSize: 14 }}>
          {recovering ? 'Restoring your session…' : 'Loading test…'}
        </p>
      </div>
    );
  }

  const currentQ     = questions[currentIdx];
  const currentState = qStates[currentIdx];
  const answered     = qStates.filter((s) => s.selected_option !== null).length;
  const markedReview = qStates.filter((s) => s.was_marked_for_review).length;
  const notVisited   = qStates.filter((s) => s.visit_count === 0).length;
  const totalDuration = (mockMeta?.duration_minutes || 0) * 60;
  const timeRatio     = totalDuration ? timeLeft / totalDuration : 1;
  const timerState    = timeRatio <= 0.1 ? styles.timerDanger : timeRatio <= 0.25 ? styles.timerWarning : '';

  return (
    <div className={styles.page}>

      {!isOnline && (
        <div className={styles.offlineBanner}>
          You are offline. Your answers are saved locally and the timer continues.
          Reconnect before submitting.
        </div>
      )}

      {recovering && (
        <div className={styles.recoveryBanner}>
          Session restored after refresh. Your answers and remaining time were saved.
          <button onClick={() => setRecovering(false)}>✕</button>
        </div>
      )}

      {/* ── Top bar ── */}
      <header className={styles.topBar}>
        <div className={styles.topLeft}>
          <VyasLogo variant="gold" size={32} />
          <div>
            <p className={styles.topSubject}>
              {String(mockMeta?.mock_id || '').replace(/_/g, ' ').toUpperCase()}
            </p>
            <p className={styles.topDetail}>
              {questions.length} questions · {mockMeta?.total_marks} marks
            </p>
          </div>
        </div>

        <div className={`${styles.timer} ${timerState}`}>
          {formatTime(timeLeft)}
        </div>

        <div className={styles.topRight}>
          <button
            className={styles.paletteToggle}
            onClick={() => setShowPalette((p) => !p)}
          >
            {showPalette ? 'Hide palette' : 'Question palette'}
          </button>
          <button
            className={styles.submitTopBtn}
            onClick={() => setShowConfirm(true)}
            disabled={submitting || !isOnline}
            title={!isOnline ? 'You must be online to submit' : ''}
          >
            Submit test
          </button>
        </div>
      </header>

      <div className={styles.body}>

        {/* ── Question panel ── */}
        <div className={styles.questionPanel}>
          <div className={styles.qHeader}>
            <span className={styles.qNum}>Question {currentIdx + 1} / {questions.length}</span>
            <div className={styles.qMeta}>
              <span className={styles.qDiff} data-diff={currentQ.difficulty}>{currentQ.difficulty}</span>
              <span className={styles.qTopic}>{currentQ.topic}</span>
              <span className={styles.qMarks}>+{currentQ.marks} / −{currentQ.negative_marking}</span>
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
                className={`${styles.actionBtn} ${styles.markBtn} ${currentState.was_marked_for_review ? styles.markActive : ''}`}
                onClick={handleMarkReview}
              >
                {currentState.was_marked_for_review ? 'Unmark review' : 'Mark for review'}
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
                Previous
              </button>
              <button
                className={`${styles.navBtn} ${styles.nextBtn}`}
                onClick={() => goToQuestion(currentIdx + 1)}
                disabled={currentIdx === questions.length - 1}
              >
                Next
              </button>
            </div>
          </div>
        </div>

        {/* ── Palette sidebar ── */}
        <aside className={`${styles.palette} ${showPalette ? styles.paletteOpen : ''}`}>
          <div className={styles.paletteSummary}>
            {[
              { label: 'Answered',    color: '#d4a843', count: answered },
              { label: 'Not answered', color: '#ef4444', count: qStates.filter(s => s.visit_count > 0 && !s.selected_option).length },
              { label: 'For review',  color: '#ef4444', count: markedReview },
              { label: 'Not visited', color: '#9a9080', count: notVisited },
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
                  className={`${styles.paletteBtn} ${idx === currentIdx ? styles.paletteCurrent : ''}`}
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
            title={!isOnline ? 'You must be online to submit' : ''}
          >
            {!isOnline ? 'Offline — can\'t submit' : 'Submit test'}
          </button>
        </aside>
      </div>

      {/* ── Confirm submit modal ── */}
      {showConfirm && (
        <div className={styles.overlay} onClick={() => !submitting && setShowConfirm(false)}>
          <div className={styles.confirmModal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.confirmTitle}>Submit test?</h2>
            <p className={styles.confirmSub}>Once submitted, you cannot change your answers.</p>
            <div className={styles.confirmStats}>
              <div className={styles.confirmStat}>
                <span className={styles.csVal} style={{ color: '#059669' }}>{answered}</span>
                <span className={styles.csLbl}>Answered</span>
              </div>
              <div className={styles.confirmStat}>
                <span className={styles.csVal} style={{ color: '#dc2626' }}>{questions.length - answered}</span>
                <span className={styles.csLbl}>Unanswered</span>
              </div>
              <div className={styles.confirmStat}>
                <span className={styles.csVal} style={{ color: '#7c3aed' }}>{markedReview}</span>
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
                {submitting ? 'Submitting…' : 'Yes, submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
