import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { login as apiLogin, signup as apiSignup } from "../api/client";
import styles from "../styles/Landing.module.css";

const FEATURES = [
  {
    icon: "⚡",
    title: "Real Exam Conditions",
    desc: "Timed sessions, question palette, and mark-for-review — exactly like the actual exam interface.",
  },
  {
    icon: "📊",
    title: "Deep Performance Analytics",
    desc: "Topic-wise accuracy, time distribution per question, and cross-attempt progress trends.",
  },
  {
    icon: "🔍",
    title: "Full Solution Review",
    desc: "Every question explained — see your selected answer vs. the correct one with full rationale.",
  },
  {
    icon: "🎯",
    title: "Targeted Improvement",
    desc: "VYAS surfaces your weakest topics so you know exactly where to focus next.",
  },
];

const EXAMS = ["GATE", "CUET", "CAT", "JEE", "UPSC"];

export default function LandingPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();

  const [modalOpen, setModalOpen]   = useState(false);
  const [tab, setTab]               = useState("login"); // "login" | "signup"
  const [formData, setFormData]     = useState({ name: "", email: "", password: "" });
  const [error, setError]           = useState("");
  const [loading, setLoading]       = useState(false);

  // If already authenticated, send to dashboard
  useEffect(() => {
    if (user) navigate("/dashboard", { replace: true });
  }, [user, navigate]);

  const openModal = (defaultTab = "login") => {
    setTab(defaultTab);
    setError("");
    setFormData({ name: "", email: "", password: "" });
    setModalOpen(true);
  };

  const closeModal = () => {
    if (loading) return;
    setModalOpen(false);
    setError("");
  };

  const handleChange = (e) =>
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      let payload;
      if (tab === "login") {
        payload = await apiLogin(formData.email, formData.password);
      } else {
        if (!formData.name.trim()) {
          setError("Please enter your full name.");
          setLoading(false);
          return;
        }
        if (formData.password.length < 6) {
          setError("Password must be at least 6 characters.");
          setLoading(false);
          return;
        }
        payload = await apiSignup(formData.name, formData.email, formData.password);
      }
      login(payload);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      {/* ── Navbar ─────────────────────────────────────────────── */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.brand}>
            <span className={styles.logo}>VY</span>
            <span className={styles.brandName}>VYAS</span>
          </div>
          <div className={styles.headerActions}>
            <button className={styles.loginLink} onClick={() => openModal("login")}>
              Sign in
            </button>
            <button className={styles.signupBtn} onClick={() => openModal("signup")}>
              Get started
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero ───────────────────────────────────────────────── */}
      <section className={styles.hero}>
        <div className={styles.heroInner}>
          <div className={styles.examPills}>
            {EXAMS.map((e) => (
              <span key={e} className={styles.examPill}>{e}</span>
            ))}
          </div>
          <h1 className={styles.heroTitle}>
            Virtual Yield<br />
            <span className={styles.heroAccent}>Assessment System</span>
          </h1>
          <p className={styles.heroSub}>
            Practice competitive exam papers in a real exam environment.
            Track your progress, identify weak areas, and improve with every attempt.
          </p>
          <div className={styles.heroCtas}>
            <button className={styles.primaryCta} onClick={() => openModal("signup")}>
              Start practising free →
            </button>
            <button className={styles.secondaryCta} onClick={() => openModal("login")}>
              Sign in
            </button>
          </div>
        </div>

        {/* Hero illustration — abstract score card */}
        <div className={styles.heroCard} aria-hidden="true">
          <div className={styles.hcHeader}>
            <span className={styles.hcDot} style={{ background: "#ef4444" }} />
            <span className={styles.hcDot} style={{ background: "#f59e0b" }} />
            <span className={styles.hcDot} style={{ background: "#10b981" }} />
            <span className={styles.hcTitle}>GATE · DBMS PYQ 2021</span>
          </div>
          <div className={styles.hcBody}>
            <div className={styles.hcScore}>
              <svg width="90" height="90" viewBox="0 0 90 90">
                <circle cx="45" cy="45" r="36" fill="none" stroke="#e5e7eb" strokeWidth="8" />
                <circle
                  cx="45" cy="45" r="36" fill="none" stroke="#2563eb" strokeWidth="8"
                  strokeDasharray="226" strokeDashoffset="68"
                  strokeLinecap="round" transform="rotate(-90 45 45)"
                />
                <text x="45" y="49" textAnchor="middle" fontSize="16" fontWeight="700" fill="#0f1e3d">70%</text>
              </svg>
            </div>
            <div className={styles.hcStats}>
              <div className={styles.hcStat}><span className={styles.hcVal} style={{ color: "#059669" }}>7</span><span className={styles.hcLbl}>Correct</span></div>
              <div className={styles.hcStat}><span className={styles.hcVal} style={{ color: "#dc2626" }}>2</span><span className={styles.hcLbl}>Wrong</span></div>
              <div className={styles.hcStat}><span className={styles.hcVal} style={{ color: "#6b7280" }}>1</span><span className={styles.hcLbl}>Skipped</span></div>
            </div>
            <div className={styles.hcTopics}>
              {[
                { topic: "SQL Queries", pct: 90 },
                { topic: "Normalisation", pct: 60 },
                { topic: "Transactions", pct: 50 },
              ].map(({ topic, pct }) => (
                <div key={topic} className={styles.hcTopicRow}>
                  <span className={styles.hcTopicName}>{topic}</span>
                  <div className={styles.hcBar}>
                    <div className={styles.hcBarFill} style={{ width: `${pct}%` }} />
                  </div>
                  <span className={styles.hcTopicPct}>{pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ───────────────────────────────────────────── */}
      <section className={styles.features}>
        <div className={styles.featuresInner}>
          <h2 className={styles.sectionTitle}>Everything you need to perform better</h2>
          <div className={styles.featureGrid}>
            {FEATURES.map((f) => (
              <div key={f.title} className={styles.featureCard}>
                <div className={styles.featureIcon}>{f.icon}</div>
                <h3 className={styles.featureTitle}>{f.title}</h3>
                <p className={styles.featureDesc}>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Banner ─────────────────────────────────────────── */}
      <section className={styles.ctaBanner}>
        <div className={styles.ctaInner}>
          <h2 className={styles.ctaTitle}>Ready to start practising?</h2>
          <p className={styles.ctaSub}>Free. No credit card. Just real exam practice.</p>
          <button className={styles.ctaBtn} onClick={() => openModal("signup")}>
            Create your account →
          </button>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────── */}
      <footer className={styles.footer}>
        <span className={styles.footerLogo}>VY</span>
        <span className={styles.footerText}>VYAS — Virtual Yield Assessment System</span>
      </footer>

      {/* ── Auth Modal ─────────────────────────────────────────── */}
      {modalOpen && (
        <div className={styles.overlay} onClick={closeModal}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            {/* Modal header */}
            <div className={styles.modalHeader}>
              <div className={styles.modalLogo}>VY</div>
              <button
                className={styles.modalClose}
                onClick={closeModal}
                aria-label="Close"
                disabled={loading}
              >
                ✕
              </button>
            </div>

            {/* Tab switcher */}
            <div className={styles.tabs}>
              <button
                className={`${styles.tabBtn} ${tab === "login" ? styles.activeTab : ""}`}
                onClick={() => { setTab("login"); setError(""); }}
                disabled={loading}
              >
                Sign in
              </button>
              <button
                className={`${styles.tabBtn} ${tab === "signup" ? styles.activeTab : ""}`}
                onClick={() => { setTab("signup"); setError(""); }}
                disabled={loading}
              >
                Create account
              </button>
            </div>

            {/* Form */}
            <form className={styles.form} onSubmit={handleSubmit} noValidate>
              {tab === "signup" && (
                <div className={styles.field}>
                  <label className={styles.label} htmlFor="name">Full name</label>
                  <input
                    id="name"
                    name="name"
                    type="text"
                    placeholder="Arjun Sharma"
                    className={styles.input}
                    value={formData.name}
                    onChange={handleChange}
                    required
                    autoComplete="name"
                    disabled={loading}
                  />
                </div>
              )}

              <div className={styles.field}>
                <label className={styles.label} htmlFor="email">Email</label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="you@example.com"
                  className={styles.input}
                  value={formData.email}
                  onChange={handleChange}
                  required
                  autoComplete="email"
                  disabled={loading}
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label} htmlFor="password">Password</label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  placeholder={tab === "signup" ? "Min. 6 characters" : "Your password"}
                  className={styles.input}
                  value={formData.password}
                  onChange={handleChange}
                  required
                  autoComplete={tab === "login" ? "current-password" : "new-password"}
                  disabled={loading}
                />
              </div>

              {error && <p className={styles.formError}>{error}</p>}

              <button
                type="submit"
                className={styles.submitBtn}
                disabled={loading}
              >
                {loading
                  ? "Please wait…"
                  : tab === "login"
                  ? "Sign in →"
                  : "Create account →"}
              </button>
            </form>

            <p className={styles.switchText}>
              {tab === "login" ? "Don't have an account? " : "Already have an account? "}
              <button
                className={styles.switchLink}
                onClick={() => { setTab(tab === "login" ? "signup" : "login"); setError(""); }}
                disabled={loading}
              >
                {tab === "login" ? "Sign up" : "Sign in"}
              </button>
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
