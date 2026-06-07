'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import MockBrowserSkeleton from '@/components/skeletons/Mockbrowserskeleton';
import { listMocks, startAttempt, type MockTest } from '@/lib/api';
import { writeHandoff, type AttemptHandoff, type Question } from '@/lib/utils';
import styles from '@/styles/MockBrowser.module.css';
import aiStyles from '@/styles/AIMockBanner.module.css';

// ── Types ─────────────────────────────────────────────────────────────────────

// Use MockTest directly from api.ts — local Mock interface removed to avoid
// year-type mismatch (MockTest.year is number|undefined, not string).

function inferDifficulty(mock: MockTest): string {
  const qCount = mock.question_count ?? mock.num_questions ?? 0;
  if (qCount >= 80) return 'Advanced';
  if (qCount >= 40) return 'Standard';
  return 'Focused';
}

// ── MockCard ──────────────────────────────────────────────────────────────────

function MockCard({
  mock,
  onStart,
  starting,
}: {
  mock: MockTest;
  onStart: (id: string) => void;
  starting: string | null;
}) {
  const yearDisplay = mock.year != null ? String(mock.year) : '';
  return (
    <article className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={mock.is_ai_generated ? styles.aiExamBadge : styles.examBadge}>
          {mock.is_ai_generated ? 'AI Mock' : mock.exam}
        </span>
        <span className={styles.difficulty}>{inferDifficulty(mock)}</span>
      </div>
      <h3 className={styles.cardTitle}>{mock.subject}</h3>
      <p className={styles.cardYear}>
        {mock.is_ai_generated ? `${mock.exam} - ${yearDisplay || 'AI Generated'}` : yearDisplay || 'Practice paper'}
      </p>
      <div className={styles.cardMeta}>
        <div><span>Questions</span><strong>{mock.question_count ?? mock.num_questions ?? '—'}</strong></div>
        <div><span>Duration</span><strong>{mock.duration_minutes ?? '—'}m</strong></div>
        <div><span>Marks</span><strong>{mock.total_marks ?? '—'}</strong></div>
      </div>
      <button
        className={styles.startBtn}
        onClick={() => onStart(mock.id)}
        disabled={starting === mock.id}
      >
        {starting === mock.id ? 'Starting…' : 'Start test →'}
      </button>
    </article>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MocksPage() {
  const router = useRouter();

  const [mocks,      setMocks]      = useState<MockTest[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState('');
  const [starting,   setStarting]   = useState<string | null>(null);
  const [query,      setQuery]      = useState('');
  const [examFilter, setExamFilter] = useState('all');
  const [yearFilter, setYearFilter] = useState('all');

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await listMocks();
        if (mounted) setMocks(data);
      } catch (e: unknown) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load mocks');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const handleStart = async (mockId: string) => {
    setStarting(mockId);
    try {
      const attempt = await startAttempt(mockId);
      // Write handoff data so TestPage can read it on arrival
      const handoffData: AttemptHandoff = {
        questions:        (attempt.questions as unknown as Question[]) || [],
        duration_minutes: attempt.duration_minutes || 90,
        total_marks:      attempt.total_marks || 100,
        mock_id:          attempt.mock_id || mockId,
        attempt_id:       attempt.attempt_id || attempt.id,
      };
      writeHandoff(handoffData);
      router.push(`/test/${attempt.attempt_id || attempt.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start test');
      setStarting(null);
    }
  };

  const exams = useMemo(
    () => ['all', ...Array.from(new Set(mocks.map((m) => m.exam))).sort()],
    [mocks],
  );
  const years = useMemo(() => {
    // Exclude AI-generated mocks from the year filter dropdown.
    // year may be number|undefined — stringify for dropdown option values.
    const realYears = mocks
      .filter((m) => !m.is_ai_generated)
      .map((m) => (m.year != null ? String(m.year) : null))
      .filter((y): y is string => Boolean(y));
    return ['all', ...Array.from(new Set(realYears)).sort()];
  }, [mocks]);

  const filtered = mocks.filter((mock) => {
    const q = query.toLowerCase();
    const yearStr = mock.year != null ? String(mock.year) : '';
    const matchesQuery =
      !q ||
      mock.subject.toLowerCase().includes(q) ||
      yearStr.toLowerCase().includes(q) ||
      mock.exam.toLowerCase().includes(q);
    const matchesExam = examFilter === 'all' || mock.exam === examFilter;
    // AI mocks always pass the year filter
    const matchesYear =
      mock.is_ai_generated ||
      yearFilter === 'all' ||
      yearStr === yearFilter;
    return matchesQuery && matchesExam && matchesYear;
  });

  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>

        <section className={styles.pageHeader}>
          <span className={styles.kicker}>Mock library</span>
          <h1 className={styles.pageTitle}>Choose your next ascent</h1>
          <p className={styles.pageSub}>
            Filter papers by exam and year, then enter a timed practice environment.
          </p>
        </section>

        {/* AI Mock Generator entry banner */}
        <Link href="/ai-mock" className={aiStyles.banner}>
          <div className={aiStyles.bannerLeft}>
            <span className={aiStyles.glyph}>✦</span>
            <div>
              <span className={aiStyles.bannerTitle}>AI Mock Generator</span>
              <span className={aiStyles.bannerSub}>
                Get a personalised test adapted to your proficiency level — questions generated on demand
              </span>
            </div>
          </div>
          <span className={aiStyles.bannerArrow}>→</span>
        </Link>

        <section className={styles.filters}>
          <input
            type="text"
            placeholder="Search subject, exam, or year"
            className={styles.searchInput}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            className={styles.select}
            value={examFilter}
            onChange={(e) => setExamFilter(e.target.value)}
          >
            {exams.map((exam) => (
              <option key={exam} value={exam}>{exam === 'all' ? 'All exams' : exam}</option>
            ))}
          </select>
          <select
            className={styles.select}
            value={yearFilter}
            onChange={(e) => setYearFilter(e.target.value)}
          >
            {years.map((year) => (
              <option key={year} value={year}>{year === 'all' ? 'All years' : year}</option>
            ))}
          </select>
        </section>

        {error && (
          <div className={styles.errorBox}>
            <span>{error}</span>
            <button onClick={() => { setError(''); window.location.reload(); }}>Retry</button>
          </div>
        )}

        {loading && <MockBrowserSkeleton />}

        {!loading && !error && (
          <>
            <p className={styles.resultCount}>
              {filtered.length} paper{filtered.length !== 1 ? 's' : ''} available
            </p>
            {filtered.length === 0 ? (
              <div className={styles.emptyState}>
                <p>No papers match the current filters.</p>
                <button
                  className={styles.clearBtn}
                  onClick={() => { setQuery(''); setExamFilter('all'); setYearFilter('all'); }}
                >
                  Reset filters
                </button>
              </div>
            ) : (
              <div className={styles.grid}>
                {filtered.map((mock) => (
                  <MockCard
                    key={mock.id}
                    mock={mock}
                    onStart={handleStart}
                    starting={starting}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}