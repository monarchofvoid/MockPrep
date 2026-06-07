'use client';

/**
 * VYAS Phase 2B — AI Mock Generator Page (v2.1.5 API fix)
 * =========================================================
 * ASYNC flow (unchanged):
 *   1. POST /api/v1/mock-tests/generate  → { job_id } (HTTP 202)
 *   2. Poll GET /api/v1/ai-jobs/{job_id} every 3 s (single status check per tick)
 *   3. On status === 'completed': POST /attempts with mock_id → attempt_id + questions
 *   4. writeHandoff(data) → router.push(`/test/${attempt_id}`)
 *
 * v2.1.5 API fixes applied:
 *   BUG-F1: generateMockTest({exam, subject, difficulty, count, use_proficiency})
 *            → ({exam_type, subject, topic, difficulty, num_questions})
 *   BUG-F2: listMyJobs() returns AIJob[] (plain array) — was cast as {ai_mocks:[]}
 *   BUG-F3: status.mock_id → status.mock_test_id (AIJob type rename)
 *   BUG-F4: status.progress_percent/questions_generated → status.progress_message
 *   BUG-F5: HistoryItem re-typed to match AIJob fields only
 *   BUG-F6: Status strings 'running'→'processing', 'queued'→'pending'
 *   BUG-F7: doPollJobStatus uses getJobStatus (single poll) not pollJobStatus (loop)
 *   BUG-F8: On completion: startAttempt(mock_test_id) for real attempt_id + questions
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import HistorySkeleton from '@/components/skeletons/Historyskeleton';
import { generateMockTest, getJobStatus, startAttempt, listMyJobs, getRecommendations, type AIJob } from '@/lib/api';
import { writeHandoff, type Question } from '@/lib/utils';
import styles from '@/styles/AIMockGeneratorPage.module.css';

// ── Static option lists ───────────────────────────────────────────────────────

const EXAMS = ['CUET', 'GATE', 'JEE', 'UPSC', 'CAT', 'CLAT', 'Other'];

const SUBJECTS_BY_EXAM: Record<string, string[]> = {
  CUET:  ['Economics', 'Business Studies', 'Accountancy', 'English', 'General Test',
           'History', 'Political Science', 'Geography', 'Sociology', 'Psychology'],
  GATE:  ['Computer Science', 'Electronics', 'Mechanical', 'Civil', 'Electrical',
           'Chemical', 'Biotechnology', 'Mathematics'],
  JEE:   ['Physics', 'Chemistry', 'Mathematics'],
  UPSC:  ['History', 'Geography', 'Polity', 'Economy', 'Environment', 'Science & Technology',
           'Current Affairs', 'Ethics'],
  CAT:   ['Verbal Ability', 'Quantitative Aptitude', 'DILR'],
  CLAT:  ['English Language', 'Current Affairs', 'Legal Reasoning',
           'Logical Reasoning', 'Quantitative Techniques'],
  Other: ['General Knowledge', 'Reasoning', 'Aptitude'],
};

const DIFFICULTY_OPTIONS: Array<{ value: 'auto' | 'easy' | 'medium' | 'hard'; label: string; icon: string }> = [
  { value: 'auto',   label: 'Auto (based on my level)', icon: '✦' },
  { value: 'easy',   label: 'Easy',                     icon: '🟢' },
  { value: 'medium', label: 'Medium',                   icon: '🟡' },
  { value: 'hard',   label: 'Hard',                     icon: '🔴' },
];

const COUNT_OPTIONS = [5, 10, 15, 20];

// ── Polling constants ─────────────────────────────────────────────────────────
const POLL_INTERVAL_MS   = 3000;   // 3 seconds between status polls
const MAX_POLL_ATTEMPTS  = 120;    // 6 minutes max (120 × 3s)

// ── History card ──────────────────────────────────────────────────────────────
// BUG-F5 FIX: HistoryItem now mirrors AIJob — backend list endpoint only returns
// job-level fields. Subject/exam/count are not included in the job status response.

interface HistoryItem {
  job_id:       string;
  status:       string;
  created_at:   string;
  completed_at: string | null;
  mock_test_id: string | null;   // was mock_id — renamed in backend v2.1
  progress_message: string | null;
  error_message: string | null;
}

function HistoryCard({
  item,
  onReopen,
}: {
  item: HistoryItem;
  onReopen: (mockTestId: string) => void;
}) {
  // BUG-F5 FIX: backend list endpoint only returns job-level fields.
  // Subject/exam/score are not included — show status-based info instead.
  const statusColor =
    item.status === 'completed'   ? '#22c55e'
    : item.status === 'failed'    ? '#ef4444'
    : item.status === 'refunded'  ? '#ef4444'
    : item.status === 'cancelled' ? '#6f6659'
    :                               '#f59e0b';   // pending/queued/running

  const statusLabel =
    item.status === 'completed'   ? 'Completed'
    : item.status === 'failed'    ? 'Failed'
    : item.status === 'refunded'  ? 'Failed (refunded)'
    : item.status === 'cancelled' ? 'Cancelled'
    : item.status === 'running'   ? 'Processing…'
    : item.status === 'queued'    ? 'Queued…'
    :                               'Pending';

  const createdDate = item.created_at
    ? new Date(item.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
    : '';

  return (
    <div className={styles.historyCard}>
      <div className={styles.historyLeft}>
        <span className={styles.historySubject}>AI Mock</span>
        <span className={styles.historyMeta}>
          {createdDate}
          {item.progress_message && ` · ${item.progress_message}`}
          {item.error_message    && ` · ${item.error_message}`}
        </span>
      </div>
      <div className={styles.historyRight}>
        <span className={styles.historyPending} style={{ color: statusColor }}>
          {statusLabel}
        </span>
        {item.status === 'completed' && item.mock_test_id && (
          <button
            className={styles.historyViewBtn}
            onClick={() => onReopen(item.mock_test_id!)}
          >
            Start test →
          </button>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AIMockPage() {
  const router = useRouter();

  // Form state
  const [exam,       setExam]       = useState('CUET');
  const [subject,    setSubject]    = useState('Economics');
  const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'hard' | 'auto'>('auto');
  const [count,      setCount]      = useState(10);

  // Generation / polling state
  const [generating,    setGenerating]    = useState(false);
  const [genError,      setGenError]      = useState('');
  const [genProgress,   setGenProgress]   = useState(0);
  const [genStatusMsg,  setGenStatusMsg]  = useState('');

  // Refs for polling cleanup
  const pollTimerRef   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollCountRef   = useRef(0);
  const activeJobIdRef = useRef<string | null>(null);

  // History state
  const [history,        setHistory]        = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Phase 3: proficiency personalisation
  const [hasProficiency, setHasProficiency] = useState(false);
  const [aiSuggestion,   setAiSuggestion]   = useState<{
    exam: string; subject: string; difficulty: string; reason: string;
  } | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, []);

  const handleExamChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setExam(val);
    setSubject((SUBJECTS_BY_EXAM[val] || ['General'])[0]);
  };

  const loadHistory = useCallback(async () => {
    try {
      // BUG-F2 FIX: listMyJobs() returns AIJob[] (plain array from backend).
      // Was incorrectly cast as { ai_mocks: HistoryItem[] } — backend list
      // endpoint returns a JSON array, not a wrapped object.
      const [jobs, rec] = await Promise.all([
        listMyJobs(),
        getRecommendations(),
      ]) as [AIJob[], {
        has_proficiency_data?: boolean;
        ai_mock_suggestion?: { exam: string; subject: string; difficulty: string; reason: string };
      }];

      // Cast AIJob[] to HistoryItem[] — shapes are compatible after BUG-F5 fix
      setHistory((jobs as unknown as HistoryItem[]) || []);
      setHasProficiency(rec.has_proficiency_data || false);

      const sugg = rec.ai_mock_suggestion;
      if (sugg) {
        setAiSuggestion(sugg);
        if (EXAMS.includes(sugg.exam))                             setExam(sugg.exam);
        const subjectList = SUBJECTS_BY_EXAM[sugg.exam] || ['General'];
        if (subjectList.includes(sugg.subject))                    setSubject(sugg.subject);
        if (['easy', 'medium', 'hard'].includes(sugg.difficulty))  setDifficulty(sugg.difficulty as 'easy' | 'medium' | 'hard');
      }
    } catch {
      // non-critical — silently fail
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // ── Step 2: Poll job status until completed / failed ──────────────────────
  const doPollJobStatus = useCallback(async (jobId: string) => {
    if (pollCountRef.current >= MAX_POLL_ATTEMPTS) {
      setGenError('Generation timed out — please try again.');
      setGenerating(false);
      activeJobIdRef.current = null;
      return;
    }

    try {
      // BUG-F7 FIX: use getJobStatus() (single poll per timer tick) instead of
      // pollJobStatus() which is an internal loop and blocks until done.
      // The page manages its own timer-based poll loop via pollTimerRef.
      const status = await getJobStatus(jobId);

      pollCountRef.current += 1;

      // BUG-F4 FIX: backend no longer sends progress_percent/questions_generated.
      // Use progress_message for human-readable status, derive a rough % from poll count.
      const roughPct = Math.min(90, 10 + pollCountRef.current * 2);
      setGenProgress(roughPct);

      // BUG FIX: backend AIJobStatus enum values are:
      //   pending | queued | running | completed | failed | refunded | cancelled
      // 'processing' and 'running'-renamed-to-processing don't exist.
      if (status.status === 'running') {
        setGenStatusMsg(status.progress_message || 'AI is crafting your questions…');
      } else if (status.status === 'queued' || status.status === 'pending') {
        setGenStatusMsg('Waiting for AI worker…');
      }

      // BUG-F3 FIX: field is mock_test_id (not mock_id) per AIJob type
      if (status.status === 'completed' && status.mock_test_id) {
        // ── Step 3: Create a real attempt (gets attempt_id + questions) ────
        setGenStatusMsg('Loading your test…');
        setGenProgress(98);

        // BUG-F8 FIX: startAttempt() creates the attempt server-side and
        // returns a real attempt_id + questions. Previously a random ID was
        // generated client-side which caused 404 on the test page.
        const attempt = await startAttempt(status.mock_test_id);
        const realAttemptId = attempt.attempt_id ?? attempt.id;

        setGenProgress(100);
        setGenStatusMsg('Done! Launching test…');

        // ── Step 4: Write handoff to sessionStorage and navigate ───────────
        writeHandoff({
          questions:        (attempt.questions as unknown as Question[]) || [],
          duration_minutes: attempt.duration_minutes ?? 90,
          total_marks:      attempt.total_marks ?? 100,
          mock_id:          attempt.mock_id ?? status.mock_test_id,
          attempt_id:       realAttemptId,
        });

        activeJobIdRef.current = null;
        router.push(`/test/${realAttemptId}`);
        return;
      }

      if (status.status === 'failed' || status.status === 'cancelled' || status.status === 'refunded') {
        const msg = status.error_message || 'Generation failed. Your credits have been refunded.';
        setGenError(msg);
        setGenerating(false);
        activeJobIdRef.current = null;
        return;
      }

      // Still in progress — schedule next poll
      pollTimerRef.current = setTimeout(() => doPollJobStatus(jobId), POLL_INTERVAL_MS);

    } catch (e: unknown) {
      // Network error during polling — retry a few times before giving up
      if (pollCountRef.current < MAX_POLL_ATTEMPTS) {
        pollTimerRef.current = setTimeout(() => doPollJobStatus(jobId), POLL_INTERVAL_MS * 2);
      } else {
        const msg = e instanceof Error ? e.message : 'Unknown error';
        setGenError(`Failed to load test status: ${msg}`);
        setGenerating(false);
        activeJobIdRef.current = null;
      }
    }
  }, [router]);

  // ── Step 1: Submit generation request ────────────────────────────────────
  const handleGenerate = async () => {
    if (generating) return;
    setGenerating(true);
    setGenError('');
    setGenProgress(5);
    setGenStatusMsg('Connecting to AI…');
    pollCountRef.current = 0;

    try {
      // BUG-F1 FIX: generateMockTest() expects MockTestRequest fields:
      // exam_type (not exam), num_questions (not count), topic (not present in UI → use subject)
      // use_proficiency is NOT a field in MockTestRequest / CreateMockTestRequest.
      const result = await generateMockTest({
        exam_type:     exam,
        subject,
        topic:         subject,   // no separate topic UI; use subject as topic
        difficulty,
        num_questions: count,
      });

      if (!result.job_id) {
        throw new Error('Server did not return a job ID. Please try again.');
      }

      activeJobIdRef.current = result.job_id;
      setGenStatusMsg('AI worker picked up your job…');
      setGenProgress(8);

      // Start polling after a short delay (worker needs a moment to start)
      pollTimerRef.current = setTimeout(
        () => doPollJobStatus(result.job_id),
        1500,
      );

    } catch (e: unknown) {
      const raw = e instanceof Error ? e.message : '';
      let friendlyMsg = raw;

      if (raw.includes('timed out') || raw.includes('504'))
        friendlyMsg = 'Generation timed out — the AI is busy. Please retry in a moment.';
      else if (raw.includes('rate limit') || raw.includes('503') || raw.includes('429'))
        friendlyMsg = 'AI service is busy right now. Please wait 30 seconds and retry.';
      else if (raw.includes('invalid response') || raw.includes('502'))
        friendlyMsg = 'AI returned an unexpected response. Please retry.';
      else if (raw.includes('profile_incomplete') || raw.includes('422'))
        friendlyMsg = 'Please complete your profile (exam selection) before generating more mocks.';
      else if (raw.includes('insufficient_credits') || raw.includes('402'))
        friendlyMsg = 'Insufficient credits. Please top up your wallet to continue.';

      setGenError(friendlyMsg || 'Generation failed. Please try again.');
      setGenerating(false);
    }
  };

  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>

        {/* ── Page header ── */}
        <div className={styles.pageHeader}>
          <div>
            <button className={styles.backBtn} onClick={() => router.push('/mocks')}>
              ← Back to Papers
            </button>
            <h1 className={styles.title}>
              <span className={styles.vyasGlyph}>✦</span> AI Mock Generator
            </h1>
            <p className={styles.subtitle}>
              Generate a personalised practice test in seconds.
              Questions are adapted to your proficiency level.
            </p>
            {hasProficiency && (
              <div className={styles.adaptiveBadge}>
                <span>✦</span>
                <span>Adapted to your profile — difficulty and topics tuned to your ELO</span>
              </div>
            )}
            {aiSuggestion && (
              <div className={styles.suggestionBox}>
                <span className={styles.suggIcon}>🎯</span>
                <span className={styles.suggText}>{aiSuggestion.reason}</span>
              </div>
            )}
          </div>
        </div>

        <div className={styles.layout}>

          {/* ── Left: Form ── */}
          <div className={styles.formPanel}>
            <h2 className={styles.panelTitle}>Configure Your Mock</h2>

            {/* Exam */}
            <div className={styles.field}>
              <label className={styles.label}>Exam</label>
              <select className={styles.select} value={exam} onChange={handleExamChange}>
                {EXAMS.map((e) => (
                  <option key={e} value={e}>{e}</option>
                ))}
              </select>
            </div>

            {/* Subject */}
            <div className={styles.field}>
              <label className={styles.label}>Subject</label>
              <select
                className={styles.select}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              >
                {(SUBJECTS_BY_EXAM[exam] || ['General']).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            {/* Difficulty */}
            <div className={styles.field}>
              <label className={styles.label}>Difficulty</label>
              <div className={styles.diffGrid}>
                {DIFFICULTY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    className={`${styles.diffBtn} ${difficulty === opt.value ? styles.diffActive : ''}`}
                    onClick={() => setDifficulty(opt.value)}
                  >
                    <span>{opt.icon}</span>
                    <span>{opt.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Question count */}
            <div className={styles.field}>
              <label className={styles.label}>Number of Questions</label>
              <div className={styles.countRow}>
                {COUNT_OPTIONS.map((n) => (
                  <button
                    key={n}
                    className={`${styles.countBtn} ${count === n ? styles.countActive : ''}`}
                    onClick={() => setCount(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <p className={styles.fieldHint}>
                ~{Math.round(count * 2.5)} minutes · {count * 4} total marks
              </p>
            </div>

            {genError && (
              <div className={styles.errorBox}>
                <span>⚠ {genError}</span>
              </div>
            )}

            <button
              className={styles.generateBtn}
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? (
                <>
                  <span className={styles.btnSpinner} />
                  <span>{genStatusMsg || `Generating ${count} questions…`}</span>
                </>
              ) : (
                <>
                  <span className={styles.vyasGlyph}>✦</span>
                  <span>Generate Mock Test</span>
                </>
              )}
            </button>

            {generating && (
              <div className={styles.progressWrap}>
                <div className={styles.progressBar} style={{ width: `${genProgress}%` }} />
                <p className={styles.generatingNote}>
                  {count > 5
                    ? `Generating in ${Math.ceil(count / 5)} batches — this takes ${Math.ceil(count / 5) * 13}–${Math.ceil(count / 5) * 16} seconds.`
                    : 'This takes 10–15 seconds.'}
                </p>
              </div>
            )}
          </div>

          {/* ── Right: History ── */}
          <div className={styles.historyPanel}>
            <h2 className={styles.panelTitle}>Your AI Mock History</h2>
            {historyLoading ? (
              <HistorySkeleton />
            ) : history.length === 0 ? (
              <div className={styles.historyEmpty}>
                <span className={styles.emptyIcon}>📋</span>
                <p>No AI mocks yet. Generate one to get started!</p>
              </div>
            ) : (
              <div className={styles.historyList}>
                {history.map((item) => (
                  <HistoryCard
                    key={item.job_id}
                    item={item}
                    onReopen={async (mockTestId) => {
                      try {
                        const attempt = await startAttempt(mockTestId);
                        const realId = attempt.attempt_id ?? attempt.id;
                        writeHandoff({
                          questions:        (attempt.questions as unknown as Question[]) || [],
                          duration_minutes: attempt.duration_minutes ?? 90,
                          total_marks:      attempt.total_marks ?? 100,
                          mock_id:          attempt.mock_id ?? mockTestId,
                          attempt_id:       realId,
                        });
                        router.push(`/test/${realId}`);
                      } catch {
                        // non-critical — user can try again
                      }
                    }}
                  />
                ))}
              </div>
            )}
          </div>

        </div>
      </main>
    </div>
  );
}