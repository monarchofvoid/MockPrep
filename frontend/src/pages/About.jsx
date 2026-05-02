import { Link } from "react-router-dom";
import StaticLayout from "../components/StaticLayout";
import styles from "../styles/StaticPage.module.css";

export default function About() {
  return (
    <StaticLayout>
      {/* ── Header ── */}
      <div className={styles.header}>
        <span className={styles.kicker}>About VYAS</span>
        <h1 className={styles.pageTitle}>Built for serious aspirants</h1>
        <p className={styles.pageLead}>
          VYAS is a disciplined mock practice platform for competitive exam
          preparation — built on the belief that honest feedback beats
          encouraging noise.
        </p>
      </div>

      {/* ── Stats ── */}
      <div className={styles.statRow}>
        <div className={styles.statCard}>
          <span className={styles.statNum}>10+</span>
          <span className={styles.statLabel}>Papers</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statNum}>700+</span>
          <span className={styles.statLabel}>Questions</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statNum}>5</span>
          <span className={styles.statLabel}>Exam tracks</span>
        </div>
      </div>

      <hr className={styles.divider} />

      {/* ── Sections ── */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>The problem we're solving</h2>
        <p>
          Most practice tools hand you a score and move on. You finish a mock
          test, see 68%, and have no clear sense of whether that means you
          misread questions, ran out of time, or simply don't know the topic.
        </p>
        <p>
          VYAS treats every attempt as structured data. Each submission
          produces a breakdown by topic accuracy, time distribution,
          per-question behaviour, and cross-attempt trends — so progress
          becomes visible and your next session has a clear direction.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>How it works</h2>
        <p>
          Select a paper from the available question bank, sit the mock under
          real timed conditions with a structured navigation interface, and
          submit. VYAS evaluates your responses instantly and returns a
          full results dashboard including:
        </p>
        <ul>
          <li>Score, accuracy, and attempt rate</li>
          <li>Topic-level performance breakdown</li>
          <li>Question-by-question review with explanations</li>
          <li>Time spent per question and visit patterns</li>
          <li>Improvement signals across multiple attempts</li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Current coverage</h2>
        <ul>
          <li>CUET — Economics, English, General Test</li>
          <li>GATE — DBMS, Operating Systems</li>
          <li>More subjects and exams added regularly</li>
        </ul>
        <p>
          Questions are sourced from publicly available past papers published
          by their respective conducting bodies (NTA, IIT, etc.).
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Our philosophy</h2>
        <p>
          We optimise for clarity over comfort. A platform that tells you
          exactly where you went wrong is more useful than one that
          congratulates you on a mediocre score. VYAS is designed to give
          you the kind of honest, structured feedback that a good tutor
          would — without the tutor.
        </p>
      </div>

      <hr className={styles.divider} />

      <div className={styles.infoCard}>
        <p>
          Have a question, spotted an error in a question, or want to
          suggest a subject?{" "}
          <Link to="/contact">Get in touch</Link> — we read and respond
          to everything.
        </p>
      </div>
    </StaticLayout>
  );
}
