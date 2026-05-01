/**
 * QuestionRenderer — Smart question display component for VYAS
 *
 * Handles all GATE/competitive exam question formats:
 *   • Standard MCQ
 *   • Passage-based (comprehension)
 *   • Match-the-following (two-column)
 *   • Statement-based (True/False pairs, Assertion-Reason)
 *   • Code/technical block questions
 *   • Numeric answer type (NAT) — display only
 */

import styles from "../styles/QuestionRenderer.module.css";

// ── Type detection ────────────────────────────────────────────────────────────

/**
 * Infer the display format from the question object.
 * The JSON `type` field is the primary signal; content heuristics are fallback.
 */
function detectFormat(question) {
  const type = (question.type || "").toLowerCase().trim();
  const text  = (question.question || "").toLowerCase();

  if (type === "passage" || type === "comprehension")          return "passage";
  if (type === "match" || type === "match_the_following")      return "match";
  if (type === "statement" || type === "assertion_reason")     return "statement";
  if (type === "nat" || type === "numerical")                  return "nat";
  if (type === "code" || type === "program")                   return "code";

  // Heuristic fallbacks when type is just "MCQ" but content tells more
  if (question.passage || question.paragraph)                  return "passage";
  if (question.columns || question.left_column)                return "match";

  // Text-level heuristics
  if (/match\s+(the\s+)?following|column\s*[–-]?\s*[12I]|list\s*[–-]?\s*[12I]/i.test(text))
    return "match";
  if (/^(passage|read\s+the\s+following|consider\s+the\s+following\s+passage)/i.test(text))
    return "passage";
  if (/statement\s*[–-]?\s*(i|ii|1|2)|assertion.*reason/i.test(text))
    return "statement";
  if (hasCodeBlock(question.question))
    return "code";

  return "standard";
}

