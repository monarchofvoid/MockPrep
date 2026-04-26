import { useState } from "react";
import styles from "../styles/ResultsDashboard.module.css";

const fmtTime = (s) => {
  if (!s) return "0s";
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}m ${s % 60}s` : `${s}s`;
};

function ScoreRing({ pct }) {
  const r = 54;
  const circ = 2 * Math.PI * r;
  const fill = circ - (pct / 100) * circ;
  const color = pct >= 60 ? "#059669" : pct >= 40 ? "#d97706" : "#dc2626";
  return (
    <svg width="140" height="140" viewBox="0 0 140 140" aria-hidden="true">
      <circle cx="70" cy="70" r={r} fill="none" stroke="#e5e7eb" strokeWidth="12" />
      <circle
        cx="70" cy="70" r={r}
        fill="none"
        stroke={color}
        strokeWidth="12"
        strokeDasharray={circ}
        strokeDashoffset={fill}
        strokeLinecap="round"
        transform="rotate(-90 70 70)"
        style={{ transition: "stroke-dashoffset 1s ease" }}
      />
      <text x="70" y="65" textAnchor="middle" fontSize="22" fontWeight="700" fill={color}>
        {Math.round(pct)}%
      </text>
      <text x="70" y="82" textAnchor="middle" fontSize="11" fill="#6b7280">
        score
      </text>
    </svg>
  );
}

function TopicBar({ topic, correct, total, accuracy }) {
  const color = accuracy >= 70 ? "#059669" : accuracy >= 40 ? "#d97706" : "#dc2626";
  return (
    <div className={styles.topicRow}>
      <span className={styles.topicName}>{topic}</span>
      <div className={styles.barBg}>
        <div
          className={styles.barFill}
          style={{ width: `${accuracy}%`, background: color }}
        />
      </div>
      <span className={styles.topicPct} style={{ color }}>
        {correct}/{total}
      </span>
    </div>
  );
}

function ReviewCard({ qr, index }) {
  const [open, setOpen] = useState(false);
  const statusColor = !qr.selected_option
    ? "#6b7280"
    : qr.is_correct
    ? "#059669"
    : "#dc2626";
  const statusLabel = !qr.selected_option
    ? "Skipped"
    : qr.is_correct
    ? "Correct"
    : "Wrong";

  return (
    <div className={styles.reviewCard}>
      <button
        className={styles.reviewHeader}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span
          className={styles.reviewNum}
          style={{ background: statusColor }}
        >
          {index + 1}
        </span>
        <span className={styles.reviewQ}>{qr.question_text}</span>
        <div className={styles.reviewMeta}>
          <span className={styles.statusTag} style={{ color: statusColor }}>
            {statusLabel}
          </span>
          <span className={styles.timeTag}>⏱ {fmtTime(qr.time_spent_seconds)}</span>
          {qr.answer_changed_count > 0 && (
            <span className={styles.changedTag}>
              changed {qr.answer_changed_count}×
            </span>
          )}
          <span className={styles.chevron}>{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open && (
        <div className={styles.reviewBody}>
          <div className={styles.optionGrid}>
            {Object.entries(qr.options).map(([k, v]) => {
              const isCorrect = k === qr.correct_option;
              const isSelected = k === qr.selected_option;
              let cls = styles.revOpt;
              if (isCorrect) cls += " " + styles.correctOpt;
              else if (isSelected && !isCorrect) cls += " " + styles.wrongOpt;
              return (
                <div key={k} className={cls}>
                  <span className={styles.revOptKey}>{k}</span>
                  <span>{v}</span>
                  {isCorrect && <span className={styles.badge}>✓ Correct</span>}
                  {isSelected && !isCorrect && (
                    <span className={styles.badgeWrong}>✗ Your answer</span>
                  )}
                </div>
              );
            })}
          </div>
          <div className={styles.explanation}>
            <span className={styles.expLabel}>Explanation</span>
            <p>{qr.explanation}</p>
          </div>
          <div className={styles.reviewStats}>
            <span>Visits: {qr.visit_count}</span>
            <span>Topic: {qr.topic}</span>
            <span>Difficulty: {qr.difficulty}</span>
            {qr.was_marked_for_review && <span>🔖 Marked for review</span>}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ResultsDashboard({ results, onRestart }) {
  const [activeTab, setActiveTab] = useState("overview");
  const {
    score, total_marks, score_percentage,
    correct_count, wrong_count, skipped_count,
    accuracy, attempt_rate, time_taken_seconds,
    avg_time_per_question, topic_performance,
    question_reviews, subject, year,
  } = results;

  const totalMin = Math.floor(time_taken_seconds / 60);
  const totalSec = time_taken_seconds % 60;

  return (
    <div className={styles.page}>
      {/* ── Hero ───────────────────────────────────────────────── */}
      <div className={styles.hero}>
        <div className={styles.heroLeft}>
          <ScoreRing pct={score_percentage} />
        </div>
        <div className={styles.heroRight}>
          <div className={styles.heroSubject}>{subject} · {year}</div>
          <div className={styles.heroScore}>
            {score}<span className={styles.heroTotal}>/{total_marks}</span>
          </div>
          <div className={styles.heroBadges}>
            <span className={styles.heroBadge} style={{ color: "#059669" }}>
              ✓ {correct_count} correct
            </span>
            <span className={styles.heroBadge} style={{ color: "#dc2626" }}>
              ✗ {wrong_count} wrong
            </span>
            <span className={styles.heroBadge} style={{ color: "#6b7280" }}>
              — {skipped_count} skipped
            </span>
          </div>
        </div>
      </div>

      {/* ── Stat cards ─────────────────────────────────────────── */}
      <div className={styles.statGrid}>
        {[
          { label: "Accuracy", value: `${accuracy}%`, color: "#2563eb" },
          { label: "Attempt Rate", value: `${attempt_rate}%`, color: "#7c3aed" },
          { label: "Time Used", value: `${totalMin}m ${totalSec}s`, color: "#0f766e" },
          { label: "Avg / Question", value: fmtTime(Math.round(avg_time_per_question)), color: "#b45309" },
        ].map(({ label, value, color }) => (
          <div key={label} className={styles.statCard}>
            <div className={styles.statVal} style={{ color }}>{value}</div>
            <div className={styles.statLbl}>{label}</div>
          </div>
        ))}
      </div>

      {/* ── Tabs ───────────────────────────────────────────────── */}
      <div className={styles.tabs}>
        {["overview", "review"].map((t) => (
          <button
            key={t}
            className={`${styles.tab} ${activeTab === t ? styles.activeTab : ""}`}
            onClick={() => setActiveTab(t)}
          >
            {t === "overview" ? "📊 Topic Analysis" : "📋 Solution Review"}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>Topic-wise Performance</h3>
          {[...topic_performance].sort((a, b) => b.accuracy - a.accuracy).map((tp) => (
            <TopicBar key={tp.topic} {...tp} />
          ))}

          <h3 className={styles.sectionTitle} style={{ marginTop: "28px" }}>
            Time Distribution
          </h3>
          <div className={styles.timeGrid}>
            {question_reviews.map((qr, i) => {
              const maxTime = Math.max(...question_reviews.map((r) => r.time_spent_seconds), 1);
              const pct = (qr.time_spent_seconds / maxTime) * 100;
              const color = qr.is_correct ? "#059669" : qr.selected_option ? "#dc2626" : "#9ca3af";
              return (
                <div key={i} className={styles.timeBar} title={`Q${i + 1}: ${fmtTime(qr.time_spent_seconds)}`}>
                  <div
                    className={styles.timeBarFill}
                    style={{ height: `${pct}%`, background: color }}
                  />
                  <span className={styles.timeBarLabel}>{i + 1}</span>
                </div>
              );
            })}
          </div>
          <div className={styles.timeLegend}>
            <span><span style={{ background: "#059669", width: 10, height: 10, display: "inline-block", borderRadius: 2, marginRight: 4 }} />Correct</span>
            <span><span style={{ background: "#dc2626", width: 10, height: 10, display: "inline-block", borderRadius: 2, marginRight: 4 }} />Wrong</span>
            <span><span style={{ background: "#9ca3af", width: 10, height: 10, display: "inline-block", borderRadius: 2, marginRight: 4 }} />Skipped</span>
          </div>
        </div>
      )}

      {activeTab === "review" && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>Solution Review — click any question to expand</h3>
          {question_reviews.map((qr, i) => (
            <ReviewCard key={qr.question_id} qr={qr} index={i} />
          ))}
        </div>
      )}

      <button className={styles.restartBtn} onClick={onRestart}>
        ← Back to Papers
      </button>
    </div>
  );
}
