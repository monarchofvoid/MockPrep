import { useState } from "react";
import StaticLayout from "../components/StaticLayout";
import styles from "../styles/StaticPage.module.css";

const BASE    = import.meta.env.VITE_API_URL || "http://localhost:8000";
const MAX_MSG = 3000;

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export default function Contact() {
  const [form, setForm]       = useState({ name: "", email: "", message: "" });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error,   setError]   = useState("");

  const handle = (e) =>
    setForm((p) => ({ ...p, [e.target.name]: e.target.value }));

  const validate = () => {
    if (!form.name.trim())                   return "Please enter your name.";
    if (!form.email.trim())                  return "Please enter your email address.";
    if (!validateEmail(form.email.trim()))   return "Please enter a valid email address.";
    if (form.message.trim().length < 10)     return "Message must be at least 10 characters.";
    if (form.message.trim().length > MAX_MSG) return `Message must be under ${MAX_MSG} characters.`;
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const err = validate();
    if (err) { setError(err); return; }

    setLoading(true);
    try {
      const res = await fetch(`${BASE}/api/contact`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          name:    form.name.trim(),
          email:   form.email.trim(),
          message: form.message.trim(),
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(
          data?.detail?.[0]?.msg || data?.detail || "Something went wrong."
        );
      }

      setSuccess(true);
    } catch (err) {
      setError(err.message || "Could not send your message. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const msgLen  = form.message.length;
  const nearMax = msgLen > MAX_MSG * 0.85;

  return (
    <StaticLayout>
      {/* ── Header ── */}
      <div className={styles.header}>
        <span className={styles.kicker}>Get in touch</span>
        <h1 className={styles.pageTitle}>Contact Us</h1>
        <p className={styles.pageLead}>
          Found a bug, have a suggestion, or spotted a wrong answer in a question
          bank? Tell us — we read and respond to every message.
        </p>
      </div>

      {success ? (
        /* ── Success state ── */
        <div className={styles.successBlock}>
          <div className={styles.successIcon}>✓</div>
          <h3>Message received</h3>
          <p>
            Thanks for reaching out, <strong>{form.name.split(" ")[0]}</strong>.
            We'll get back to you at <strong>{form.email}</strong> within 48 hours.
          </p>
        </div>
      ) : (
        /* ── Form ── */
        <form className={styles.form} onSubmit={handleSubmit} noValidate>

          <div className={styles.field}>
            <label className={styles.label} htmlFor="name">Your name</label>
            <input
              id="name"
              name="name"
              type="text"
              className={styles.input}
              placeholder="Aditi Sharma"
              value={form.name}
              onChange={handle}
              disabled={loading}
              autoComplete="name"
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label} htmlFor="email">Email address</label>
            <input
              id="email"
              name="email"
              type="email"
              className={styles.input}
              placeholder="you@example.com"
              value={form.email}
              onChange={handle}
              disabled={loading}
              autoComplete="email"
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label} htmlFor="message">Message</label>
            <textarea
              id="message"
              name="message"
              className={styles.textarea}
              placeholder="Describe your question, bug report, or feedback…"
              value={form.message}
              onChange={handle}
              disabled={loading}
              maxLength={MAX_MSG}
            />
            {msgLen > 0 && (
              <span className={`${styles.charCount} ${nearMax ? styles.near : ""}`}>
                {msgLen} / {MAX_MSG}
              </span>
            )}
          </div>

          {error && <p className={styles.formError}>{error}</p>}

          <button
            type="submit"
            className={styles.submitBtn}
            disabled={loading}
          >
            {loading ? "Sending…" : "Send Message →"}
          </button>
        </form>
      )}

      <hr className={styles.divider} />

      {/* ── Direct contact info ── */}
      <div className={styles.infoCard}>
        <p>
          Prefer email directly?{" "}
          <a href="sinabhinav19@gmail.com">sinabhinav19@gmail.com</a>
        </p>
        <p style={{ marginTop: 8 }}>
          <strong>Response time:</strong> within 48 hours on working days.
        </p>
      </div>
    </StaticLayout>
  );
}
