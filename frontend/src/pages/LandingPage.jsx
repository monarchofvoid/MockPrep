import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { login as apiLogin, signup as apiSignup } from "../api/client";
import VyasLogo from "../components/VyasLogo";
import styles from "../styles/Landing.module.css";

/* ─── Data ─────────────────────────────────────────────────────────────────── */

const FEATURES = [
  {
    kicker: "Simulate",
    title: "Real exam conditions",
    desc: "Timed papers, structured navigation, review states, and submission discipline built into every attempt.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
  },
  {
    kicker: "Diagnose",
    title: "Performance intelligence",
    desc: "Score, accuracy, pace, and topic mastery are tracked across attempts so progress becomes visible.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6"  y1="20" x2="6"  y2="14" />
        <line x1="2"  y1="20" x2="22" y2="20" />
      </svg>
    ),
  },
  {
    kicker: "Review",
    title: "Clear solution analysis",
    desc: "Every result opens into question-level review with correct answers, explanations, and behaviour signals.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
        <line x1="11" y1="8"  x2="11" y2="14" />
        <line x1="8"  y1="11" x2="14" y2="11" />
      </svg>
    ),
  },
  {
    kicker: "Ascend",
    title: "Focused improvement",
    desc: "Weak areas surface naturally, helping learners spend their next session where it matters most.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
        <polyline points="16 7 22 7 22 13" />
      </svg>
    ),
  },
];

const EXAMS = ["CUET", "GATE", "CAT", "JEE", "UPSC"];

const STATS = [
  { value: 10,  suffix: "+",  label: "Mock Papers",    mono: true },
  { value: 700, suffix: "+",  label: "Questions",      mono: true },
  { value: 100, suffix: "%",  label: "Free to start",  mono: true },
];

const HOW_IT_WORKS = [
  {
    step: "01",
    title: "Choose your exam",
    desc: "Browse mock papers across UPSC, GATE, CAT, JEE and CUET. Pick your challenge.",
  },
  {
    step: "02",
    title: "Train under pressure",
    desc: "Attempt tests in real exam conditions — timed, structured, and discipline-enforced from question one.",
  },
  {
    step: "03",
    title: "Ascend with insight",
    desc: "Review every answer, study your patterns. VYAS surfaces exactly where to focus next.",
  },
];

const TRUST_ITEMS = ["Free to start", "No credit card", "AI-powered", "Secure & private"];

/* ─── Hooks ─────────────────────────────────────────────────────────────────── */

/** Adds a CSS class when element scrolls into view */
function useScrollReveal(threshold = 0.15) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);

  return [ref, visible];
}

/** Animates a number from 0 → target when `active` becomes true */
function useCountUp(target, duration = 1400, active = false) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!active) return;
    let start = null;
    let raf;
    const step = (ts) => {
      if (!start) start = ts;
      const pct = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - pct, 3);
      setCount(Math.round(eased * target));
      if (pct < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, active]);

  return count;
}

/* ─── Sub-components ────────────────────────────────────────────────────────── */

function StatCounter({ value, suffix, label }) {
  const [ref, visible] = useScrollReveal(0.3);
  const count = useCountUp(value, 1200, visible);
  return (
    <div ref={ref} className={`${styles.statItem} ${visible ? styles.statVisible : ""}`}>
      <span className={styles.statValue}>
        {count}{suffix}
      </span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  );
}

function FeatureCard({ feature, index }) {
  const [ref, visible] = useScrollReveal(0.1);
  return (
    <article
      ref={ref}
      className={`${styles.featureCard} ${visible ? styles.cardVisible : ""}`}
      style={{ "--card-delay": `${index * 80}ms` }}
    >
      <div className={styles.featureIconWrap}>
        {feature.icon}
      </div>
      <span className={styles.featureKicker}>{feature.kicker}</span>
      <h3 className={styles.featureTitle}>{feature.title}</h3>
      <p className={styles.featureDesc}>{feature.desc}</p>
    </article>
  );
}

function StepCard({ step, index }) {
  const [ref, visible] = useScrollReveal(0.15);
  return (
    <div
      ref={ref}
      className={`${styles.step} ${visible ? styles.stepVisible : ""}`}
      style={{ "--step-delay": `${index * 120}ms` }}
    >
      <div className={styles.stepNumber}>{step.step}</div>
      <div className={styles.stepContent}>
        <h3 className={styles.stepTitle}>{step.title}</h3>
        <p className={styles.stepDesc}>{step.desc}</p>
      </div>
      {index < HOW_IT_WORKS.length - 1 && (
        <div className={styles.stepConnector} aria-hidden="true" />
      )}
    </div>
  );
}

