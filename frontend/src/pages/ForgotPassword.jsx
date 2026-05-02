import { useState } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "../api/client";
import VyasLogo from "../components/VyasLogo";
import styles from "../styles/PasswordReset.module.css";

export default function ForgotPassword() {
  const [email,     setEmail]     = useState("");
  const [loading,   setLoading]   = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error,     setError]     = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!email.trim()) {
      setError("Please enter your email address.");
      return;
    }

    setLoading(true);
    try {
      await forgotPassword(email.trim());
      setSubmitted(true);
    } catch (err) {
      // Surface network/server errors; API-level "not found" is swallowed by
      // the backend and returns 200, so this only fires on real errors.
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.card}>

        {/* Brand */}
        <div className={styles.brand}>
          <VyasLogo variant="gold" size={44} />
          <span className={styles.brandName}>VYAS</span>
        </div>

        {submitted ? (
          /* ── Success state ─────────────────────────────────────────────── */
          <div className={styles.successBlock}>
            <div className={styles.successIcon}>✓</div>
            <h1 className={styles.title}>Check your inbox</h1>
            <p className={styles.subtitle}>
              If <strong>{email}</strong> is registered with VYAS, you'll receive
              a reset link within a few seconds. The link expires in&nbsp;
              <strong>15&nbsp;minutes</strong>.
            </p>
            <p className={styles.note}>
              Didn't receive it? Check your spam folder or&nbsp;
              <button
                className={styles.retryLink}
                onClick={() => { setSubmitted(false); setEmail(""); }}
              >
                try again
              </button>
              .
            </p>
          </div>
        ) : (
          /* ── Request form ──────────────────────────────────────────────── */
          <>
            <h1 className={styles.title}>Forgot password?</h1>
            <p className={styles.subtitle}>
              Enter the email you signed up with and we'll send you a reset link.
            </p>

            <form className={styles.form} onSubmit={handleSubmit} noValidate>
              <div className={styles.field}>
                <label className={styles.label} htmlFor="email">
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  className={styles.input}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  disabled={loading}
                  required
                />
              </div>

              {error && <p className={styles.formError}>{error}</p>}

              <button
                type="submit"
                className={styles.submitBtn}
                disabled={loading}
              >
                {loading ? "Sending link…" : "Send reset link →"}
              </button>
            </form>
          </>
        )}

        <p className={styles.backLink}>
          <Link to="/" className={styles.link}>← Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
