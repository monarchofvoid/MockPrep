/**
 * TopicIntelligence — Dynamic expandable topic performance panel
 *
 * Shows strong / average / weak topics derived from ALL past attempts.
 * Groups by subject. Expandable per tier. Updates every time analytics refreshes.
 */

import { useState } from "react";
import styles from "../styles/TopicIntelligence.module.css";

// ── Helpers ───────────────────────────────────────────────────────────────────

function AccuracyBar({ pct, color }) {
  return (
    <div className={styles.bar}>
      <div
        className={styles.barFill}
        style={{ width: `${Math.min(pct, 100)}%`, background: color }}
      />
    </div>
  );
}

function strengthMeta(strength) {
  return {
    strong:  { color: "#059669", bg: "#d1fae5", border: "#6ee7b7", label: "Strong",  icon: "🟢" },
    average: { color: "#d97706", bg: "#fef3c7", border: "#fcd34d", label: "Average", icon: "🟡" },
    weak:    { color: "#dc2626", bg: "#fee2e2", border: "#fca5a5", label: "Weak",    icon: "🔴" },
  }[strength] || { color: "#6b7280", bg: "#f3f4f6", border: "#e5e7eb", label: "—", icon: "⚪" };
}

// ── Topic row ─────────────────────────────────────────────────────────────────

function TopicRow({ item, rank }) {
  const meta = strengthMeta(item.strength);
  return (
    <div className={styles.topicRow}>
      <span className={styles.rank}>#{rank}</span>
      <div className={styles.topicInfo}>
        <div className={styles.topicHeader}>
          <span className={styles.topicName}>{item.topic}</span>
          <span className={styles.subjectTag}>{item.subject}</span>
        </div>
        <AccuracyBar pct={item.accuracy} color={meta.color} />
      </div>
      <div className={styles.topicStats}>
        <span className={styles.accuracy} style={{ color: meta.color }}>
          {item.accuracy}%
        </span>
        <span className={styles.fraction}>{item.correct}/{item.total} correct</span>
      </div>
    </div>
  );
}

// ── Tier section ──────────────────────────────────────────────────────────────

function TierSection({ strength, items, defaultExpanded = false }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const meta     = strengthMeta(strength);
  const preview  = items.slice(0, 3);
  const rest     = items.slice(3);
  const hasMore  = rest.length > 0;

  if (items.length === 0) return null;

  return (
    <div className={styles.tier} style={{ borderColor: meta.border }}>
      {/* Tier header */}
      <button
        className={styles.tierHeader}
        onClick={() => setExpanded(e => !e)}
        style={{ background: meta.bg }}
      >
        <div className={styles.tierLeft}>
          <span className={styles.tierIcon}>{meta.icon}</span>
          <span className={styles.tierLabel} style={{ color: meta.color }}>
            {meta.label} Topics
          </span>
          <span className={styles.tierCount} style={{ color: meta.color }}>
            {items.length}
          </span>
        </div>
        <div className={styles.tierRight}>
          <span className={styles.tierHint} style={{ color: meta.color }}>
            {strength === "strong"  && "Keep practising these"}
            {strength === "average" && "Room to improve"}
            {strength === "weak"    && "Focus here next"}
          </span>
          <span className={styles.chevron} style={{ color: meta.color }}>
            {expanded ? "▲" : "▼"}
          </span>
        </div>
      </button>

      {/* Always show top 3 */}
      <div className={styles.tierBody}>
        {preview.map((item, i) => (
          <TopicRow key={item.topic} item={item} rank={i + 1} />
        ))}

        {/* Expandable rest */}
        {hasMore && (
          <>
            <div className={`${styles.expandableRows} ${expanded ? styles.expandableOpen : ""}`}>
              {rest.map((item, i) => (
                <TopicRow key={item.topic} item={item} rank={preview.length + i + 1} />
              ))}
            </div>
            <button
              className={styles.showMoreBtn}
              style={{ color: meta.color }}
              onClick={() => setExpanded(e => !e)}
            >
              {expanded
                ? `Show less ▲`
                : `Show ${rest.length} more topic${rest.length !== 1 ? "s" : ""} ▼`}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

/**
 * @param {Array}  topicMastery  — array of TopicMastery objects from /analytics/me
 * @param {number} totalAttempts — total submitted attempts (to show "not enough data" state)
 */
export default function TopicIntelligence({ topicMastery = [], totalAttempts = 0 }) {
  const [filterSubject, setFilterSubject] = useState("all");

  // Derive unique subjects for filter pills
  const subjects = ["all", ...Array.from(new Set(topicMastery.map(t => t.subject))).sort()];

  // Apply subject filter
  const filtered = filterSubject === "all"
    ? topicMastery
    : topicMastery.filter(t => t.subject === filterSubject);

  const strong  = filtered.filter(t => t.strength === "strong");
  const average = filtered.filter(t => t.strength === "average");
  const weak    = filtered.filter(t => t.strength === "weak");

  // Not enough data yet
  if (totalAttempts === 0 || topicMastery.length === 0) {
    return (
      <div className={styles.emptyState}>
        <span className={styles.emptyIcon}>🧠</span>
        <p className={styles.emptyTitle}>Topic intelligence builds over time</p>
        <p className={styles.emptySub}>
          Complete at least one mock test and VYAS will automatically analyse
          your topic-level strengths and weaknesses here.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.panelHeader}>
        <div>
          <h2 className={styles.panelTitle}>🧠 Topic Intelligence</h2>
          <p className={styles.panelSub}>
            Based on {topicMastery.reduce((s, t) => s + t.total, 0)} questions
            across {totalAttempts} attempt{totalAttempts !== 1 ? "s" : ""}.
            Updates after every submission.
          </p>
        </div>

        {/* Subject filter pills */}
        {subjects.length > 2 && (
          <div className={styles.subjectFilter}>
            {subjects.map(s => (
              <button
                key={s}
                className={`${styles.subjectPill} ${filterSubject === s ? styles.subjectPillActive : ""}`}
                onClick={() => setFilterSubject(s)}
              >
                {s === "all" ? "All subjects" : s}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Tiers */}
      <div className={styles.tiers}>
        <TierSection strength="strong"  items={strong}  defaultExpanded={true}  />
        <TierSection strength="average" items={average} defaultExpanded={false} />
        <TierSection strength="weak"    items={weak}    defaultExpanded={true}  />

        {filtered.length === 0 && (
          <p className={styles.noMatch}>
            No topics found for "{filterSubject}".
          </p>
        )}
      </div>

      {/* Legend */}
      <div className={styles.legend}>
        <span className={styles.legendItem}>🟢 ≥ 70% accuracy = Strong</span>
        <span className={styles.legendItem}>🟡 40–69% = Average</span>
        <span className={styles.legendItem}>🔴 &lt; 40% = Weak</span>
        <span className={styles.legendItem}>Min. 2 questions to appear</span>
      </div>
    </div>
  );
}
