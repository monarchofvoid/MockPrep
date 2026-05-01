import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { login as apiLogin, signup as apiSignup } from "../api/client";
import VyasLogo from "../components/VyasLogo";
import styles from "../styles/Landing.module.css";

const FEATURES = [
  {
    kicker: "Simulate",
    title: "Real exam conditions",
    desc: "Timed papers, structured navigation, review states, and submission discipline built into every attempt.",
  },
  {
    kicker: "Diagnose",
    title: "Performance intelligence",
    desc: "Score, accuracy, pace, and topic mastery are tracked across attempts so progress becomes visible.",
  },
  {
    kicker: "Review",
    title: "Clear solution analysis",
    desc: "Every result opens into question-level review with correct answers, explanations, and behaviour signals.",
  },
  {
    kicker: "Ascend",
    title: "Focused improvement",
    desc: "Weak areas surface naturally, helping learners spend their next session where it matters most.",
  },
];

const EXAMS = ["CUET", "GATE", "CAT", "JEE", "UPSC"];

export default function LandingPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();

  const [modalOpen, setModalOpen] = useState(false);
  const [tab, setTab] = useState("login");
  const [formData, setFormData] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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

      const payload = tab === "login"
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

  return (
    <div className={styles.page}>
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
        <section className={styles.hero}>
          <div className={styles.heroInner}>
            <VyasLogo variant="gold" size={120} animate className={styles.heroLogo} />
            <h1 className={styles.heroTitle}>Ascend with Intelligence</h1>
            <p className={styles.heroSub}>
              VYAS brings disciplined mock practice, precise analytics, and elegant review workflows into one aspirational learning platform.
            </p>
            <div className={styles.examPills}>
              {EXAMS.map((exam) => (
                <span key={exam} className={styles.examPill}>{exam}</span>
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
          </div>
        </section>

        <section className={styles.features}>
          <div className={styles.featuresInner}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionKicker}>Practice system</span>
              <h2 className={styles.sectionTitle}>Built for deliberate preparation</h2>
            </div>
            <div className={styles.featureGrid}>
              {FEATURES.map((feature) => (
                <article key={feature.title} className={styles.featureCard}>
                  <span className={styles.featureKicker}>{feature.kicker}</span>
                  <h3 className={styles.featureTitle}>{feature.title}</h3>
                  <p className={styles.featureDesc}>{feature.desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className={styles.statsBar}>
          <span>10 papers</span>
          <span>700+ questions</span>
          <span>Real exam conditions</span>
        </section>

        <section className={styles.ctaBanner}>
          <div className={styles.ctaInner}>
            <h2 className={styles.ctaTitle}>Train with clarity. Rise with discipline.</h2>
            <button className={styles.ctaBtn} onClick={() => openModal("signup")}>
              Start practising free →
            </button>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <VyasLogo variant="gold" size={34} />
        <div>
          <span className={styles.footerBrand}>VYAS</span>
          <span className={styles.footerText}>Intelligence · Discipline · Ascent</span>
        </div>
      </footer>

      {modalOpen && (
        <div className={styles.overlay} onClick={closeModal}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div className={styles.modalBrand}>
                <VyasLogo variant="gold" size={40} />
                <span>VYAS</span>
              </div>
              <button className={styles.modalClose} onClick={closeModal} disabled={loading} aria-label="Close">
                x
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

              {error && <p className={styles.formError}>{error}</p>}

              <button type="submit" className={styles.submitBtn} disabled={loading}>
                {loading ? "Please wait..." : tab === "login" ? "Sign in →" : "Create account →"}
              </button>
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
