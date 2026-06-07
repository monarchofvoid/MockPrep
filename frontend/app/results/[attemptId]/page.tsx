'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import TutorPanel from '@/components/Tutorpanel';
import ResultsSkeleton from '@/components/skeletons/Resultsskeleton';
import QuestionRenderer from '@/components/Questionrenderer';
import { getAttemptResult } from '@/lib/api';
import { formatDuration } from '@/lib/utils';
import styles from '@/styles/ResultsPage.module.css';

// ── Types ─────────────────────────────────────────────────────────────────────

interface TopicPerf {
  topic:    string;
  accuracy: number;
  correct:  number;
  total:    number;
}

interface QuestionReview {
  question_id:          number;
  question_text:        string;
  options:              Record<string, string>;
  type?:                string;
  passage?:             string;
  passage_title?:       string;
  columns?:             unknown;
  difficulty:           string;
  topic:                string;
  is_correct:           boolean;
  selected_option?:     string | null;
  correct_option:       string;
  marks_awarded:        number;
  explanation?:         string;
  time_spent_seconds:   number;
  visit_count:          number;
  answer_changed_count: number;
  was_marked_for_review: boolean;
}

interface ResultsData {
  subject:               string;
  year:                  string;
  score:                 number;
  total_marks:           number;
  score_percentage:      number;
  correct_count:         number;
  wrong_count:           number;
  skipped_count:         number;
  accuracy:              number;
  attempt_rate:          number;
  time_taken_seconds:    number;
  avg_time_per_question: number;
  topic_performance:     TopicPerf[];
  question_reviews:      QuestionReview[];
}

// ── Score ring SVG ────────────────────────────────────────────────────────────

function ScoreRing({ pct }: { pct: number }) {
  const r     = 54;
  const circ  = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  const color = pct >= 70 ? '#22c55e' : pct >= 40 ? '#f59e0b' : '#ef4444';

  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" />
      <circle
        cx="70" cy="70" r={r}
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 70 70)"
        style={{ transition: 'stroke-dashoffset 1s ease' }}
      />
      <text x="70" y="65" textAnchor="middle" fontSize="22" fontWeight="800" fill="#f5f0e8">
        {pct.toFixed(1)}%
      </text>
      <text x="70" y="84" textAnchor="middle" fontSize="11" fill="#9a9080" fontWeight="500">
        Score
      </text>
    </svg>
  );
}

const DIFF_CLASS: Record<string, string> = {
  Easy:   styles.easy,
  Medium: styles.medium,
  Hard:   styles.hard,
};

