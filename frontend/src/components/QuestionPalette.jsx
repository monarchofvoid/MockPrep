import styles from "../styles/QuestionPalette.module.css";

/**
 * Returns the display status for a question in the palette:
 * unvisited | visited | answered | marked | answered_marked
 */
export function getStatus(qs) {
  if (qs.selectedOption && qs.markedForReview) return "answered_marked";
  if (qs.selectedOption) return "answered";
  if (qs.markedForReview) return "marked";
  if (qs.visitCount > 0) return "visited";
  return "unvisited";
}

const STATUS_LABEL = {
  unvisited: "Not visited",
  visited: "Visited",
  answered: "Answered",
  marked: "Marked for review",
  answered_marked: "Answered & marked",
};

export default function QuestionPalette({
  questions,
  questionStates,
  currentIndex,
  onJump,
}) {
  const counts = {
    answered: 0,
    visited: 0,
    marked: 0,
    answered_marked: 0,
    unvisited: 0,
  };
  questionStates.forEach((qs) => {
    counts[getStatus(qs)]++;
  });

  return (
    <aside className={styles.sidebar} aria-label="Question palette">
      <div className={styles.header}>Question Palette</div>

      {/* Summary counts */}
      <div className={styles.counts}>
        <div className={`${styles.countBadge} ${styles.answered}`}>
          {counts.answered + counts.answered_marked} Answered
        </div>
        <div className={`${styles.countBadge} ${styles.marked}`}>
          {counts.marked + counts.answered_marked} Marked
        </div>
        <div className={`${styles.countBadge} ${styles.notAttempted}`}>
          {counts.unvisited + counts.visited} Not done
        </div>
      </div>

      {/* Grid */}
      <div className={styles.grid} role="list">
        {questions.map((_, i) => {
          const st = getStatus(questionStates[i]);
          return (
            <button
              key={i}
              role="listitem"
              aria-label={`Question ${i + 1}: ${STATUS_LABEL[st]}`}
              className={`${styles.cell} ${styles[st]} ${
                i === currentIndex ? styles.active : ""
              }`}
              onClick={() => onJump(i)}
            >
              {i + 1}
            </button>
          );
        })}
      </div>

      {/* Legend */}
      <div className={styles.legend} aria-hidden="true">
        {[
          { key: "unvisited", label: "Not visited" },
          { key: "visited", label: "Visited, unanswered" },
          { key: "answered", label: "Answered" },
          { key: "marked", label: "Marked for review" },
          { key: "answered_marked", label: "Answered + marked" },
        ].map(({ key, label }) => (
          <div key={key} className={styles.legRow}>
            <span className={`${styles.legDot} ${styles[key]}`} />
            <span className={styles.legLabel}>{label}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}
