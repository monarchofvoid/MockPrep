/**
 * VYAS Phase 2A — TutorPanel
 * ===========================
 * Renders the "Ask VYAS" button and the AI explanation panel inside an
 * expanded question review card.
 *
 * Props:
 *   attemptId   {number}   - the attempt this question belongs to
 *   questionId  {number}   - the specific question to explain
 *   isCorrect   {boolean}  - if true, component renders nothing (tutor only for wrong/skipped)
 */

import { useState } from "react";
import { getTutorExplanation, rateTutorExplanation } from "../api/client";
import styles from "../styles/TutorPanel.module.css";

const SECTION_LABELS = {
  opening:       "What Happened",
  core_concept:  "Core Concept",
  why_correct:   "Why Correct",
  why_wrong:     "Why Wrong",
  memory_anchor: "Remember This",
  follow_up:     "Challenge",
};

const SECTION_ICONS = {
  opening:       "🔍",
  core_concept:  "💡",
  why_correct:   "✅",
  why_wrong:     "❌",
  memory_anchor: "🧠",
  follow_up:     "🎯",
};

const LEVEL_COLORS = {
  Beginner:     "#22c55e",
  Intermediate: "#f59e0b",
  Advanced:     "#3b82f6",
  Expert:       "#a855f7",
};

function StarRating({ interactionId, onRated }) {
  const [hovered, setHovered] = useState(0);
  const [selected, setSelected] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const handleRate = async (rating) => {
    if (selected || submitting) return;
    setSubmitting(true);
    try {
      await rateTutorExplanation(interactionId, rating);
      setSelected(rating);
      onRated?.(rating);
    } catch {
      // silently fail — rating is optional
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.starRow}>
      <span className={styles.starLabel}>
        {selected ? "Thanks for your feedback!" : "Rate this explanation"}
      </span>
      <div className={styles.stars}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            className={`${styles.star} ${
              n <= (hovered || selected) ? styles.starActive : ""
            }`}
            onMouseEnter={() => !selected && setHovered(n)}
            onMouseLeave={() => !selected && setHovered(0)}
            onClick={() => handleRate(n)}
            disabled={!!selected || submitting}
            aria-label={`Rate ${n} star${n > 1 ? "s" : ""}`}
          >
            ★
          </button>
        ))}
      </div>
    </div>
  );
}

export default function TutorPanel({ attemptId, questionId, isCorrect }) {
  const [state, setState] = useState("idle"); // idle | loading | success | error
  const [data, setData]   = useState(null);
  const [error, setError] = useState("");

  // Don't render anything for correct answers
  if (isCorrect) return null;

  const handleAsk = async () => {
    if (state === "loading") return;
    setState("loading");
    setError("");
    try {
      const res = await getTutorExplanation(attemptId, questionId);
      setData(res);
      setState("success");
    } catch (e) {
      setError(e.message || "Could not load explanation. Please try again.");
      setState("error");
    }
  };

  const handleRefresh = async () => {
    setState("loading");
    setError("");
    try {
      const res = await getTutorExplanation(attemptId, questionId, true);
      setData(res);
      setState("success");
    } catch (e) {
      setError(e.message || "Could not refresh explanation.");
      setState("error");
    }
  };

  const levelColor = data ? (LEVEL_COLORS[data.proficiency_level] || "#d4a843") : "#d4a843";
  const exp = data?.explanation;

  return (
    <div className={styles.wrapper}>
      {/* ── Trigger button ─────────────────────────────────────────── */}
      {state === "idle" && (
        <button className={styles.askBtn} onClick={handleAsk}>
          <span className={styles.askIcon}>✦</span>
          Ask VYAS
        </button>
      )}

      {/* ── Loading ────────────────────────────────────────────────── */}
      {state === "loading" && (
        <div className={styles.loadingRow}>
          <span className={styles.spinner} />
          <span className={styles.loadingText}>VYAS is thinking…</span>
        </div>
      )}

      {/* ── Error ──────────────────────────────────────────────────── */}
      {state === "error" && (
        <div className={styles.errorBox}>
          <span>⚠ {error}</span>
          <button className={styles.retryBtn} onClick={handleAsk}>Retry</button>
        </div>
      )}

      {/* ── Explanation panel ──────────────────────────────────────── */}
      {state === "success" && data && exp && (
        <div className={styles.panel}>
          {/* Header */}
          <div className={styles.panelHeader}>
            <div className={styles.panelTitle}>
              <span className={styles.vyasGlyph}>✦</span>
              <span>VYAS Explanation</span>
            </div>
            <div className={styles.panelMeta}>
              <span
                className={styles.levelBadge}
                style={{ background: `${levelColor}22`, color: levelColor, borderColor: `${levelColor}44` }}
              >
                {data.proficiency_level}
              </span>
              {data.was_cache_hit && (
                <span className={styles.cacheBadge} title="Served from cache">⚡ cached</span>
              )}
              <button
                className={styles.refreshBtn}
                onClick={handleRefresh}
                title="Regenerate explanation"
              >
                ↺
              </button>
            </div>
          </div>

          {/* Behavioral note */}
          {data.behavioral_note && (
            <div className={styles.behaviorNote}>
              <span className={styles.noteIcon}>💬</span>
              <span>{data.behavioral_note}</span>
            </div>
          )}

          {/* Explanation sections */}
          <div className={styles.sections}>
            {Object.entries(SECTION_LABELS).map(([key, label]) => {
              const content = exp[key];
              if (!content) return null;
              return (
                <div key={key} className={`${styles.section} ${styles[`section_${key}`] || ""}`}>
                  <div className={styles.sectionHeader}>
                    <span className={styles.sectionIcon}>{SECTION_ICONS[key]}</span>
                    <span className={styles.sectionLabel}>{label}</span>
                  </div>
                  <p className={styles.sectionContent}>{content}</p>
                </div>
              );
            })}
          </div>

          {/* Rating */}
          <StarRating interactionId={data.interaction_id} />
        </div>
      )}
    </div>
  );
}