type FilterType = 'all' | 'correct' | 'wrong' | 'skipped';

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ResultsPage() {
  const params    = useParams<{ attemptId: string }>();
  const router    = useRouter();
  const attemptId = params.attemptId;

  const [data,           setData]           = useState<ResultsData | null>(null);
  const [loading,        setLoading]        = useState(true);
  const [error,          setError]          = useState('');
  const [tab,            setTab]            = useState<'overview' | 'review'>('overview');
  const [filter,         setFilter]         = useState<FilterType>('all');
  const [animatedScore,  setAnimatedScore]  = useState(0);
  const [openReview,     setOpenReview]     = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const r = await getAttemptResult(parseInt(attemptId, 10));
        if (mounted) setData(r as ResultsData);
      } catch (e: unknown) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load results');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [attemptId]);

  // Animate score counter
  useEffect(() => {
    if (!data) return;
    let frame: number;
    const start    = performance.now();
    const duration = 900;
    const target   = data.score_percentage || 0;
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      setAnimatedScore(Number((target * progress).toFixed(1)));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [data]);

  // ── Loading state ─────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className={styles.page}>
        <Navbar />
        <main className={styles.main}>
          <div className={styles.pageHeader} style={{ marginBottom: 24 }}>
            <div>
              <button className={styles.backBtn} onClick={() => router.push('/dashboard')}>
                Dashboard
              </button>
              <div style={{ height: 32, width: 260, background: 'var(--surface-2)', borderRadius: 6, marginTop: 8 }} />
              <div style={{ height: 14, width: 140, background: 'var(--surface-2)', borderRadius: 4, marginTop: 8 }} />
            </div>
          </div>
          <ResultsSkeleton />
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.page}>
        <Navbar />
        <div className={styles.center}>
          <p className={styles.errorText}>{error}</p>
          <button className={styles.retryBtn} onClick={() => router.push('/dashboard')}>
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    subject, year, score, total_marks, score_percentage: _score_percentage,
    correct_count, wrong_count, skipped_count,
    accuracy, attempt_rate, time_taken_seconds, avg_time_per_question,
    topic_performance, question_reviews,
  } = data;

  const filteredQs = question_reviews.filter((q) => {
    if (filter === 'correct') return q.is_correct;
    if (filter === 'wrong')   return !q.is_correct && q.selected_option;
    if (filter === 'skipped') return !q.selected_option;
    return true;
  });

  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>

        {/* ── Header ── */}
        <div className={styles.pageHeader}>
          <div>
            <button className={styles.backBtn} onClick={() => router.push('/dashboard')}>
              Dashboard
            </button>
            <h1 className={styles.pageTitle}>{subject}</h1>
            <p className={styles.pageSub}>{year} · Attempt #{attemptId}</p>
          </div>
          <button className={styles.reattemptBtn} onClick={() => router.push('/mocks')}>
            Try another paper
          </button>
        </div>

        {/* ── Score hero ── */}
        <div className={styles.scoreHero}>
          <div className={styles.scoreRing}>
            <ScoreRing pct={animatedScore} />
          </div>
          <div className={styles.scoreBreakdown}>
            <div className={styles.sbItem}>
              <span className={styles.sbVal} style={{ color: '#22c55e' }}>{correct_count}</span>
              <span className={styles.sbLbl}>Correct</span>
            </div>
            <div className={styles.sbDivider} />
            <div className={styles.sbItem}>
              <span className={styles.sbVal} style={{ color: '#ef4444' }}>{wrong_count}</span>
              <span className={styles.sbLbl}>Wrong</span>
            </div>
            <div className={styles.sbDivider} />
            <div className={styles.sbItem}>
              <span className={styles.sbVal} style={{ color: '#9a9080' }}>{skipped_count}</span>
              <span className={styles.sbLbl}>Skipped</span>
            </div>
          </div>
          <div className={styles.scoreStats}>
            {[
              { label: 'Raw score',     value: `${score} / ${total_marks}` },
              { label: 'Accuracy',      value: `${accuracy?.toFixed(1)}%` },
              { label: 'Attempt rate',  value: `${attempt_rate?.toFixed(1)}%` },
              { label: 'Total time',    value: formatDuration(time_taken_seconds) },
              { label: 'Avg / question',value: formatDuration(Math.round(avg_time_per_question)) },
            ].map(({ label, value }) => (
              <div key={label} className={styles.ssStat}>
                <span className={styles.ssLabel}>{label}</span>
                <span className={styles.ssValue}>{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Tabs ── */}
        <div className={styles.tabs}>
          {(['overview', 'review'] as const).map((t) => (
            <button
              key={t}
              className={`${styles.tab} ${tab === t ? styles.activeTab : ''}`}
              onClick={() => setTab(t)}
            >
              {t === 'overview' ? 'Topic Overview' : 'Question Review'}
            </button>
          ))}
        </div>

        {/* ── Overview tab ── */}
        {tab === 'overview' && (
          <div className={styles.topicGrid}>
            {topic_performance.length === 0 ? (
              <p className={styles.noData}>No topic data available.</p>
            ) : (
              topic_performance.map((tp) => (
                <div key={tp.topic} className={styles.topicCard}>
                  <div className={styles.tcHeader}>
                    <span className={styles.tcTopic}>{tp.topic}</span>
                    <span
                      className={styles.tcPct}
                      style={{
                        color: tp.accuracy >= 70 ? '#22c55e'
                             : tp.accuracy >= 40 ? '#f59e0b'
                             : '#ef4444',
                      }}
                    >
                      {tp.accuracy}%
                    </span>
                  </div>
                  <div className={styles.tcBar}>
                    <div
                      className={styles.tcFill}
                      style={{
                        width:      `${tp.accuracy}%`,
                        background: tp.accuracy >= 70 ? '#22c55e'
                                  : tp.accuracy >= 40 ? '#f59e0b'
                                  : '#ef4444',
                      }}
                    />
                  </div>
                  <p className={styles.tcDetail}>{tp.correct} correct out of {tp.total}</p>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Review tab ── */}
        {tab === 'review' && (
          <div>
            <div className={styles.filterRow}>
              {(['all', 'correct', 'wrong', 'skipped'] as FilterType[]).map((f) => (
                <button
                  key={f}
                  className={`${styles.filterPill} ${filter === f ? styles.filterActive : ''}`}
                  onClick={() => setFilter(f)}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                  {f === 'all'     && ` (${question_reviews.length})`}
                  {f === 'correct' && ` (${question_reviews.filter(q => q.is_correct).length})`}
                  {f === 'wrong'   && ` (${question_reviews.filter(q => !q.is_correct && q.selected_option).length})`}
                  {f === 'skipped' && ` (${question_reviews.filter(q => !q.selected_option).length})`}
                </button>
              ))}
            </div>

            <div className={styles.reviewList}>
              {filteredQs.map((q, i) => {
                const isCorrect  = q.is_correct;
                const isSkipped  = !q.selected_option;
                const statusCls  = isCorrect ? styles.qCorrect : isSkipped ? styles.qSkipped : styles.qWrong;
                const statusText = isCorrect ? 'Correct' : isSkipped ? 'Skipped' : 'Wrong';
                const isOpen     = openReview === q.question_id;

                return (
                  <div key={q.question_id} className={`${styles.reviewCard} ${statusCls}`}>
                    <button
                      className={styles.rcHeader}
                      onClick={() => setOpenReview(isOpen ? null : q.question_id)}
                      aria-expanded={isOpen}
                    >
                      <span className={styles.rcNum}>Q{i + 1}</span>
                      <div className={styles.rcMeta}>
                        <span className={`${styles.rcDiff} ${DIFF_CLASS[q.difficulty] || ''}`}>
                          {q.difficulty}
                        </span>
                        <span className={styles.rcTopic}>{q.topic}</span>
                      </div>
                      <span className={`${styles.rcStatus} ${statusCls}`}>{statusText}</span>
                      <span
                        className={styles.rcMarks}
                        style={{ color: q.marks_awarded > 0 ? '#22c55e' : '#ef4444' }}
                      >
                        {q.marks_awarded > 0 ? '+' : ''}{q.marks_awarded}
                      </span>
                    </button>

                    {isOpen && (
                      <>
                        <div className={styles.reviewRenderer}>
                          <QuestionRenderer
                            question={{
                              question:      q.question_text,
                              options:       q.options,
                              type:          q.type || 'MCQ',
                              passage:       q.passage,
                              passage_title: q.passage_title,
                              columns:       q.columns as never,
                            }}
                            selectedOption={q.selected_option}
                            showAnswer={true}
                            correctOption={q.correct_option}
                          />
                        </div>

                        {q.explanation && (
                          <div className={styles.explanation}>
                            <span className={styles.expLabel}>Explanation</span>
                            <p className={styles.expText}>{q.explanation}</p>
                          </div>
                        )}

                        <TutorPanel
                          attemptId={parseInt(attemptId, 10)}
                          questionId={q.question_id}
                          isCorrect={q.is_correct}
                        />

                        <div className={styles.rcFooter}>
                          <span className={styles.rcFootItem}>{formatDuration(q.time_spent_seconds)}</span>
                          <span className={styles.rcFootItem}>
                            {q.visit_count} visit{q.visit_count !== 1 ? 's' : ''}
                          </span>
                          {q.answer_changed_count > 0 && (
                            <span className={styles.rcFootItem}>Changed {q.answer_changed_count}x</span>
                          )}
                          {q.was_marked_for_review && (
                            <span className={styles.rcFootItem}>Marked for review</span>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>

      <div className={styles.bottomCtas}>
        <button onClick={() => router.push('/mocks')}>Try another paper</button>
        <button onClick={() => setTab('review')}>Review weak topics</button>
      </div>
    </div>
  );
}