/**
 * VYAS Phase 2B — AIMockGeneratorPage
 * =====================================
 * Route: /ai-mock (protected)
 *
 * Two-panel layout:
 *   Left  — Generation form (exam / subject / difficulty / count)
 *   Right — User's AI mock history (scores + links)
 *
 * On successful generation: navigates to /test/{attempt_id}
 * (TestEngine is unchanged — it receives the same StartAttemptResponse shape)
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { generateAIMock, getAIMockHistory, getRecommendations } from "../api/client";  // Phase 3: +getRecommendations
import Navbar from "../components/Navbar";
import HistorySkeleton from "../components/skeletons/HistorySkeleton";
import styles from "../styles/AIMockGeneratorPage.module.css";

// ── Static option lists ────────────────────────────────────────────────────────

const EXAMS = ["CUET", "GATE", "JEE", "UPSC", "CAT", "CLAT", "Other"];

const SUBJECTS_BY_EXAM = {
  CUET:  ["Economics", "Business Studies", "Accountancy", "English", "General Test",
          "History", "Political Science", "Geography", "Sociology", "Psychology"],
  GATE:  ["Computer Science", "Electronics", "Mechanical", "Civil", "Electrical",
          "Chemical", "Biotechnology", "Mathematics"],
  JEE:   ["Physics", "Chemistry", "Mathematics"],
  UPSC:  ["History", "Geography", "Polity", "Economy", "Environment", "Science & Technology",
          "Current Affairs", "Ethics"],
  CAT:   ["Verbal Ability", "Quantitative Aptitude", "DILR"],
  CLAT:  ["English Language", "Current Affairs", "Legal Reasoning",
          "Logical Reasoning", "Quantitative Techniques"],
  Other: ["General Knowledge", "Reasoning", "Aptitude"],
};

const DIFFICULTY_OPTIONS = [
  { value: "auto",   label: "Auto (based on my level)", icon: "✦" },
  { value: "easy",   label: "Easy",                     icon: "🟢" },
  { value: "medium", label: "Medium",                   icon: "🟡" },
  { value: "hard",   label: "Hard",                     icon: "🔴" },
];

const COUNT_OPTIONS = [5, 10, 15, 20];

// ── History item ───────────────────────────────────────────────────────────────

function HistoryCard({ item, onReopen }) {
  const pct   = item.total_marks ? Math.round((item.score / item.total_marks) * 100) : null;
  const color = pct == null ? "#6f6659" : pct >= 70 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <div className={styles.historyCard}>
      <div className={styles.historyLeft}>
        <span className={styles.historySubject}>{item.subject}</span>
        <span className={styles.historyMeta}>
          {item.exam} · {item.question_count}q · {item.difficulty}
        </span>
      </div>
      <div className={styles.historyRight}>
        {pct != null ? (
          <span className={styles.historyScore} style={{ color }}>
            {pct}%
          </span>
        ) : (
          <span className={styles.historyPending}>Not submitted</span>
        )}
        {item.attempt_id && (
          <button
            className={styles.historyViewBtn}
            onClick={() => onReopen(item.attempt_id)}
          >
            {pct != null ? "View results" : "Continue →"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function AIMockGeneratorPage() {
  const navigate = useNavigate();

  // ── Form state ──────────────────────────────────────────────────────────────
  const [exam,       setExam]       = useState("CUET");
  const [subject,    setSubject]    = useState("Economics");
  const [difficulty, setDifficulty] = useState("auto");
  const [count,      setCount]      = useState(10);

  const [generating, setGenerating] = useState(false);
  const [genError,   setGenError]   = useState("");

  // Progress UX: time-based estimation (no websocket needed)
  // Estimate: ~12s per batch, batch size = 5, so 20q = 4 batches ≈ 50s total
  const [genProgress,   setGenProgress]   = useState(0);
  const [genStatusMsg,  setGenStatusMsg]  = useState("");

  // ── History state ────────────────────────────────────────────────────────────
  const [history,        setHistory]        = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // ── Phase 3: Proficiency state for personalisation badge + pre-fill ──────────
  const [hasProficiency,  setHasProficiency]  = useState(false);
  const [aiSuggestion,    setAiSuggestion]    = useState(null);

  // Update subject when exam changes
  const handleExamChange = (e) => {
    const val = e.target.value;
    setExam(val);
    setSubject((SUBJECTS_BY_EXAM[val] || ["General"])[0]);
  };

  // ── Load history ─────────────────────────────────────────────────────────────
  const loadHistory = useCallback(async () => {
    try {
      const [data, rec] = await Promise.all([
        getAIMockHistory(),
        getRecommendations(),   // Phase 3: get proficiency + AI suggestion
      ]);
      setHistory(data.ai_mocks || []);
      setHasProficiency(rec.has_proficiency_data || false);

      // Pre-fill form with the recommendation if it exists
      const sugg = rec.ai_mock_suggestion;
      if (sugg) {
        setAiSuggestion(sugg);
        if (EXAMS.includes(sugg.exam))           setExam(sugg.exam);
        const subjectList = SUBJECTS_BY_EXAM[sugg.exam] || ["General"];
        if (subjectList.includes(sugg.subject))  setSubject(sugg.subject);
        if (["easy","medium","hard"].includes(sugg.difficulty)) setDifficulty(sugg.difficulty);
      }
    } catch {
      // silently fail — recommendations are non-critical
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // ── Generate handler ─────────────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (generating) return;
    setGenerating(true);
    setGenError("");
    setGenProgress(0);
    setGenStatusMsg("Connecting to AI…");

    // Time-based progress: estimate total time from question count.
    // Each batch of 5 takes ~12s on Groq free tier (conservative).
    const BATCH_SIZE    = 5;
    const SECS_PER_BATCH = 13;
    const n_batches      = Math.ceil(count / BATCH_SIZE);
    const estimatedSecs  = n_batches * SECS_PER_BATCH + 3; // +3 for overhead

    const BATCH_MESSAGES = [
      "Crafting your questions…",
      "Generating more questions…",
      "Building your mock test…",
      "Almost there…",
    ];

    let elapsed = 0;
    const intervalMs = 800;
    const progressInterval = setInterval(() => {
      elapsed += intervalMs / 1000;
      const pct = Math.min(92, Math.round((elapsed / estimatedSecs) * 100));
      setGenProgress(pct);

      // Update status message at batch boundaries
      const batchIdx = Math.min(
        Math.floor(elapsed / SECS_PER_BATCH),
        BATCH_MESSAGES.length - 1
      );
      setGenStatusMsg(
        n_batches > 1
          ? `${BATCH_MESSAGES[batchIdx]} (part ${batchIdx + 1} of ${n_batches})`
          : BATCH_MESSAGES[0]
      );
    }, intervalMs);

    try {
      const result = await generateAIMock(exam, subject, difficulty, count, true);
      clearInterval(progressInterval);
      setGenProgress(100);
      setGenStatusMsg("Done! Loading your test…");
      navigate(`/test/${result.attempt_id}`, {
        state: {
          attemptData: {
            questions:        result.questions,
            duration_minutes: result.duration_minutes,
            total_marks:      result.total_marks,
            mock_id:          result.mock_id,
          },
        },
      });
    } catch (e) {
      clearInterval(progressInterval);
      setGenProgress(0);
      setGenStatusMsg("");
      // Provide friendlier messages for known server errors
      const raw = e.message || "";
      let friendlyMsg = raw;
      if (raw.includes("timed out") || raw.includes("504")) {
        friendlyMsg = "Generation timed out — the AI is busy. Please retry in a moment.";
      } else if (raw.includes("rate limit") || raw.includes("503") || raw.includes("429")) {
        friendlyMsg = "AI service is busy right now. Please wait 30 seconds and retry.";
      } else if (raw.includes("invalid response") || raw.includes("502")) {
        friendlyMsg = "AI returned an unexpected response. Please retry.";
      }
      setGenError(friendlyMsg || "Generation failed. Please try again.");
      setGenerating(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>

        {/* ── Page header ─────────────────────────────────────────── */}
        <div className={styles.pageHeader}>
          <div>
            <button className={styles.backBtn} onClick={() => navigate("/mocks")}>
              ← Back to Papers
            </button>
            <h1 className={styles.title}>
              <span className={styles.vyasGlyph}>✦</span> AI Mock Generator
            </h1>
            <p className={styles.subtitle}>
              Generate a personalised practice test in seconds.
              Questions are adapted to your proficiency level.
            </p>
            {/* Phase 3: Personalisation badge */}
            {hasProficiency && (
              <div className={styles.adaptiveBadge}>
                <span>✦</span>
                <span>Adapted to your profile — difficulty and topics tuned to your ELO</span>
              </div>
            )}
            {/* Phase 3: AI suggestion callout */}
            {aiSuggestion && (
              <div className={styles.suggestionBox}>
                <span className={styles.suggIcon}>🎯</span>
                <span className={styles.suggText}>{aiSuggestion.reason}</span>
              </div>
            )}
          </div>
        </div>

        <div className={styles.layout}>

          {/* ── Left: Form ────────────────────────────────────────── */}
          <div className={styles.formPanel}>
            <h2 className={styles.panelTitle}>Configure Your Mock</h2>

            {/* Exam */}
            <div className={styles.field}>
              <label className={styles.label}>Exam</label>
              <select className={styles.select} value={exam} onChange={handleExamChange}>
                {EXAMS.map((e) => (
                  <option key={e} value={e}>{e}</option>
                ))}
              </select>
            </div>

            {/* Subject */}
            <div className={styles.field}>
              <label className={styles.label}>Subject</label>
              <select
                className={styles.select}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              >
                {(SUBJECTS_BY_EXAM[exam] || ["General"]).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            {/* Difficulty */}
            <div className={styles.field}>
              <label className={styles.label}>Difficulty</label>
              <div className={styles.diffGrid}>
                {DIFFICULTY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    className={`${styles.diffBtn} ${difficulty === opt.value ? styles.diffActive : ""}`}
                    onClick={() => setDifficulty(opt.value)}
                  >
                    <span>{opt.icon}</span>
                    <span>{opt.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Question count */}
            <div className={styles.field}>
              <label className={styles.label}>Number of Questions</label>
              <div className={styles.countRow}>
                {COUNT_OPTIONS.map((n) => (
                  <button
                    key={n}
                    className={`${styles.countBtn} ${count === n ? styles.countActive : ""}`}
                    onClick={() => setCount(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <p className={styles.fieldHint}>
                ~{Math.round(count * 2.5)} minutes · {count * 4} total marks
              </p>
            </div>

            {/* Error */}
            {genError && (
              <div className={styles.errorBox}>
                <span>⚠ {genError}</span>
              </div>
            )}

            {/* Generate button */}
            <button
              className={styles.generateBtn}
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? (
                <>
                  <span className={styles.btnSpinner} />
                  <span>{genStatusMsg || `Generating ${count} questions…`}</span>
                </>
              ) : (
                <>
                  <span className={styles.vyasGlyph}>✦</span>
                  <span>Generate Mock Test</span>
                </>
              )}
            </button>

            {/* Progress bar */}
            {generating && (
              <div className={styles.progressWrap}>
                <div
                  className={styles.progressBar}
                  style={{ width: `${genProgress}%` }}
                />
                <p className={styles.generatingNote}>
                  {count > 5
                    ? `Generating in ${Math.ceil(count / 5)} batches — this takes ${Math.ceil(count / 5) * 13}–${Math.ceil(count / 5) * 16} seconds.`
                    : "This takes 10–15 seconds."}
                </p>
              </div>
            )}
          </div>

          {/* ── Right: History ────────────────────────────────────── */}
          <div className={styles.historyPanel}>
            <h2 className={styles.panelTitle}>Your AI Mock History</h2>

            {historyLoading ? (
              <HistorySkeleton />
            ) : history.length === 0 ? (
              <div className={styles.historyEmpty}>
                <span className={styles.emptyIcon}>📋</span>
                <p>No AI mocks yet. Generate one to get started!</p>
              </div>
            ) : (
              <div className={styles.historyList}>
                {history.map((item) => (
                  <HistoryCard
                    key={item.mock_id}
                    item={item}
                    onReopen={(id) => navigate(`/results/${id}`)}
                  />
                ))}
              </div>
            )}
          </div>

        </div>
      </main>
    </div>
  );
}