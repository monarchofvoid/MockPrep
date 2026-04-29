import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getMyAnalytics, getMyAttempts } from "../api/client";
import Navbar from "../components/Navbar";
import styles from "../styles/Dashboard.module.css";

function StatCard({ label, value, sub, accent }) {
  return (
    <div className={styles.statCard}>
      <p className={styles.statLabel}>{label}</p>
      <p className={styles.statValue} style={accent ? { color: accent } : {}}>{value}</p>
      {sub && <p className={styles.statSub}>{sub}</p>}
    </div>
  );
}

function fmt(seconds) {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function scoreColor(pct) {
  if (pct >= 70) return "#059669";
  if (pct >= 40) return "#d97706";
  return "#dc2626";
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate  = useNavigate();

  const [analytics, setAnalytics] = useState(null);
  const [attempts,  setAttempts]  = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState("");

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [ana, att] = await Promise.all([getMyAnalytics(), getMyAttempts()]);
        if (mounted) { setAnalytics(ana); setAttempts(att); }
      } catch (e) {
        if (mounted) setError(e.message);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>
        {/* Welcome */}
        <div className={styles.welcome}>
          <div>
            <h1 className={styles.welcomeTitle}>
              Welcome back, {user?.name?.split(" ")[0]} 👋
            </h1>
            <p className={styles.welcomeSub}>Here's your performance overview.</p>
          </div>
          <button className={styles.startBtn} onClick={() => navigate("/mocks")}>
            Start a mock test →
          </button>
        </div>

        {loading && (
          <div className={styles.center}>
            <div className="spinner" />
            <p className={styles.loadingText}>Loading your analytics…</p>
          </div>
        )}

        {error && !loading && (
          <div className={styles.errorBox}>
            <p>⚠️ {error}</p>
            <button onClick={() => window.location.reload()}>Retry</button>
          </div>
        )}

        {!loading && !error && analytics && (
          <>
            {/* Stats row */}
            <div className={styles.statsRow}>
              <StatCard
                label="Total Attempts"
                value={analytics.total_attempts}
              />
              <StatCard
                label="Avg Score"
                value={`${analytics.avg_score_percentage?.toFixed(1) ?? "—"}%`}
                accent={analytics.avg_score_percentage
                  ? scoreColor(analytics.avg_score_percentage) : undefined}
              />
              <StatCard
                label="Avg Accuracy"
                value={`${analytics.avg_accuracy?.toFixed(1) ?? "—"}%`}
              />
              <StatCard
                label="Strongest Topic"
                value={analytics.strongest_topic || "—"}
                sub="Keep it up!"
                accent="#059669"
              />
              <StatCard
                label="Weakest Topic"
                value={analytics.weakest_topic || "—"}
                sub="Focus here"
                accent="#dc2626"
              />
            </div>

            {/* Recent attempts */}
            <div className={styles.section}>
              <div className={styles.sectionHeader}>
                <h2 className={styles.sectionTitle}>Recent Attempts</h2>
                <button className={styles.browseLink} onClick={() => navigate("/mocks")}>
                  Browse papers →
                </button>
              </div>

              {attempts.length === 0 ? (
                <div className={styles.emptyState}>
                  <p className={styles.emptyIcon}>📄</p>
                  <p className={styles.emptyTitle}>No attempts yet</p>
                  <p className={styles.emptySub}>
                    Take your first mock test and your results will appear here.
                  </p>
                  <button className={styles.startBtn} onClick={() => navigate("/mocks")}>
                    Browse mock tests →
                  </button>
                </div>
              ) : (
                <div className={styles.tableWrapper}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Paper</th>
                        <th>Year</th>
                        <th>Score</th>
                        <th>Accuracy</th>
                        <th>Time</th>
                        <th>Status</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {attempts.map((a) => {
                        const pct = a.total_marks
                          ? ((a.score / a.total_marks) * 100).toFixed(1)
                          : null;
                        return (
                          <tr key={a.attempt_id}>
                            <td className={styles.paperCell}>
                              <span className={styles.subjectTag}>{a.subject}</span>
                            </td>
                            <td>{a.year || "—"}</td>
                            <td>
                              {pct != null ? (
                                <span
                                  className={styles.scoreBadge}
                                  style={{ color: scoreColor(parseFloat(pct)) }}
                                >
                                  {a.score}/{a.total_marks} ({pct}%)
                                </span>
                              ) : "—"}
                            </td>
                            <td>{a.accuracy != null ? `${a.accuracy.toFixed(1)}%` : "—"}</td>
                            <td>{fmt(a.time_taken_seconds)}</td>
                            <td>
                              <span className={a.submitted
                                ? styles.badgeDone : styles.badgePending}>
                                {a.submitted ? "Submitted" : "In progress"}
                              </span>
                            </td>
                            <td>
                              {a.submitted && (
                                <button
                                  className={styles.viewBtn}
                                  onClick={() => navigate(`/results/${a.attempt_id}`)}
                                >
                                  View results
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
