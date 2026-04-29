import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getMocks, startAttempt } from "../api/client";
import Navbar from "../components/Navbar";
import styles from "../styles/MockBrowser.module.css";

const SUBJECT_ICONS = {
  "Database Management Systems": "🗄️",
  "Operating Systems": "💻",
  "Computer Networks": "🌐",
  "Data Structures": "🌳",
  "Algorithms": "⚙️",
  "default": "📄",
};

function getIcon(subject) {
  return SUBJECT_ICONS[subject] || SUBJECT_ICONS.default;
}

function MockCard({ mock, onStart, starting }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.cardIcon}>{getIcon(mock.subject)}</span>
        <span className={styles.examBadge}>{mock.exam}</span>
      </div>
      <h3 className={styles.cardTitle}>{mock.subject}</h3>
      <p className={styles.cardYear}>{mock.year}</p>
      <div className={styles.cardMeta}>
        <span className={styles.metaItem}>
          <span className={styles.metaIcon}>⏱</span>
          {mock.duration_minutes} min
        </span>
        <span className={styles.metaDivider} />
        <span className={styles.metaItem}>
          <span className={styles.metaIcon}>📝</span>
          {mock.question_count} questions
        </span>
        <span className={styles.metaDivider} />
        <span className={styles.metaItem}>
          <span className={styles.metaIcon}>⭐</span>
          {mock.total_marks} marks
        </span>
      </div>
      <button
        className={styles.startBtn}
        onClick={() => onStart(mock.id)}
        disabled={starting === mock.id}
      >
        {starting === mock.id ? "Starting…" : "Start test →"}
      </button>
    </div>
  );
}

export default function MockBrowser() {
  const navigate  = useNavigate();
  const [mocks,    setMocks]    = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState("");
  const [starting, setStarting] = useState(null); // mock_id currently being started
  const [filter,   setFilter]   = useState("");

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

  const filtered = mocks.filter((m) => {
    const q = filter.toLowerCase();
    return (
      !q ||
      m.subject.toLowerCase().includes(q) ||
      m.year.toLowerCase().includes(q) ||
      m.exam.toLowerCase().includes(q)
    );
  });

  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.pageHeader}>
          <div>
            <h1 className={styles.pageTitle}>Mock Test Library</h1>
            <p className={styles.pageSub}>
              Choose a paper and start practising. Results saved automatically.
            </p>
          </div>
        </div>

        {/* Search */}
        <div className={styles.searchBar}>
          <span className={styles.searchIcon}>🔍</span>
          <input
            type="text"
            placeholder="Search by subject, exam, or year…"
            className={styles.searchInput}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          {filter && (
            <button className={styles.clearSearch} onClick={() => setFilter("")}>✕</button>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className={styles.errorBox}>
            ⚠️ {error}
            <button onClick={() => { setError(""); window.location.reload(); }}>Retry</button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className={styles.center}>
            <div className="spinner" />
            <p className={styles.loadingText}>Loading papers…</p>
          </div>
        )}

        {/* Grid */}
        {!loading && !error && (
          <>
            {filtered.length === 0 ? (
              <div className={styles.emptyState}>
                <p>No papers found matching "{filter}"</p>
                <button className={styles.clearBtn} onClick={() => setFilter("")}>
                  Clear search
                </button>
              </div>
            ) : (
              <>
                <p className={styles.resultCount}>
                  {filtered.length} paper{filtered.length !== 1 ? "s" : ""} available
                </p>
                <div className={styles.grid}>
                  {filtered.map((m) => (
                    <MockCard
                      key={m.id}
                      mock={m}
                      onStart={handleStart}
                      starting={starting}
                    />
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
