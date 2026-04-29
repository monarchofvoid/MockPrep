import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getResults } from "../api/client";
import Navbar from "../components/Navbar";
import styles from "../styles/ResultsPage.module.css";

function ScoreRing({ pct }) {
  const r = 54;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  const color = pct >= 70 ? "#059669" : pct >= 40 ? "#d97706" : "#dc2626";

  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} fill="none" stroke="#f3f4f6" strokeWidth="10" />
      <circle
        cx="70" cy="70" r={r}
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 70 70)"
        style={{ transition: "stroke-dashoffset 1s ease" }}
      />
      <text x="70" y="65" textAnchor="middle" fontSize="22" fontWeight="800" fill="#0f1e3d">
        {pct.toFixed(1)}%
      </text>
      <text x="70" y="84" textAnchor="middle" fontSize="11" fill="#9ca3af" fontWeight="500">
        Score
      </text>
    </svg>
  );
}

function fmt(s) {
  if (!s) return "—";
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

const DIFF_CLASS = {
  Easy:   styles.easy,
  Medium: styles.medium,
  Hard:   styles.hard,
};

export default function ResultsPage() {
  const { attemptId } = useParams();
  const navigate      = useNavigate();

  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");
  const [tab,     setTab]     = useState("overview"); // "overview" | "review"
  const [filter,  setFilter]  = useState("all");      // "all" | "correct" | "wrong" | "skipped"

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const r = await getResults(parseInt(attemptId));
        if (mounted) setData(r);
      } catch (e) {
        if (mounted) setError(e.message);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [attemptId]);

  if (loading) return (
    <div className={styles.page}>
      <Navbar />
      <div className={styles.center}>
        <div className="spinner" />
        <p className={styles.loadingText}>Loading your results…</p>
      </div>
    </div>
  );

  if (error) return (
    <div className={styles.page}>
      <Navbar />
      <div className={styles.center}>
        <p className={styles.errorText}>⚠️ {error}</p>
        <button className={styles.retryBtn} onClick={() => navigate("/dashboard")}>
          Back to Dashboard
        </button>
      </div>
    </div>
  );

  const {
    subject, year, score, total_marks, score_percentage,
    correct_count, wrong_count, skipped_count,
    accuracy, attempt_rate, time_taken_seconds, avg_time_per_question,
    topic_performance, question_reviews,
  } = data;

  const filteredQs = question_reviews.filter((q) => {
    if (filter === "correct") return q.is_correct;
    if (filter === "wrong")   return !q.is_correct && q.selected_option;
    if (filter === "skipped") return !q.selected_option;
    return true;
  });

  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>

        {/* ── Header ─────────────────────────────────────────────── */}
        <div className={styles.pageHeader}>
          <div>
            <button className={styles.backBtn} onClick={() => navigate("/dashboard")}>
              ← Dashboard
            </button>
            <h1 className={styles.pageTitle}>{subject}</h1>
            <p className={styles.pageSub}>{year} · Attempt #{attemptId}</p>
          </div>
          <button className={styles.reattemptBtn} onClick={() => navigate("/mocks")}>
            Try another mock →
          </button>
        </div>

        {/* ── Score hero ─────────────────────────────────────────── */}
        <div className={styles.scoreHero}>
          <div className={styles.scoreRing}>
            <ScoreRing pct={score_percentage} />
          </div>
          <div className={styles.scoreBreakdown}>
            <div className={styles.sbItem}>
              <span className={styles.sbVal} style={{ color: "#059669" }}>{correct_count}</span>
              <span className={styles.sbLbl}>Correct</span>
            </div>
            <div className={styles.sbDivider} />
            <div className={styles.sbItem}>
              <span className={styles.sbVal} style={{ color: "#dc2626" }}>{wrong_count}</span>
              <span className={styles.sbLbl}>Wrong</span>
            </div>
            <div className={styles.sbDivider} />
            <div className={styles.sbItem}>
              <span className={styles.sbVal} style={{ color: "#6b7280" }}>{skipped_count}</span>
              <span className={styles.sbLbl}>Skipped</span>
            </div>
          </div>
          <div className={styles.scoreStats}>
            <div className={styles.ssStat}>
              <span className={styles.ssLabel}>Raw score</span>
              <span className={styles.ssValue}>{score} / {total_marks}</span>
            </div>
            <div className={styles.ssStat}>
              <span className={styles.ssLabel}>Accuracy</span>
              <span className={styles.ssValue}>{accuracy?.toFixed(1)}%</span>
            </div>
            <div className={styles.ssStat}>
              <span className={styles.ssLabel}>Attempt rate</span>
              <span className={styles.ssValue}>{attempt_rate?.toFixed(1)}%</span>
            </div>
            <div className={styles.ssStat}>
              <span className={styles.ssLabel}>Total time</span>
              <span className={styles.ssValue}>{fmt(time_taken_seconds)}</span>
            </div>
            <div className={styles.ssStat}>
              <span className={styles.ssLabel}>Avg / question</span>
              <span className={styles.ssValue}>{fmt(Math.round(avg_time_per_question))}</span>
            </div>
          </div>
        </div>

        {/* ── Tabs ───────────────────────────────────────────────── */}
        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${tab === "overview" ? styles.activeTab : ""}`}
            onClick={() => setTab("overview")}
          >
            Topic Overview
          </button>
          <button
            className={`${styles.tab} ${tab === "review" ? styles.activeTab : ""}`}
            onClick={() => setTab("review")}
          >
            Question Review
          </button>
        </div>

        {/* ── Overview tab ───────────────────────────────────────── */}
        {tab === "overview" && (
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
                        color: tp.accuracy >= 70 ? "#059669"
                             : tp.accuracy >= 40 ? "#d97706"
                             : "#dc2626"
                      }}
                    >
                      {tp.accuracy}%
                    </span>
                  </div>
                  <div className={styles.tcBar}>
                    <div
                      className={styles.tcFill}
                      style={{
                        width: `${tp.accuracy}%`,
                        background: tp.accuracy >= 70 ? "#059669"
                                  : tp.accuracy >= 40 ? "#d97706"
                                  : "#dc2626"
                      }}
                    />
                  </div>
                  <p className={styles.tcDetail}>
                    {tp.correct} correct out of {tp.total}
                  </p>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Review tab ─────────────────────────────────────────── */}
        {tab === "review" && (
          <div>
            {/* Filter pills */}
            <div className={styles.filterRow}>
              {["all", "correct", "wrong", "skipped"].map((f) => (
                <button
                  key={f}
                  className={`${styles.filterPill} ${filter === f ? styles.filterActive : ""}`}
                  onClick={() => setFilter(f)}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                  {f === "all"     && ` (${question_reviews.length})`}
                  {f === "correct" && ` (${question_reviews.filter(q => q.is_correct).length})`}
                  {f === "wrong"   && ` (${question_reviews.filter(q => !q.is_correct && q.selected_option).length})`}
                  {f === "skipped" && ` (${question_reviews.filter(q => !q.selected_option).length})`}
                </button>
              ))}
            </div>

            {/* Question cards */}
            <div className={styles.reviewList}>
              {filteredQs.map((q, i) => {
                const isCorrect  = q.is_correct;
                const isSkipped  = !q.selected_option;
                const statusCls  = isCorrect ? styles.qCorrect : isSkipped ? styles.qSkipped : styles.qWrong;
                const statusText = isCorrect ? "✓ Correct" : isSkipped ? "— Skipped" : "✗ Wrong";

                return (
                  <div key={q.question_id} className={`${styles.reviewCard} ${statusCls}`}>
                    <div className={styles.rcHeader}>
                      <span className={styles.rcNum}>Q{i + 1}</span>
                      <div className={styles.rcMeta}>
                        <span className={`${styles.rcDiff} ${DIFF_CLASS[q.difficulty] || ""}`}>
                          {q.difficulty}
                        </span>
                        <span className={styles.rcTopic}>{q.topic}</span>
                      </div>
                      <span className={`${styles.rcStatus} ${statusCls}`}>{statusText}</span>
                      <span className={styles.rcMarks} style={{ color: q.marks_awarded > 0 ? "#059669" : "#dc2626" }}>
                        {q.marks_awarded > 0 ? "+" : ""}{q.marks_awarded}
                      </span>
                    </div>

                    <p className={styles.rcQuestion}>{q.question_text}</p>

                    {/* Options */}
                    <div className={styles.rcOptions}>
                      {Object.entries(q.options).map(([key, val]) => {
                        const isSelected = q.selected_option === key;
                        const isCorrectOpt = q.correct_option === key;
                        let optClass = styles.rcOpt;
                        if (isCorrectOpt) optClass += ` ${styles.rcOptCorrect}`;
                        else if (isSelected && !isCorrectOpt) optClass += ` ${styles.rcOptWrong}`;

                        return (
                          <div key={key} className={optClass}>
                            <span className={styles.rcOptKey}>{key}</span>
                            <span className={styles.rcOptVal}>{val}</span>
                            {isSelected && !isCorrectOpt && (
                              <span className={styles.rcOptTag} style={{ color: "#dc2626" }}>Your answer</span>
                            )}
                            {isCorrectOpt && (
                              <span className={styles.rcOptTag} style={{ color: "#059669" }}>Correct</span>
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {/* Explanation */}
                    {q.explanation && (
                      <div className={styles.explanation}>
                        <span className={styles.expLabel}>💡 Explanation</span>
                        <p className={styles.expText}>{q.explanation}</p>
                      </div>
                    )}

                    {/* Time & behavior */}
                    <div className={styles.rcFooter}>
                      <span className={styles.rcFootItem}>⏱ {fmt(q.time_spent_seconds)}</span>
                      <span className={styles.rcFootItem}>👁 {q.visit_count} visit{q.visit_count !== 1 ? "s" : ""}</span>
                      {q.answer_changed_count > 0 && (
                        <span className={styles.rcFootItem}>🔄 Changed {q.answer_changed_count}×</span>
                      )}
                      {q.was_marked_for_review && (
                        <span className={styles.rcFootItem}>🔖 Marked for review</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
