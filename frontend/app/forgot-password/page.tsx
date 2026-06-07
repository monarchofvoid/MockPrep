'use client'

/**
 * VYAS — Forgot / Reset Password Page
 * =====================================
 * v2.1: Eye toggles on both password fields (preserved)
 * v2.2: Real-time password strength meter (preserved)
 *
 * v2.1.5 API migration:
 *   - Removed `api` namespace import (no longer exported by api.ts)
 *   - Replaced api.auth.forgotPassword() → forgotPassword() named import
 *   - Replaced api.auth.resetPassword(token, pwd) → resetPassword({ token, new_password })
 *     (function signature changed to accept a data object)
 *   - Replaced VYASApiError → isApiError() type guard (class removed from api.ts)
 *   - Error messages come through sanitizeMessage() automatically via api.ts internals
 */

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useMemo, useState } from 'react'
import VyasLogo from '@/components/VyasLogo'
import { forgotPassword, resetPassword, isApiError } from '@/lib/api'
import styles from '@/styles/PasswordReset.module.css'

// ── Eye icons ─────────────────────────────────────────────────────────────────

function SvgEye() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function SvgEyeOff() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  )
}

// ── Password rules & strength ─────────────────────────────────────────────────

interface StrengthResult {
  level: 'empty' | 'weak' | 'fair' | 'good' | 'strong'
  score: number
  failures: string[]
  isValid: boolean
}

function analysePassword(pw: string): StrengthResult {
  if (!pw) return { level: 'empty', score: 0, failures: [], isValid: false }

  const rules = [
    { label: 'At least 9 characters',                   met: pw.length >= 9 },
    { label: 'At least one uppercase letter (A–Z)',      met: /[A-Z]/.test(pw) },
    { label: 'At least one digit (1–9)',                 met: /[1-9]/.test(pw) },
    { label: 'At least one special character (@#&!%…)',  met: /[^A-Za-z0-9]/.test(pw) },
  ]

  const score    = rules.filter((r) => r.met).length
  const failures = rules.filter((r) => !r.met).map((r) => r.label)
  const isValid  = score === 4

  const level: StrengthResult['level'] =
    score === 4 ? 'strong' :
    score === 3 ? 'good'   :
    score === 2 ? 'fair'   : 'weak'

  return { level, score, failures, isValid }
}

// ── Strength meter component ──────────────────────────────────────────────────

