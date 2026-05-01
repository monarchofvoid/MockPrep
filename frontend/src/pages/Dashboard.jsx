import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAuth } from "../context/AuthContext";
import { getMyAnalytics, getMyAttempts } from "../api/client";
import Navbar from "../components/Navbar";
import styles from "../styles/Dashboard.module.css";

function StatCard({ label, value, sub, tone = "gold" }) {
  return (
    <div className={styles.statCard} data-tone={tone}>
      <p className={styles.statLabel}>{label}</p>
      <p className={styles.statValue}>{value}</p>
      {sub && <p className={styles.statSub}>{sub}</p>}
    </div>
  );
}

function fmt(seconds) {
  if (!seconds) return "-";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function scoreColor(pct) {
  if (pct >= 70) return "var(--success)";
  if (pct >= 40) return "var(--warning)";
  return "var(--danger)";
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [analytics, setAnalytics] = useState(null);
  const [attempts, setAttempts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [ana, att] = await Promise.all([getMyAnalytics(), getMyAttempts()]);
        if (mounted) {
          setAnalytics(ana);
          setAttempts(att);
        }
      } catch (e) {
        if (mounted) setError(e.message);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const trendData = useMemo(() => {
    return [...attempts]
      .filter((attempt) => attempt.submitted && attempt.total_marks)
      .reverse()
      .map((attempt, index) => ({
        label: `A${index + 1}`,
        score: Number(((attempt.score / attempt.total_marks) * 100).toFixed(1)),
        accuracy: Number((attempt.accuracy || 0).toFixed(1)),
      }));
  }, [attempts]);

  const topicData = useMemo(() => {
    return (analytics?.topic_mastery || [])
      .slice()
      .sort((a, b) => b.total - a.total)
      .slice(0, 8)
      .map((topic) => ({
        name: topic.topic.length > 18 ? `${topic.topic.slice(0, 18)}...` : topic.topic,
        accuracy: topic.accuracy,
        fill: scoreColor(topic.accuracy),
      }));
  }, [analytics]);

  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>
        <section className={styles.welcome}>
          <div>
            <span className={styles.kicker}>Performance command</span>
            <h1 className={styles.welcomeTitle}>Welcome back, {user?.name?.split(" ")[0]}</h1>
            <p className={styles.welcomeSub}>Your preparation signal, pace, and mastery in one place.</p>
          </div>
          <button className={styles.startBtn} onClick={() => navigate("/mocks")}>
            Start a mock test →
          </button>
        </section>

        {loading && (
          <div className={styles.center}>
            <div className="spinner" />
            <p className={styles.loadingText}>Loading your analytics...</p>
          </div>
        )}

        {error && !loading && (
          <div className={styles.errorBox}>
            <p>{error}</p>
            <button onClick={() => window.location.reload()}>Retry</button>
          </div>
        )}

        {!loading && !error && analytics && (
          <>
            <section className={styles.statsRow}>
              <StatCard label="Total attempts" value={analytics.total_attempts} sub="Completed and active sessions" />
              <StatCard
                label="Avg score"
                value={`${analytics.avg_score_percentage?.toFixed(1) ?? "-"}%`}
                sub="Across submitted attempts"
                tone="blue"
              />
              <StatCard
                label="Avg accuracy"
                value={`${analytics.avg_accuracy?.toFixed(1) ?? "-"}%`}
                sub="Correct among attempted"
                tone="green"
              />
            </section>

            <section className={styles.chartGrid}>
              <div className={styles.panel}>
                <div className={styles.panelHeader}>
                  <div>
                    <h2 className={styles.panelTitle}>Score trajectory</h2>
                    <p className={styles.panelSub}>Score percentage over submitted attempts</p>
                  </div>
                </div>
                <div className={styles.chartBox}>
                  {trendData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={trendData}>
                        <CartesianGrid stroke="rgba(212,168,67,0.08)" vertical={false} />
                        <XAxis dataKey="label" stroke="#9a9080" tickLine={false} axisLine={false} />
                        <YAxis stroke="#9a9080" tickLine={false} axisLine={false} domain={[0, 100]} />
                        <Tooltip contentStyle={{ background: "#111", border: "1px solid #2a2a2a", borderRadius: 12 }} />
                        <Line type="monotone" dataKey="score" stroke="#d4a843" strokeWidth={3} dot={{ r: 4, fill: "#d4a843" }} />
                        <Line type="monotone" dataKey="accuracy" stroke="#3b82f6" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className={styles.emptyChart}>Complete a mock to unlock your score line.</div>
                  )}
                </div>
              </div>

              <div className={styles.panel}>
                <div className={styles.panelHeader}>
                  <div>
                    <h2 className={styles.panelTitle}>Topic mastery</h2>
                    <p className={styles.panelSub}>Green 70%+, amber 40-70%, red below 40%</p>
                  </div>
                </div>
                <div className={styles.chartBox}>
                  {topicData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={topicData} layout="vertical" margin={{ left: 12, right: 20 }}>
                        <CartesianGrid stroke="rgba(212,168,67,0.08)" horizontal={false} />
                        <XAxis type="number" domain={[0, 100]} stroke="#9a9080" tickLine={false} axisLine={false} />
                        <YAxis dataKey="name" type="category" stroke="#9a9080" tickLine={false} axisLine={false} width={116} />
                        <Tooltip contentStyle={{ background: "#111", border: "1px solid #2a2a2a", borderRadius: 12 }} />
                        <Bar dataKey="accuracy" radius={[0, 8, 8, 0]}>
                          {topicData.map((entry) => (
                            <Cell key={entry.name} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className={styles.emptyChart}>Topic mastery appears after submissions.</div>
                  )}
                </div>
              </div>
            </section>

            <section className={styles.section}>
              <div className={styles.sectionHeader}>
                <div>
                  <h2 className={styles.sectionTitle}>Recent attempts</h2>
                  <p className={styles.sectionSub}>Continue reviewing what you have already earned.</p>
                </div>
                <button className={styles.browseLink} onClick={() => navigate("/mocks")}>
                  Browse papers →
                </button>
              </div>

              {attempts.length === 0 ? (
                <div className={styles.emptyState}>
                  <p className={styles.emptyTitle}>No attempts yet</p>
                  <p className={styles.emptySub}>Take your first mock test and your results will appear here.</p>
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
                      {attempts.map((attempt) => {
                        const pct = attempt.total_marks
                          ? ((attempt.score / attempt.total_marks) * 100).toFixed(1)
                          : null;
                        return (
                          <tr key={attempt.attempt_id}>
                            <td className={styles.paperCell}>{attempt.subject}</td>
                            <td>{attempt.year || "-"}</td>
                            <td>
                              {pct != null ? (
                                <span className={styles.scoreBadge} style={{ color: scoreColor(parseFloat(pct)) }}>
                                  {attempt.score}/{attempt.total_marks} ({pct}%)
                                </span>
                              ) : "-"}
                            </td>
                            <td>{attempt.accuracy != null ? `${attempt.accuracy.toFixed(1)}%` : "-"}</td>
                            <td>{fmt(attempt.time_taken_seconds)}</td>
                            <td>
                              <span className={attempt.submitted ? styles.badgeDone : styles.badgePending}>
                                {attempt.submitted ? "Submitted" : "In progress"}
                              </span>
                            </td>
                            <td>
                              {attempt.submitted && (
                                <button className={styles.viewBtn} onClick={() => navigate(`/results/${attempt.attempt_id}`)}>
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
            </section>
          </>
        )}
      </main>
    </div>
  );
}
