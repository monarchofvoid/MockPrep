import { useEffect, useState } from "react";
import { getMocks } from "../api/client";
import styles from "../styles/Home.module.css";

const ICONS = {
  GATE: "⚙️",
  CAT: "📊",
  JEE: "🔬",
  default: "📝",
};

export default function Home({ userId, onSelectPaper }) {
  const [mocks, setMocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getMocks()
      .then(setMocks)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className={styles.center}>
        <div className={styles.spinner} />
        <p>Loading papers…</p>
      </div>
    );

  if (error)
    return (
      <div className={styles.center}>
        <p className={styles.error}>⚠ {error}</p>
        <p>Make sure the backend is running on port 8000.</p>
      </div>
    );

  const grouped = mocks.reduce((acc, m) => {
    if (!acc[m.exam]) acc[m.exam] = [];
    acc[m.exam].push(m);
    return acc;
  }, {});

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.logo}>MP</div>
        <h1>MockPrep</h1>
        <p>Real exam environment · Deep analytics · Review every mistake</p>
      </div>

      {Object.entries(grouped).map(([exam, papers]) => (
        <section key={exam} className={styles.section}>
          <h2 className={styles.examLabel}>
            <span>{ICONS[exam] || ICONS.default}</span> {exam}
          </h2>
          <div className={styles.grid}>
            {papers.map((p) => (
              <button
                key={p.id}
                className={styles.card}
                onClick={() => onSelectPaper(p)}
              >
                <div className={styles.cardExam}>{p.exam}</div>
                <div className={styles.cardSubject}>{p.subject}</div>
                <div className={styles.cardYear}>{p.year}</div>
                <div className={styles.pills}>
                  <span className={styles.pill}>⏱ {p.duration_minutes} min</span>
                  <span className={styles.pill}>📋 {p.question_count} Qs</span>
                  <span className={styles.pill}>🎯 {p.total_marks} marks</span>
                </div>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