/* ─── Main Component ────────────────────────────────────────────────────────── */

export default function LandingPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();

  /* auth modal state ─────────────────────────────────────── */
  const [modalOpen, setModalOpen] = useState(false);
  const [tab, setTab] = useState("login");
  const [formData, setFormData] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  /* cycling exam pill ────────────────────────────────────── */
  const [activeExam, setActiveExam] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setActiveExam((p) => (p + 1) % EXAMS.length), 1800);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (user) navigate("/dashboard", { replace: true });
  }, [user, navigate]);

  /* scroll-reveal refs for hero elements ─────────────────── */
  const [heroRef, heroVisible] = useScrollReveal(0.05);
  const [aiRef, aiVisible] = useScrollReveal(0.1);
  const [ctaRef, ctaVisible] = useScrollReveal(0.1);

  /* modal handlers ───────────────────────────────────────── */
  const openModal = useCallback((defaultTab = "login") => {
    setTab(defaultTab);
    setError("");
    setFormData({ name: "", email: "", password: "" });
    setModalOpen(true);
  }, []);

  const closeModal = useCallback(() => {
    if (loading) return;
    setModalOpen(false);
    setError("");
  }, [loading]);

  const handleChange = (e) =>
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "signup" && !formData.name.trim()) {
        setError("Please enter your full name.");
        setLoading(false);
        return;
      }
      if (tab === "signup" && formData.password.length < 6) {
        setError("Password must be at least 6 characters.");
        setLoading(false);
        return;
      }
      const payload =
        tab === "login"
          ? await apiLogin(formData.email, formData.password)
          : await apiSignup(formData.name.trim(), formData.email, formData.password);
      login(payload);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  /* ── Render ──────────────────────────────────────────────────────────────── */
  return (
    <div className={styles.page}>

      {/* ══ HEADER ══════════════════════════════════════════════════════════ */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.brand}>
            <VyasLogo variant="gold" size={36} />
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

      <main>

        {/* ══ HERO ════════════════════════════════════════════════════════════ */}
        <section className={styles.hero}>
          {/* atmospheric background elements */}
          <div className={styles.heroBgGrid} aria-hidden="true" />
          <div className={styles.heroBgOrb1} aria-hidden="true" />
          <div className={styles.heroBgOrb2} aria-hidden="true" />

          <div ref={heroRef} className={`${styles.heroInner} ${heroVisible ? styles.heroVisible : ""}`}>
            <VyasLogo variant="gold" size={108} animate className={styles.heroLogo} />

            {/* trust chips */}
            <div className={styles.trustRow}>
              {TRUST_ITEMS.map((t) => (
                <span key={t} className={styles.trustChip}>
                  <span className={styles.trustDot} aria-hidden="true" />
                  {t}
                </span>
              ))}
            </div>

            <h1 className={styles.heroTitle}>
              Ascend with<br />
              <span className={styles.heroTitleAccent}>Intelligence</span>
            </h1>

            <p className={styles.heroSub}>
              VYAS brings disciplined mock practice, precise analytics, and elegant review
              workflows into one aspirational learning platform.
            </p>

            {/* exam pills — active one pulsed */}
            <div className={styles.examPills}>
              {EXAMS.map((exam, i) => (
                <span
                  key={exam}
                  className={`${styles.examPill} ${i === activeExam ? styles.examPillActive : ""}`}
                >
                  {exam}
                </span>
              ))}
            </div>

            <div className={styles.heroCtas}>
              <button className={styles.primaryCta} onClick={() => openModal("signup")}>
                Start practising free →
              </button>
              <button className={styles.secondaryCta} onClick={() => openModal("login")}>
                Continue ascent
              </button>
            </div>

            <div className={styles.scrollHint} aria-hidden="true">
              <span className={styles.scrollLine} />
              <span className={styles.scrollText}>scroll to explore</span>
            </div>
          </div>
        </section>

        {/* ══ STATS ═══════════════════════════════════════════════════════════ */}
        <section className={styles.statsSection}>
          <div className={styles.statsInner}>
            {STATS.map((s) => (
              <StatCounter key={s.label} value={s.value} suffix={s.suffix} label={s.label} />
            ))}
          </div>
        </section>

        {/* ══ HOW IT WORKS ════════════════════════════════════════════════════ */}
        <section className={styles.howSection}>
          <div className={styles.howInner}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionKicker}>The journey</span>
              <h2 className={styles.sectionTitle}>Three steps to the top</h2>
              <p className={styles.sectionSub}>
                From choosing your exam to surfacing hidden weaknesses — VYAS guides every step with precision.
              </p>
            </div>
            <div className={styles.stepsRow}>
              {HOW_IT_WORKS.map((step, i) => (
                <StepCard key={step.step} step={step} index={i} />
              ))}
            </div>
          </div>
        </section>

        {/* ══ FEATURES ════════════════════════════════════════════════════════ */}
        <section className={styles.features}>
          <div className={styles.featuresInner}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionKicker}>Practice system</span>
              <h2 className={styles.sectionTitle}>Built for deliberate preparation</h2>
              <p className={styles.sectionSub}>
                Every feature is designed around one goal: measurable improvement per hour of practice.
              </p>
            </div>
            <div className={styles.featureGrid}>
              {FEATURES.map((feature, i) => (
                <FeatureCard key={feature.title} feature={feature} index={i} />
              ))}
            </div>
          </div>
        </section>

        {/* ══ AI SPOTLIGHT ════════════════════════════════════════════════════ */}
        <section className={styles.aiSection}>
          <div ref={aiRef} className={`${styles.aiInner} ${aiVisible ? styles.aiVisible : ""}`}>
            <div className={styles.aiContent}>
              <span className={styles.sectionKicker}>New · AI Generator</span>
              <h2 className={styles.aiTitle}>
                Never run out of<br />practice material
              </h2>
              <p className={styles.aiDesc}>
                VYAS's AI Mock Generator creates fresh, exam-relevant questions on demand —
                calibrated to your proficiency level and targeted at your weakest topics.
                Infinite practice. Zero repetition.
              </p>
              <ul className={styles.aiFeatureList}>
                <li className={styles.aiFeatureItem}>
                  <span className={styles.aiCheck} aria-hidden="true">✦</span>
                  Topic-targeted generation
                </li>
                <li className={styles.aiFeatureItem}>
                  <span className={styles.aiCheck} aria-hidden="true">✦</span>
                  Difficulty calibrated to your level
                </li>
                <li className={styles.aiFeatureItem}>
                  <span className={styles.aiCheck} aria-hidden="true">✦</span>
                  Instant explanations &amp; solutions
                </li>
                <li className={styles.aiFeatureItem}>
                  <span className={styles.aiCheck} aria-hidden="true">✦</span>
                  Synced with your performance data
                </li>
              </ul>
              <button className={styles.primaryCta} onClick={() => openModal("signup")}>
                Try AI generator free →
              </button>
            </div>

            <div className={styles.aiVisual} aria-hidden="true">
              <div className={styles.aiCard}>
                <div className={styles.aiCardHeader}>
                  <span className={styles.aiCardDot} />
                  <span className={styles.aiCardDot} />
                  <span className={styles.aiCardDot} />
                  <span className={styles.aiCardTitle}>AI Mock · Generating</span>
                </div>
                <div className={styles.aiCardBody}>
                  <div className={styles.aiLine} style={{ "--w": "90%" }} />
                  <div className={styles.aiLine} style={{ "--w": "75%" }} />
                  <div className={styles.aiLine} style={{ "--w": "60%" }} />
                  <div className={styles.aiOptionRow}>
                    <div className={styles.aiOption}>A</div>
                    <div className={styles.aiOptionBar} style={{ "--w": "82%" }} />
                  </div>
                  <div className={styles.aiOptionRow}>
                    <div className={`${styles.aiOption} ${styles.aiOptionCorrect}`}>B</div>
                    <div className={`${styles.aiOptionBar} ${styles.aiOptionBarCorrect}`} style={{ "--w": "95%" }} />
                  </div>
                  <div className={styles.aiOptionRow}>
                    <div className={styles.aiOption}>C</div>
                    <div className={styles.aiOptionBar} style={{ "--w": "55%" }} />
                  </div>
                  <div className={styles.aiOptionRow}>
                    <div className={styles.aiOption}>D</div>
                    <div className={styles.aiOptionBar} style={{ "--w": "40%" }} />
                  </div>
                </div>
                <div className={styles.aiCardFooter}>
                  <span className={styles.aiTag}>UPSC GS-I</span>
                  <span className={styles.aiTag}>History</span>
                  <span className={styles.aiTag}>Medium</span>
                </div>
              </div>
              {/* ambient glow */}
              <div className={styles.aiGlow} />
            </div>
          </div>
        </section>

        {/* ══ CTA BANNER ══════════════════════════════════════════════════════ */}
        <section className={styles.ctaBanner}>
          <div ref={ctaRef} className={`${styles.ctaInner} ${ctaVisible ? styles.ctaVisible : ""}`}>
            <div className={styles.ctaTextGroup}>
              <span className={styles.ctaKicker}>Ready to ascend?</span>
              <h2 className={styles.ctaTitle}>Train with clarity.<br />Rise with discipline.</h2>
              <p className={styles.ctaSub}>
                Join aspirants who choose precision over guesswork.
                Your first mock test is free — always.
              </p>
            </div>
            <div className={styles.ctaActions}>
              <button className={styles.ctaBtn} onClick={() => openModal("signup")}>
                Start practising free →
              </button>
              <button className={styles.ctaSecondaryBtn} onClick={() => openModal("login")}>
                Already a member? Sign in
              </button>
            </div>
          </div>
        </section>

      </main>

      {/* ══ FOOTER ═════════════════════════════════════════════════════════════ */}
      <footer className={styles.footer}>
        <div className={styles.footerLeft}>
          <VyasLogo variant="gold" size={30} />
          <div className={styles.footerBrandText}>
            <span className={styles.footerBrand}>VYAS</span>
            <span className={styles.footerText}>Intelligence · Discipline · Ascent</span>
          </div>
        </div>
        <nav className={styles.footerLinks}>
          <Link to="/about"   className={styles.footerLink}>About</Link>
          <Link to="/contact" className={styles.footerLink}>Contact</Link>
          <Link to="/privacy" className={styles.footerLink}>Privacy</Link>
          <Link to="/terms"   className={styles.footerLink}>Terms</Link>
        </nav>
      </footer>

      {/* ══ AUTH MODAL ══════════════════════════════════════════════════════════ */}
      {modalOpen && (
        <div className={styles.overlay} onClick={closeModal}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div className={styles.modalBrand}>
                <VyasLogo variant="gold" size={40} />
                <span>VYAS</span>
              </div>
              <button
                className={styles.modalClose}
                onClick={closeModal}
                disabled={loading}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

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

            <form className={styles.form} onSubmit={handleSubmit} noValidate>
              {tab === "signup" && (
                <div className={styles.field}>
                  <label className={styles.label} htmlFor="name">Full name</label>
                  <input
                    id="name"
                    name="name"
                    type="text"
                    placeholder="Aditi Sharma"
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

              {tab === "login" && (
                <p style={{ margin: "0", textAlign: "right" }}>
                  <Link
                    to="/forgot-password"
                    style={{ fontSize: "12px", color: "rgba(212,168,67,0.7)", textDecoration: "none" }}
                    onClick={closeModal}
                  >
                    Forgot password?
                  </Link>
                </p>
              )}

              {error && <p className={styles.formError}>{error}</p>}

              <button type="submit" className={styles.submitBtn} disabled={loading}>
                {loading ? "Please wait..." : tab === "login" ? "Sign in →" : "Create account →"}
              </button>

              <p className={styles.consentText}>
                By continuing, you agree to our{" "}
                <Link to="/terms"   className={styles.consentLink} onClick={closeModal}>Terms</Link>
                {" "}&amp;{" "}
                <Link to="/privacy" className={styles.consentLink} onClick={closeModal}>Privacy Policy</Link>
              </p>
            </form>

            <p className={styles.switchText}>
              {tab === "login" ? "No account yet? " : "Already registered? "}
              <button
                className={styles.switchLink}
                onClick={() => { setTab(tab === "login" ? "signup" : "login"); setError(""); }}
                disabled={loading}
              >
                {tab === "login" ? "Create one" : "Sign in"}
              </button>
            </p>
          </div>
        </div>
      )}
    </div>
  );
}