import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { getMocks, startAttempt } from "../api/client";
import Navbar from "../components/Navbar";
import MockBrowserSkeleton from "../components/skeletons/MockBrowserSkeleton";
import styles from "../styles/MockBrowser.module.css";
import aiStyles from "../styles/AIMockBanner.module.css";   // Phase 2B

function inferDifficulty(mock) {
  if (mock.question_count >= 80) return "Advanced";
  if (mock.question_count >= 40) return "Standard";
  return "Focused";
}

function MockCard({ mock, onStart, starting }) {
  return (
    <article className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.examBadge}>{mock.exam}</span>
        <span className={styles.difficulty}>{inferDifficulty(mock)}</span>
      </div>
      <h3 className={styles.cardTitle}>{mock.subject}</h3>
      <p className={styles.cardYear}>{mock.year || "Practice paper"}</p>
      <div className={styles.cardMeta}>
        <div><span>Questions</span><strong>{mock.question_count}</strong></div>
        <div><span>Duration</span><strong>{mock.duration_minutes}m</strong></div>
        <div><span>Marks</span><strong>{mock.total_marks}</strong></div>
      </div>
      <button className={styles.startBtn} onClick={() => onStart(mock.id)} disabled={starting === mock.id}>
        {starting === mock.id ? "Starting..." : "Start test →"}
      </button>
    </article>
  );
}

export default function MockBrowser() {
  const navigate = useNavigate();
  const [mocks, setMocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(null);
  const [query, setQuery] = useState("");
  const [examFilter, setExamFilter] = useState("all");
  const [yearFilter, setYearFilter] = useState("all");

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await getMocks();
        if (mounted) setMocks(data);
      } catch (e) {
        if (mounted) setError(e.message);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const handleStart = async (mockId) => {
    setStarting(mockId);
    try {
      const attempt = await startAttempt(mockId);
      navigate(`/test/${attempt.attempt_id}`, { state: { attemptData: attempt } });
    } catch (e) {
      setError(e.message);
      setStarting(null);
    }
  };

  const exams = useMemo(() => ["all", ...Array.from(new Set(mocks.map((m) => m.exam))).sort()], [mocks]);
  const years = useMemo(() => ["all", ...Array.from(new Set(mocks.map((m) => m.year).filter(Boolean))).sort()], [mocks]);

  const filtered = mocks.filter((mock) => {
    const q = query.toLowerCase();
    const matchesQuery = !q ||
      mock.subject.toLowerCase().includes(q) ||
      mock.year.toLowerCase().includes(q) ||
      mock.exam.toLowerCase().includes(q);
    const matchesExam = examFilter === "all" || mock.exam === examFilter;
    const matchesYear = yearFilter === "all" || mock.year === yearFilter;
    return matchesQuery && matchesExam && matchesYear;
  });

  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>
        <section className={styles.pageHeader}>
          <span className={styles.kicker}>Mock library</span>
          <h1 className={styles.pageTitle}>Choose your next ascent</h1>
          <p className={styles.pageSub}>Filter papers by exam and year, then enter a timed practice environment.</p>
        </section>

        {/* Phase 2B: AI Mock Generator entry banner */}
        <div className={aiStyles.banner} onClick={() => navigate("/ai-mock")}>
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
        </div>

        <section className={styles.filters}>
          <input
            type="text"
            placeholder="Search subject, exam, or year"
            className={styles.searchInput}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select className={styles.select} value={examFilter} onChange={(e) => setExamFilter(e.target.value)}>
            {exams.map((exam) => (
              <option key={exam} value={exam}>{exam === "all" ? "All exams" : exam}</option>
            ))}
          </select>
          <select className={styles.select} value={yearFilter} onChange={(e) => setYearFilter(e.target.value)}>
            {years.map((year) => (
              <option key={year} value={year}>{year === "all" ? "All years" : year}</option>
            ))}
          </select>
        </section>

        {error && (
          <div className={styles.errorBox}>
            <span>{error}</span>
            <button onClick={() => { setError(""); window.location.reload(); }}>Retry</button>
          </div>
        )}

        {loading && <MockBrowserSkeleton />}

        {!loading && !error && (
          <>
            <p className={styles.resultCount}>{filtered.length} paper{filtered.length !== 1 ? "s" : ""} available</p>
            {filtered.length === 0 ? (
              <div className={styles.emptyState}>
                <p>No papers match the current filters.</p>
                <button className={styles.clearBtn} onClick={() => { setQuery(""); setExamFilter("all"); setYearFilter("all"); }}>
                  Reset filters
                </button>
              </div>
            ) : (
              <div className={styles.grid}>
                {filtered.map((mock) => (
                  <MockCard key={mock.id} mock={mock} onStart={handleStart} starting={starting} />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}