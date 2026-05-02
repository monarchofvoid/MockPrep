import { useState, useEffect } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { resetPassword } from "../api/client";
import VyasLogo from "../components/VyasLogo";
import styles from "../styles/PasswordReset.module.css";

const MIN_LEN = 8;

export default function ResetPassword() {
  const [searchParams]              = useSearchParams();
  const navigate                    = useNavigate();

  const [password,  setPassword]    = useState("");
  const [confirm,   setConfirm]     = useState("");
  const [loading,   setLoading]     = useState(false);
  const [success,   setSuccess]     = useState(false);
  const [error,     setError]       = useState("");
  const [tokenMissing, setTokenMissing] = useState(false);

  const token = searchParams.get("token") || "";

  useEffect(() => {
    if (!token) setTokenMissing(true);
  }, [token]);

  // Password strength helpers
  const strength = (() => {
    if (!password) return null;
    if (password.length < MIN_LEN) return "weak";
    const hasUpper  = /[A-Z]/.test(password);
    const hasLower  = /[a-z]/.test(password);
    const hasDigit  = /\d/.test(password);
    const hasSymbol = /[^A-Za-z0-9]/.test(password);
    const score = [hasUpper, hasLower, hasDigit, hasSymbol].filter(Boolean).length;
    if (score <= 2) return "fair";
    if (score === 3) return "good";
    return "strong";
  })();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (password.length < MIN_LEN) {
      setError(`Password must be at least ${MIN_LEN} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }

    setLoading(true);
    try {
      await resetPassword(token, password);
      setSuccess(true);
      // Auto-redirect to home after 3 seconds
      setTimeout(() => navigate("/", { replace: true }), 3000);
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  /* ── Guard: no token in URL ──────────────────────────────────────────────── */
  if (tokenMissing) {
    return (
      <div className={styles.page}>
        <div className={styles.card}>
          <div className={styles.brand}>
            <VyasLogo variant="gold" size={44} />
            <span className={styles.brandName}>VYAS</span>
          </div>
          <div className={styles.errorBlock}>
            <div className={styles.errorIcon}>✕</div>
            <h1 className={styles.title}>Invalid reset link</h1>
            <p className={styles.subtitle}>
              This link is missing a reset token. Please request a new one.
            </p>
            <Link to="/forgot-password" className={styles.submitBtn} style={{ textDecoration: "none", display: "inline-block" }}>
              Request new link →
            </Link>
          </div>
          <p className={styles.backLink}>
            <Link to="/" className={styles.link}>← Back to sign in</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>

        {/* Brand */}
        <div className={styles.brand}>
          <VyasLogo variant="gold" size={44} />
          <span className={styles.brandName}>VYAS</span>
        </div>

        {success ? (
          /* ── Success state ─────────────────────────────────────────────── */
          <div className={styles.successBlock}>
            <div className={styles.successIcon}>✓</div>
            <h1 className={styles.title}>Password updated</h1>
            <p className={styles.subtitle}>
              Your password has been changed successfully. Redirecting you to
              sign in…
            </p>
            <Link to="/" className={styles.submitBtn} style={{ textDecoration: "none", display: "inline-block" }}>
              Sign in now →
            </Link>
          </div>
        ) : (
          /* ── Reset form ────────────────────────────────────────────────── */
          <>
            <h1 className={styles.title}>Choose a new password</h1>
            <p className={styles.subtitle}>
              Pick something strong. Minimum {MIN_LEN} characters.
            </p>

            <form className={styles.form} onSubmit={handleSubmit} noValidate>

              {/* New password */}
              <div className={styles.field}>
                <label className={styles.label} htmlFor="password">
                  New password
                </label>
                <input
                  id="password"
                  type="password"
                  placeholder={`At least ${MIN_LEN} characters`}
                  className={styles.input}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  disabled={loading}
                  required
                />
                {/* Strength indicator */}
                {strength && (
                  <div className={`${styles.strength} ${styles[`strength_${strength}`]}`}>
                    <span className={styles.strengthBar} />
                    <span className={styles.strengthBar} />
                    <span className={styles.strengthBar} />
                    <span className={styles.strengthBar} />
                    <span className={styles.strengthLabel}>{strength}</span>
                  </div>
                )}
              </div>

              {/* Confirm password */}
              <div className={styles.field}>
                <label className={styles.label} htmlFor="confirm">
                  Confirm password
                </label>
                <input
                  id="confirm"
                  type="password"
                  placeholder="Repeat your new password"
                  className={styles.input}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="new-password"
                  disabled={loading}
                  required
                />
                {confirm && password !== confirm && (
                  <p className={styles.fieldHint}>Passwords don't match yet.</p>
                )}
              </div>

              {error && <p className={styles.formError}>{error}</p>}

              <button
                type="submit"
                className={styles.submitBtn}
                disabled={loading || password.length < MIN_LEN || password !== confirm}
              >
                {loading ? "Updating…" : "Set new password →"}
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