function StrengthMeter({ password }: { password: string }) {
  if (!password) return null

  const { level, failures } = analysePassword(password)

  const cssLevel =
    level === 'strong' ? 'strong' :
    level === 'good'   ? 'good'   :
    level === 'fair'   ? 'fair'   : 'weak'

  return (
    <div style={{ marginTop: '6px' }}>
      <div className={`${styles.strength} ${styles[`strength_${cssLevel}`]}`}>
        <span className={styles.strengthBar} />
        <span className={styles.strengthBar} />
        <span className={styles.strengthBar} />
        <span className={styles.strengthBar} />
        <span className={styles.strengthLabel}>{level}</span>
      </div>

      {failures.length > 0 && (
        <ul style={{ margin: '6px 0 0', padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '3px' }}>
          {failures.map((f) => (
            <li key={f} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#9a9080', lineHeight: 1.4 }}>
              <span style={{ display: 'inline-block', width: '5px', height: '5px', borderRadius: '50%', background: '#ef4444', flexShrink: 0 }} />
              {f}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Password input with eye toggle ────────────────────────────────────────────

interface PasswordFieldProps {
  id: string
  label: string
  placeholder: string
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  disabled: boolean
  autoComplete?: string
  showMeter?: boolean
}

function PasswordField({
  id, label, placeholder, value, onChange, disabled,
  autoComplete = 'new-password', showMeter = false,
}: PasswordFieldProps) {
  const [show, setShow] = useState(false)

  return (
    <label className={styles.field}>
      <span className={styles.label}>{label}</span>
      <div style={{ position: 'relative' }}>
        <input
          id={id}
          className={styles.input}
          type={show ? 'text' : 'password'}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          required
          disabled={disabled}
          autoComplete={autoComplete}
          style={{ paddingRight: '44px', boxSizing: 'border-box', width: '100%' }}
        />
        <button
          type="button"
          onClick={() => setShow((v) => !v)}
          aria-label={show ? 'Hide password' : 'Show password'}
          tabIndex={-1}
          style={{
            position: 'absolute', right: '12px', top: '50%',
            transform: 'translateY(-50%)',
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#6f6659', display: 'flex', alignItems: 'center', padding: '4px',
          }}
        >
          {show ? <SvgEyeOff /> : <SvgEye />}
        </button>
      </div>
      {showMeter && <StrengthMeter password={value} />}
    </label>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ForgotPasswordPage() {
  const router       = useRouter()
  const searchParams = useSearchParams()
  const token        = searchParams.get('token')
  const mode         = token ? 'reset' : 'request'

  const [email,           setEmail]           = useState('')
  const [newPassword,     setNewPassword]     = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [message,         setMessage]         = useState('')
  const [error,           setError]           = useState('')
  const [loading,         setLoading]         = useState(false)

  const newPwStrength = useMemo(() => analysePassword(newPassword), [newPassword])

  // ── Request reset link ─────────────────────────────────────────────────────
  const handleRequest = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    try {
      // FIX: was api.auth.forgotPassword(email) → named import forgotPassword(email)
      await forgotPassword(email.trim())
      setMessage('If an account exists for that email, a secure reset link has been sent.')
      setEmail('')
    } catch (err: unknown) {
      // FIX: was err.message (untyped) → isApiError() type guard
      if (isApiError(err)) {
        setError(err.message || 'Failed to send reset email.')
      } else {
        setError('Failed to send reset email.')
      }
    } finally {
      setLoading(false)
    }
  }

  // ── Submit new password ────────────────────────────────────────────────────
  const handleReset = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setMessage('')

    if (!newPwStrength.isValid) {
      setError('Please meet all password requirements shown below.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      // FIX: was api.auth.resetPassword(token!, newPassword)
      // New signature: resetPassword({ token, new_password })
      await resetPassword({ token: token!, new_password: newPassword })
      setMessage('Password updated. Redirecting you to sign in...')
      setTimeout(() => router.push('/'), 1800)
    } catch (err: unknown) {
      // FIX: was err.message (untyped) → isApiError() type guard
      if (isApiError(err)) {
        setError(err.message || 'Failed to reset password.')
      } else {
        setError('Failed to reset password.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.shell}>

        {/* ── Left panel ──────────────────────────────────────────────────── */}
        <div className={styles.panel}>
          <Link href="/" className={styles.brand}>
            <VyasLogo variant="gold" size={38} />
            <span className={styles.brandName}>VYAS</span>
          </Link>

          <div className={styles.copyBlock}>
            <span className={styles.kicker}>Account recovery</span>
            <h1 className={styles.title}>
              {mode === 'request' ? 'Recover your access' : 'Set a new password'}
            </h1>
            <p className={styles.subtitle}>
              {mode === 'request'
                ? 'Enter the email linked to your VYAS account. We will send a one-time reset link if it exists.'
                : 'Choose a strong password to secure your VYAS account before returning to your dashboard.'}
            </p>
          </div>

          <div className={styles.securityList} aria-label="Security notes">
            <span>One-time reset link</span>
            <span>Expires automatically</span>
            <span>Sessions revoked after reset</span>
          </div>
        </div>

        {/* ── Right card ──────────────────────────────────────────────────── */}
        <div className={styles.card}>

          {message ? (
            <div className={styles.successBlock}>
              <div className={styles.successIcon}>✓</div>
              <h2>{mode === 'request' ? 'Check your inbox' : 'Password changed'}</h2>
              <p>{message}</p>
              {mode === 'request' && (
                <button className={styles.secondaryBtn} onClick={() => setMessage('')}>
                  Send another link
                </button>
              )}
            </div>

          ) : mode === 'request' ? (
            /* ── Request form ─────────────────────────────────────────────── */
            <form onSubmit={handleRequest} className={styles.form}>
              <div className={styles.formHeader}>
                <span className={styles.formStep}>Step 1 of 2</span>
                <h2>Send reset link</h2>
              </div>

              <label className={styles.field}>
                <span className={styles.label}>Email address</span>
                <input
                  className={styles.input}
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={loading}
                  autoComplete="email"
                />
              </label>

              {error && <p className={styles.formError}>{error}</p>}

              <button type="submit" disabled={loading} className={styles.submitBtn}>
                {loading ? 'Sending...' : 'Send reset link'}
              </button>
            </form>

          ) : (
            /* ── Reset form ───────────────────────────────────────────────── */
            <form onSubmit={handleReset} className={styles.form}>
              <div className={styles.formHeader}>
                <span className={styles.formStep}>Step 2 of 2</span>
                <h2>Create new password</h2>
              </div>

              <PasswordField
                id="new-password"
                label="New password"
                placeholder="Min. 9 chars, A-Z, 1-9, @#!…"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                disabled={loading}
                autoComplete="new-password"
                showMeter={true}
              />

              <PasswordField
                id="confirm-password"
                label="Confirm password"
                placeholder="Re-enter password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={loading}
                autoComplete="new-password"
                showMeter={false}
              />

              {confirmPassword && newPassword !== confirmPassword && (
                <p style={{ margin: 0, fontSize: '12px', color: '#fca5a5' }}>
                  Passwords do not match
                </p>
              )}

              {error && <p className={styles.formError}>{error}</p>}

              <button
                type="submit"
                disabled={loading || !newPwStrength.isValid || newPassword !== confirmPassword}
                className={styles.submitBtn}
              >
                {loading ? 'Updating...' : 'Reset password'}
              </button>
            </form>
          )}

          <p className={styles.backLink}>
            Remembered it?{' '}
            <Link href="/" className={styles.link}>Return to sign in</Link>
          </p>
        </div>
      </section>
    </main>
  )
}