'use client';

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

import React from 'react';
import styles from '@/styles/QuestionRenderer.module.css';

// ── Types ─────────────────────────────────────────────────────────────────────

interface QuestionObj {
  question: string;
  options?: Record<string, string>;
  type?: string;
  passage?: string;
  passage_title?: string;
  paragraph?: string;
  columns?: { left: ColumnItem[]; right: ColumnItem[] };
  left_column?: ColumnItem[];
  right_column?: ColumnItem[];
  left_label?: string;
  right_label?: string;
}

interface ColumnItem {
  key: string;
  value: string;
}

interface QuestionRendererProps {
  question: QuestionObj;
  selectedOption?: string | null;
  onSelect?: (key: string) => void;
  showAnswer?: boolean;
  correctOption?: string;
}

// ── Type detection ────────────────────────────────────────────────────────────

function detectFormat(question: QuestionObj): string {
  const type = (question.type || '').toLowerCase().trim();
  const text  = (question.question || '').toLowerCase();

  if (type === 'passage' || type === 'comprehension')        return 'passage';
  if (type === 'match' || type === 'match_the_following')    return 'match';
  if (type === 'statement' || type === 'assertion_reason')   return 'statement';
  if (type === 'nat' || type === 'numerical')                return 'nat';
  if (type === 'code' || type === 'program')                 return 'code';

  if (question.passage || question.paragraph)                return 'passage';
  if (question.columns || question.left_column)              return 'match';

  if (/match\s+(the\s+)?following|column\s*[–-]?\s*[12I]|list\s*[–-]?\s*[12I]/i.test(text))
    return 'match';
  if (/^(passage|read\s+the\s+following|consider\s+the\s+following\s+passage)/i.test(text))
    return 'passage';
  if (/statement\s*[–-]?\s*(i|ii|1|2)|assertion.*reason/i.test(text))
    return 'statement';
  if (hasCodeBlock(question.question))
    return 'code';

  return 'standard';
}

