'use client';

/**
 * VYAS Phase 2A — TutorPanel  (v2.1.1 bugfix)
 * =============================================
 * Renders the "Ask VYAS" button and the AI explanation panel inside an
 * expanded question review card.
 *
 * Props:
 *   attemptId   {number}  — the attempt this question belongs to
 *   questionId  {number}  — the specific question to explain
 *   isCorrect   {boolean} — if true, component renders nothing
 *
 * v2.1.1 changes:
 *   - TutorData.explanation type updated from Record<string, string> to
 *     TutorExplanation interface. The old type was incorrect: it typed all
 *     values as string, which hid that `steps` is an array and that
 *     `why_wrong`/`follow_up` were the correct key names (vs the old
 *     backend's `common_mistake`/`mnemonic`).
 *   - SECTION_LABELS/SECTION_ICONS keys now match the backend response
 *     exactly: why_wrong and follow_up (backend schemas/tutor.py also fixed).
 *   - Error message now shows the server-side error detail when available,
 *     making payment / credit errors (402) readable to the user.
 *   - Improved error display: distinguishes credit errors from generic errors.
 */

import { useState } from 'react';
import { getTutorExplanation, isApiError, sanitizeMessage } from '@/lib/api';
import styles from '@/styles/TutorPanel.module.css';

// ── Types — mirroring backend schemas.TutorExplanation ───────────────────────

interface TutorExplanation {
  opening: string;
  core_concept: string;
  why_correct: string;
  memory_anchor: string;
  // Optional fields — names match AI prompt output AND backend schema
  why_wrong?: string | null;    // was missing from old interface
  follow_up?: string | null;    // was missing from old interface
  steps?: string[] | null;
  formula?: string | null;
  [key: string]: unknown;       // allow any extra fields from AI
}

interface TutorData {
  interaction_id: number;
  question_id: string;
  proficiency_level: string;
  proficiency_score: number;
  was_cache_hit: boolean;
  behavioral_note?: string | null;
  explanation: TutorExplanation;
}

// ── Section configuration ─────────────────────────────────────────────────────
// Keys match the AI prompt JSON output AND backend TutorExplanation schema fields.

const SECTION_LABELS: Record<string, string> = {
  opening:       'What Happened',
  core_concept:  'Core Concept',
  why_correct:   'Why Correct',
  why_wrong:     'Why Wrong',      // was "common_mistake" in old backend — now fixed
  memory_anchor: 'Remember This',
  follow_up:     'Challenge',      // was "mnemonic" in old backend — now fixed
};

const SECTION_ICONS: Record<string, string> = {
  opening:       '🔍',
  core_concept:  '💡',
  why_correct:   '✅',
  why_wrong:     '❌',
  memory_anchor: '🧠',
  follow_up:     '🎯',
};

const LEVEL_COLORS: Record<string, string> = {
  Beginner:     '#22c55e',
  Intermediate: '#f59e0b',
  Advanced:     '#3b82f6',
  Expert:       '#a855f7',
};

// ── Main component ────────────────────────────────────────────────────────────

interface TutorPanelProps {
  attemptId:  number;
  questionId: number;
  isCorrect:  boolean;
}

type PanelState = 'idle' | 'loading' | 'success' | 'error';

// Distinguish credit errors so the UI can show a top-up prompt
interface ErrorState {
  message: string;
  isCreditsError: boolean;
}

export default function TutorPanel({ attemptId, questionId, isCorrect }: TutorPanelProps) {
  const [state,     setState]  = useState<PanelState>('idle');
  const [data,      setData]   = useState<TutorData | null>(null);
  const [errorInfo, setErrorInfo] = useState<ErrorState>({ message: '', isCreditsError: false });

  if (isCorrect) return null;

  const handleAsk = async (forceRefresh = false) => {
    setState('loading');
    setErrorInfo({ message: '', isCreditsError: false });
    try {
      const res = await getTutorExplanation(attemptId, String(questionId), forceRefresh);
      setData(res);
      setState('success');
    } catch (e: unknown) {
      let message = 'Could not load explanation. Please try again.';
      let isCreditsError = false;

      if (isApiError(e)) {
        // Credit / payment errors (402)
        if (e.status === 402 || e.code === 'insufficient_credits') {
          isCreditsError = true;
          message = sanitizeMessage(e.message) || 'Not enough credits. Please top up your wallet.';
        } else {
          message = sanitizeMessage(e.message) || message;
        }
      }

      setErrorInfo({ message, isCreditsError });
      setState('error');
    }
  };

  const levelColor = data ? (LEVEL_COLORS[data.proficiency_level] || '#d4a843') : '#d4a843';
  const exp = data?.explanation;

  return (
    <div className={styles.wrapper}>
      {/* ── Trigger button ── */}
      {state === 'idle' && (
        <button className={styles.askBtn} onClick={() => handleAsk()}>
          <span className={styles.askIcon}>✦</span>
          Ask VYAS
        </button>
      )}

      {/* ── Loading ── */}
      {state === 'loading' && (
        <div className={styles.loadingRow}>
          <span className={styles.spinner} />
          <span className={styles.loadingText}>VYAS is thinking…</span>
        </div>
      )}

      {/* ── Error ── */}
      {state === 'error' && (
        <div className={styles.errorBox}>
          <span>
            {errorInfo.isCreditsError ? '💳 ' : '⚠ '}
            {errorInfo.message}
          </span>
          {errorInfo.isCreditsError ? (
            <a className={styles.retryBtn} href="/wallet">Top up wallet</a>
          ) : (
            <button className={styles.retryBtn} onClick={() => handleAsk()}>Retry</button>
          )}
        </div>
      )}

      {/* ── Explanation panel ── */}
      {state === 'success' && data && exp && (
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div className={styles.panelTitle}>
              <span className={styles.vyasGlyph}>✦</span>
              <span>VYAS Explanation</span>
            </div>
            <div className={styles.panelMeta}>
              <span
                className={styles.levelBadge}
                style={{
                  background:  `${levelColor}22`,
                  color:       levelColor,
                  borderColor: `${levelColor}44`,
                }}
              >
                {data.proficiency_level}
              </span>
              {data.was_cache_hit && (
                <span className={styles.cacheBadge} title="Served from cache">⚡ cached</span>
              )}
              <button
                className={styles.refreshBtn}
                onClick={() => handleAsk(true)}
                title="Regenerate explanation"
              >
                ↺
              </button>
            </div>
          </div>

          {data.behavioral_note && (
            <div className={styles.behaviorNote}>
              <span className={styles.noteIcon}>💬</span>
              <span>{data.behavioral_note}</span>
            </div>
          )}

          <div className={styles.sections}>
            {Object.entries(SECTION_LABELS).map(([key, label]) => {
              const content = exp[key];
              // Skip null/undefined sections (e.g. why_wrong when skipped,
              // follow_up for Beginner/Intermediate levels)
              if (content === null || content === undefined || content === '') return null;
              // steps is an array — join for display (schema allows it but prompt
              // doesn't usually output it; guard here just in case)
              const displayText = Array.isArray(content) ? content.join(' ') : String(content);
              return (
                <div key={key} className={`${styles.section} ${styles[`section_${key}`] || ''}`}>
                  <div className={styles.sectionHeader}>
                    <span className={styles.sectionIcon}>{SECTION_ICONS[key]}</span>
                    <span className={styles.sectionLabel}>{label}</span>
                  </div>
                  <p className={styles.sectionContent}>{displayText}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