function hasCodeBlock(text = "") {
  return /```[\s\S]*```/.test(text) ||
         /`[^`]+`/.test(text) ||
         /^\s{4,}\S/m.test(text) ||
         /<code>|<pre>/i.test(text);
}

// ── Text processors ───────────────────────────────────────────────────────────

/**
 * Split question text into a passage block + the actual question sentence.
 * Convention: passage ends at last blank line before the question, OR
 * the question sentence starts with "Q." / "Question:" / ends the paragraph.
 */
function splitPassage(text = "") {
  // If explicit passage field exists on question object, handled upstream
  const parts = text.split(/\n{2,}/);
  if (parts.length >= 2) {
    const question = parts[parts.length - 1];
    const passage  = parts.slice(0, -1).join("\n\n");
    return { passage, question };
  }
  // Try splitting on a line that starts with Q. or "Question"
  const qMatch = text.match(/^(Q\.|Question:?\s)/im);
  if (qMatch) {
    const idx = text.indexOf(qMatch[0]);
    return { passage: text.slice(0, idx).trim(), question: text.slice(idx).trim() };
  }
  return { passage: "", question: text };
}

/**
 * Parse match-the-following columns from question text.
 * Looks for patterns like:
 *   A. item    i.  item
 *   B. item    ii. item
 * or explicit JSON fields: columns: { left: [...], right: [...] }
 */
function parseMatchColumns(question) {
  // Prefer structured JSON fields
  if (question.columns) {
    const { left = [], right = [] } = question.columns;
    return { leftLabel: "List I", rightLabel: "List II", left, right };
  }
  if (question.left_column && question.right_column) {
    return {
      leftLabel:  question.left_label  || "List I",
      rightLabel: question.right_label || "List II",
      left:  question.left_column,
      right: question.right_column,
    };
  }

  // Heuristic: parse lines with pattern "A. ... i. ..." or tab/spacing separated
  const text  = question.question || "";
  const lines = text.split("\n").map(s => s.trim()).filter(Boolean);

  const leftItems  = [];
  const rightItems = [];

  // Patterns for left column: A., B., C., D., (A), (B)
  const leftRe  = /^[\(]?([A-Da-d])[\)\.]\s+(.+)/;
  // Patterns for right column: i., ii., iii., iv., (i), (ii), 1., 2.
  const rightRe = /^[\(]?(i{1,3}v?|iv|[1-4])[\)\.]\s+(.+)/i;

  // Try to find a header line "Column I  Column II" or "List I  List II"
  let leftLabel  = "List I";
  let rightLabel = "List II";
  const headerRe = /(column|list)\s*[–-]?\s*(i|1)\s+(column|list)\s*[–-]?\s*(ii|2)/i;

  for (const line of lines) {
    if (headerRe.test(line)) {
      const m = line.match(/(column|list)\s*[–-]?\s*(i|1)/i);
      leftLabel  = m ? line.slice(0, line.search(/\s{2,}|\t/)).trim() : "List I";
      rightLabel = line.slice(line.search(/\s{2,}|\t/)).trim() || "List II";
      continue;
    }
    const lm = line.match(leftRe);
    const rm = line.match(rightRe);
    if (lm) leftItems.push({ key: lm[1].toUpperCase(), value: lm[2].trim() });
    if (rm) rightItems.push({ key: toRoman(rightItems.length + 1), value: rm[2].trim() });
  }

  // Fallback: if we couldn't parse, return null so we fall back to standard
  if (leftItems.length === 0) return null;

  return { leftLabel, rightLabel, left: leftItems, right: rightItems };
}

function toRoman(n) {
  const map = [["iv",4],["iii",3],["ii",2],["i",1]];
  for (const [r, v] of map) if (n === v) return r;
  return String(n);
}

/**
 * Parse statement questions like:
 *   Statement I: ...
 *   Statement II: ...
 * or
 *   Assertion (A): ...
 *   Reason (R): ...
 */
function parseStatements(text = "") {
  const stmtRe = /(?:Statement|Assertion|Reason|S)\s*[–-]?\s*([IiAaRr12]+)[:\.\)]\s*([^\n]+)/gi;
  const stmts  = [];
  let m;
  while ((m = stmtRe.exec(text)) !== null) {
    stmts.push({ label: m[1].toUpperCase(), text: m[2].trim() });
  }
  // Get the actual question (the part after the statements)
  const lastIdx = text.lastIndexOf("\n\n");
  const tail    = lastIdx > -1 ? text.slice(lastIdx).trim() : "";
  return { statements: stmts, question: tail || "Which of the following is correct?" };
}

/**
 * Render inline code (backtick) and code blocks (triple backtick).
 * Returns an array of React-renderable segments.
 */
function renderRichText(text = "") {
  if (!text) return null;

  // Split on triple-backtick code blocks first
  const blockParts = text.split(/(```[\s\S]*?```)/g);
  return blockParts.map((part, i) => {
    if (part.startsWith("```")) {
      const code = part.replace(/^```\w*\n?/, "").replace(/```$/, "");
      return <pre key={i} className={styles.codeBlock}><code>{code}</code></pre>;
    }

    // Within non-code parts, handle inline backticks
    const inlineParts = part.split(/(`[^`]+`)/g);
    return (
      <span key={i}>
        {inlineParts.map((seg, j) => {
          if (seg.startsWith("`") && seg.endsWith("`")) {
            return <code key={j} className={styles.inlineCode}>{seg.slice(1,-1)}</code>;
          }
          // Preserve newlines as <br>
          return seg.split("\n").map((line, k, arr) => (
            <span key={k}>{line}{k < arr.length - 1 ? <br /> : null}</span>
          ));
        })}
      </span>
    );
  });
}

// ── Sub-renderers ─────────────────────────────────────────────────────────────

function StandardQuestion({ question }) {
  return (
    <div className={styles.questionText}>
      {renderRichText(question.question)}
    </div>
  );
}

function PassageQuestion({ question }) {
  const src  = question.passage || question.paragraph || question.question;
  const { passage, question: qText } = question.passage
    ? { passage: question.passage, question: question.question }
    : splitPassage(src);

  return (
    <div>
      {passage && (
        <div className={styles.passageBox}>
          <div className={styles.passageLabel}>📄 Passage</div>
          {question.passage_title && (
            <div className={styles.passageTitle}>{question.passage_title}</div>
          )}
          <div className={styles.passageText}>{renderRichText(passage)}</div>
        </div>
      )}
      <div className={styles.questionText}>{renderRichText(qText)}</div>
    </div>
  );
}

function MatchQuestion({ question }) {
  const parsed = parseMatchColumns(question);

  if (!parsed) {
    // Couldn't parse columns — fall back to standard rendering
    return <StandardQuestion question={question} />;
  }

  const { leftLabel, rightLabel, left, right } = parsed;

  return (
    <div>
      <div className={styles.questionText}>
        {renderRichText(
          // Strip the column data lines from the question text; show preamble only
          (question.question || "").split("\n").slice(0, 2).join(" ")
        )}
      </div>
      <div className={styles.matchTable}>
        <div className={styles.matchColumn}>
          <div className={styles.matchColumnHeader}>{leftLabel}</div>
          {left.map((item, i) => (
            <div key={i} className={styles.matchRow}>
              <span className={styles.matchKey}>{item.key}.</span>
              <span className={styles.matchValue}>{item.value}</span>
            </div>
          ))}
        </div>
        <div className={styles.matchDivider} />
        <div className={styles.matchColumn}>
          <div className={styles.matchColumnHeader}>{rightLabel}</div>
          {right.map((item, i) => (
            <div key={i} className={styles.matchRow}>
              <span className={styles.matchKey}>{item.key}.</span>
              <span className={styles.matchValue}>{item.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatementQuestion({ question }) {
  const { statements, question: qText } = parseStatements(question.question || "");

  return (
    <div>
      {statements.length > 0 ? (
        <div className={styles.statementBox}>
          {statements.map((s, i) => (
            <div key={i} className={styles.statementRow}>
              <span className={styles.statementLabel}>Statement {s.label}:</span>
              <span className={styles.statementText}>{s.text}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className={styles.questionText}>{renderRichText(question.question)}</div>
      )}
      {qText && statements.length > 0 && (
        <div className={styles.statementQuestion}>{renderRichText(qText)}</div>
      )}
    </div>
  );
}

function CodeQuestion({ question }) {
  return (
    <div className={styles.questionText}>
      {renderRichText(question.question)}
    </div>
  );
}

function NATQuestion({ question }) {
  return (
    <div>
      <div className={styles.natBadge}>Numerical Answer Type</div>
      <div className={styles.questionText}>{renderRichText(question.question)}</div>
    </div>
  );
}

// ── Options renderer ──────────────────────────────────────────────────────────

/**
 * Renders the A/B/C/D options. Shared across all question types.
 * For match-type questions the options are "A→i, B→ii" sequences —
 * we detect this and format them as a mini-table.
 */
function OptionsBlock({ options, selectedOption, onSelect, showAnswer, correctOption }) {
  const isMatchOption = Object.values(options || {}).some(v =>
    /[A-D]\s*[–→-]\s*(i{1,3}v?|iv)/i.test(v)
  );

  return (
    <div className={styles.optionsList}>
      {Object.entries(options || {}).map(([key, val]) => {
        const isSelected = selectedOption === key;
        const isCorrect  = showAnswer && correctOption === key;
        const isWrong    = showAnswer && isSelected && correctOption !== key;

        return (
          <button
            key={key}
            className={[
              styles.option,
              isSelected && !showAnswer ? styles.optionSelected : "",
              isCorrect               ? styles.optionCorrect  : "",
              isWrong                 ? styles.optionWrong    : "",
            ].filter(Boolean).join(" ")}
            onClick={() => onSelect && onSelect(key)}
            disabled={showAnswer}
          >
            <span className={[
              styles.optKey,
              isSelected && !showAnswer ? styles.optKeySelected : "",
              isCorrect                 ? styles.optKeyCorrect  : "",
              isWrong                   ? styles.optKeyWrong    : "",
            ].filter(Boolean).join(" ")}>
              {key}
            </span>
            <span className={styles.optVal}>
              {isMatchOption
                ? <MatchOptionValue value={val} />
                : renderRichText(val)
              }
            </span>
            {showAnswer && isCorrect  && <span className={styles.optTag} data-tag="correct">✓ Correct</span>}
            {showAnswer && isWrong    && <span className={styles.optTag} data-tag="wrong">✗ Your answer</span>}
          </button>
        );
      })}
    </div>
  );
}

/** Renders "A → i, B → ii, C → iii, D → iv" as a small grid */
function MatchOptionValue({ value }) {
  // Split on comma then parse each "X → y" pair
  const pairs = value.split(/,\s*/).map(p => {
    const m = p.match(/([A-D])\s*[–→\-]+\s*(.+)/i);
    return m ? { left: m[1].toUpperCase(), right: m[2].trim() } : { left: "", right: p };
  });

  if (pairs.every(p => p.left)) {
    return (
      <span className={styles.matchOptionGrid}>
        {pairs.map((p, i) => (
          <span key={i} className={styles.matchOptionPair}>
            <span className={styles.matchOptLeft}>{p.left}</span>
            <span className={styles.matchOptArrow}>→</span>
            <span className={styles.matchOptRight}>{p.right}</span>
          </span>
        ))}
      </span>
    );
  }
  return <span>{value}</span>;
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * @param {object}   question       — Full question object from JSON
 * @param {string}   selectedOption — Currently selected key ("A"/"B"/"C"/"D")
 * @param {function} onSelect       — Called with key when user picks an option
 * @param {boolean}  showAnswer     — If true, reveal correct/wrong styling (results view)
 * @param {string}   correctOption  — The correct key (only used when showAnswer=true)
 */
export default function QuestionRenderer({
  question,
  selectedOption,
  onSelect,
  showAnswer = false,
  correctOption,
}) {
  if (!question) return null;

  const format = detectFormat(question);

  const QuestionBody = {
    standard:  StandardQuestion,
    passage:   PassageQuestion,
    match:     MatchQuestion,
    statement: StatementQuestion,
    code:      CodeQuestion,
    nat:       NATQuestion,
  }[format] || StandardQuestion;

  return (
    <div className={styles.wrapper}>
      {/* Format badge — subtle indicator */}
      {format !== "standard" && (
        <div className={styles.formatBadge} data-format={format}>
          {FORMAT_LABELS[format]}
        </div>
      )}

      {/* Question body */}
      <div className={styles.questionBody}>
        <QuestionBody question={question} />
      </div>

      {/* Options */}
      <OptionsBlock
        options={question.options}
        selectedOption={selectedOption}
        onSelect={onSelect}
        showAnswer={showAnswer}
        correctOption={correctOption}
      />
    </div>
  );
}

const FORMAT_LABELS = {
  passage:   "📄 Passage-based",
  match:     "🔗 Match the Following",
  statement: "📋 Statement-based",
  code:      "💻 Code / Technical",
  nat:       "🔢 Numerical Answer",
};