function hasCodeBlock(text = ''): boolean {
  return /```[\s\S]*```/.test(text) ||
         /`[^`]+`/.test(text) ||
         /^\s{4,}\S/m.test(text) ||
         /<code>|<pre>/i.test(text);
}

// ── Text processors ───────────────────────────────────────────────────────────

function splitPassage(text = ''): { passage: string; question: string } {
  const parts = text.split(/\n{2,}/);
  if (parts.length >= 2) {
    return {
      passage:  parts.slice(0, -1).join('\n\n'),
      question: parts[parts.length - 1],
    };
  }
  const qMatch = text.match(/^(Q\.|Question:?\s)/im);
  if (qMatch) {
    const idx = text.indexOf(qMatch[0]);
    return { passage: text.slice(0, idx).trim(), question: text.slice(idx).trim() };
  }
  return { passage: '', question: text };
}

function toRoman(n: number): string {
  const map: [string, number][] = [['iv',4],['iii',3],['ii',2],['i',1]];
  for (const [r, v] of map) if (n === v) return r;
  return String(n);
}

function parseMatchColumns(question: QuestionObj) {
  if (question.columns) {
    const { left = [], right = [] } = question.columns;
    return { leftLabel: 'List I', rightLabel: 'List II', left, right };
  }
  if (question.left_column && question.right_column) {
    return {
      leftLabel:  question.left_label  || 'List I',
      rightLabel: question.right_label || 'List II',
      left:  question.left_column,
      right: question.right_column,
    };
  }

  const text  = question.question || '';
  const lines = text.split('\n').map(s => s.trim()).filter(Boolean);
  const leftItems: ColumnItem[]  = [];
  const rightItems: ColumnItem[] = [];
  const leftRe  = /^[\(]?([A-Da-d])[\)\.]]\s+(.+)/;
  const rightRe = /^[\(]?(i{1,3}v?|iv|[1-4])[\)\.]]\s+(.+)/i;
  const leftLabel  = 'List I';
  const rightLabel = 'List II';

  for (const line of lines) {
    const lm = line.match(leftRe);
    const rm = line.match(rightRe);
    if (lm) leftItems.push({ key: lm[1].toUpperCase(), value: lm[2].trim() });
    if (rm) rightItems.push({ key: toRoman(rightItems.length + 1), value: rm[2].trim() });
  }

  if (leftItems.length === 0) return null;
  return { leftLabel, rightLabel, left: leftItems, right: rightItems };
}

function parseStatements(text = '') {
  const stmtRe = /(?:Statement|Assertion|Reason|S)\s*[–-]?\s*([IiAaRr12]+)[:\.\)]\s*([^\n]+)/gi;
  const stmts: { label: string; text: string }[] = [];
  let m;
  while ((m = stmtRe.exec(text)) !== null) {
    stmts.push({ label: m[1].toUpperCase(), text: m[2].trim() });
  }
  const lastIdx = text.lastIndexOf('\n\n');
  const tail    = lastIdx > -1 ? text.slice(lastIdx).trim() : '';
  return { statements: stmts, question: tail || 'Which of the following is correct?' };
}

function renderRichText(text = ''): React.ReactNode {
  if (!text) return null;
  const blockParts = text.split(/(```[\s\S]*?```)/g);
  return blockParts.map((part, i) => {
    if (part.startsWith('```')) {
      const code = part.replace(/^```\w*\n?/, '').replace(/```$/, '');
      return <pre key={i} className={styles.codeBlock}><code>{code}</code></pre>;
    }
    const inlineParts = part.split(/(`[^`]+`)/g);
    return (
      <span key={i}>
        {inlineParts.map((seg, j) => {
          if (seg.startsWith('`') && seg.endsWith('`')) {
            return <code key={j} className={styles.inlineCode}>{seg.slice(1,-1)}</code>;
          }
          return seg.split('\n').map((line, k, arr) => (
            <span key={k}>{line}{k < arr.length - 1 ? <br /> : null}</span>
          ));
        })}
      </span>
    );
  });
}

// ── Sub-renderers ─────────────────────────────────────────────────────────────

function StandardQuestion({ question }: { question: QuestionObj }) {
  return <div className={styles.questionText}>{renderRichText(question.question)}</div>;
}

function PassageQuestion({ question }: { question: QuestionObj }) {
  const src = question.passage || question.paragraph || question.question;
  const { passage, question: qText } = question.passage
    ? { passage: question.passage, question: question.question }
    : splitPassage(src);

  return (
    <div>
      {passage && (
        <div className={styles.passageBox}>
          <div className={styles.passageLabel}>Passage</div>
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

function MatchQuestion({ question }: { question: QuestionObj }) {
  const parsed = parseMatchColumns(question);
  if (!parsed) return <StandardQuestion question={question} />;

  const { leftLabel, rightLabel, left, right } = parsed;
  return (
    <div>
      <div className={styles.questionText}>
        {renderRichText(
          (question.question || '').split('\n').slice(0, 2).join(' ')
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

function StatementQuestion({ question }: { question: QuestionObj }) {
  const { statements, question: qText } = parseStatements(question.question || '');
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

function NATQuestion({ question }: { question: QuestionObj }) {
  return (
    <div>
      <div className={styles.natBadge}>Numerical Answer Type</div>
      <div className={styles.questionText}>{renderRichText(question.question)}</div>
    </div>
  );
}

// ── Match-option value formatter ──────────────────────────────────────────────

function MatchOptionValue({ value }: { value: string }) {
  const pairs = value.split(/,\s*/).map(p => {
    const m = p.match(/([A-D])\s*[–→\-]+\s*(.+)/i);
    return m ? { left: m[1].toUpperCase(), right: m[2].trim() } : { left: '', right: p };
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

// ── Options block ─────────────────────────────────────────────────────────────

function OptionsBlock({
  options,
  selectedOption,
  onSelect,
  showAnswer,
  correctOption,
}: {
  options?: Record<string, string>;
  selectedOption?: string | null;
  onSelect?: (key: string) => void;
  showAnswer?: boolean;
  correctOption?: string;
}) {
  const isMatchOption = Object.values(options || {}).some(v =>
    /[A-D]\s*[–→-]\s*(i{1,3}v?|iv)/i.test(v)
  );

  return (
    <div className={styles.optionsList}>
      {Object.entries(options || {}).map(([key, val]) => {
        const isSelected = selectedOption === key;
        const isCorrect  = !!(showAnswer && correctOption === key);
        const isWrong    = !!(showAnswer && isSelected && correctOption !== key);

        return (
          <button
            key={key}
            className={[
              styles.option,
              isSelected && !showAnswer ? styles.optionSelected : '',
              isCorrect               ? styles.optionCorrect  : '',
              isWrong                 ? styles.optionWrong    : '',
            ].filter(Boolean).join(' ')}
            onClick={() => onSelect && onSelect(key)}
            disabled={showAnswer}
          >
            <span className={[
              styles.optKey,
              isSelected && !showAnswer ? styles.optKeySelected : '',
              isCorrect                 ? styles.optKeyCorrect  : '',
              isWrong                   ? styles.optKeyWrong    : '',
            ].filter(Boolean).join(' ')}>
              {key}
            </span>
            <span className={styles.optVal}>
              {isMatchOption ? <MatchOptionValue value={val} /> : renderRichText(val)}
            </span>
            {showAnswer && isCorrect && <span className={styles.optTag} data-tag="correct">✓ Correct</span>}
            {showAnswer && isWrong   && <span className={styles.optTag} data-tag="wrong">✗ Your answer</span>}
          </button>
        );
      })}
    </div>
  );
}

// ── Format labels ─────────────────────────────────────────────────────────────

const FORMAT_LABELS: Record<string, string> = {
  passage:   'Passage-based',
  match:     'Match the Following',
  statement: 'Statement-based',
  code:      'Code / Technical',
  nat:       'Numerical Answer',
};

// ── Main export ───────────────────────────────────────────────────────────────

export default function QuestionRenderer({
  question,
  selectedOption,
  onSelect,
  showAnswer = false,
  correctOption,
}: QuestionRendererProps) {
  if (!question) return null;

  const format = detectFormat(question);

  const QuestionBody = {
    standard:  StandardQuestion,
    passage:   PassageQuestion,
    match:     MatchQuestion,
    statement: StatementQuestion,
    code:      StandardQuestion,  // code questions use rich-text rendering
    nat:       NATQuestion,
  }[format] || StandardQuestion;

  return (
    <div className={styles.wrapper}>
      {format !== 'standard' && (
        <div className={styles.formatBadge} data-format={format}>
          {FORMAT_LABELS[format]}
        </div>
      )}
      <div className={styles.questionBody}>
        <QuestionBody question={question} />
      </div>
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