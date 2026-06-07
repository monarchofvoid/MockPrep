'use client'

import { useState } from 'react'
import StaticLayout from '@/components/Staticlayout'
import { sendContactMessage, isApiError, sanitizeMessage } from '@/lib/api'
import styles from '@/styles/StaticPage.module.css'

const MAX_MSG = 3000

function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

/* ── SVG icons ────────────────────────────────────────────────────────────── */
const IconBug = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden="true">
    <path d="M8 2l1.88 1.88M14.12 3.88 16 2M9 7.13v-1a3.003 3.003 0 116 0v1" />
    <path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 014-4h4a4 4 0 014 4v3c0 3.3-2.7 6-6 6z" />
    <path d="M12 20v-9M6.53 9C4.6 8.8 3 7.1 3 5M6 13H2M3 21c0-2.1 1.7-3.9 3.8-4M20.97 5c0 2.1-1.6 3.8-3.5 4M22 13h-4M17.2 17c2.1.1 3.8 1.9 3.8 4" />
  </svg>
)
const IconLightbulb = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden="true">
    <line x1="9" y1="18" x2="15" y2="18" /><line x1="10" y1="22" x2="14" y2="22" />
    <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0018 8 6 6 0 006 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 018.91 14" />
  </svg>
)
const IconFileText = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden="true">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
  </svg>
)
const IconUser = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden="true">
    <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" />
  </svg>
)
const IconCreditCard = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden="true">
    <rect x="1" y="4" width="22" height="16" rx="2" ry="2" /><line x1="1" y1="10" x2="23" y2="10" />
  </svg>
)
const IconHandshake = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="20" height="20" aria-hidden="true">
    <path d="M20.42 4.58a5.4 5.4 0 00-7.65 0l-.77.78-.77-.78a5.4 5.4 0 00-7.65 0C1.46 6.7 1.33 10.28 4 13l8 8 8-8c2.67-2.72 2.54-6.3.42-8.42z" />
  </svg>
)
const IconZap = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
)
const IconMessageCircle = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
  </svg>
)
const IconShieldCheck = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <polyline points="9,12 11,14 15,10" />
  </svg>
)
const IconRefreshCw = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
    <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
  </svg>
)
/* Success icon — SVG circle-check, replaces ✓ unicode */
const IconCircleCheck = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="26" height="26" aria-hidden="true">
    <circle cx="12" cy="12" r="10" />
    <polyline points="7,12 10,15 17,9" />
  </svg>
)
/* FAQ chevron — SVG, no unicode +/- */
const IconChevronDown = () => (
  <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="4,7 10,13 16,7" />
  </svg>
)
const IconChevronUp = () => (
  <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="4,13 10,7 16,13" />
  </svg>
)

const CONTACT_CATEGORIES = [
  { icon: <IconBug />,         label: 'Bug Report',         value: 'bug' },
  { icon: <IconLightbulb />,   label: 'Feature Suggestion', value: 'feature' },
  { icon: <IconFileText />,    label: 'Question Bank Issue', value: 'question' },
  { icon: <IconUser />,        label: 'Account Support',    value: 'account' },
  { icon: <IconCreditCard />,  label: 'Payment Support',    value: 'payment' },
  { icon: <IconHandshake />,   label: 'Partnership',        value: 'partnership' },
]

const SUPPORT_PROMISES = [
  { icon: <IconZap />,          label: 'Fast Responses' },
  { icon: <IconMessageCircle />,label: 'Student-Focused Support' },
  { icon: <IconShieldCheck />,  label: 'Transparent Communication' },
  { icon: <IconRefreshCw />,    label: 'Continuous Improvement' },
]

const FAQ_ITEMS = [
  {
    q: 'How do credits work?',
    a: 'Credits are used to generate AI-powered mock tests. You receive a starting balance when you join and can purchase more from the Wallet page. Each AI mock generation deducts a fixed credit amount shown before you confirm.',
  },
  {
    q: 'Is my data secure?',
    a: 'Yes. Passwords are stored securely and never in plain text. Payments are handled entirely by our payment gateway — we never receive your card details. All sessions are managed through secure, server-side authentication.',
  },
  {
    q: 'How long does it take to get a response?',
    a: 'We aim to respond within 48 hours on working days. For urgent payment issues, include your order ID and we will prioritise your request.',
  },
  {
    q: 'Can I delete my account?',
    a: 'Yes. Contact us through this form requesting account deletion. We will confirm and remove your data in accordance with our Privacy Policy.',
  },
  {
    q: 'How do I report an incorrect question?',
    a: 'Select "Question Bank Issue" as your category, describe the question (paper name and question number), and explain the error. We review every report and publish corrections.',
  },
]

function FaqAccordion() {
  const [openIdx, setOpenIdx] = useState<number | null>(null)
  return (
    <div className={styles.faqList}>
      {FAQ_ITEMS.map((item, i) => (
        <div key={i} className={`${styles.faqItem} ${openIdx === i ? styles.faqItemOpen : ''}`}>
          <button
            className={styles.faqQuestion}
            onClick={() => setOpenIdx(openIdx === i ? null : i)}
            aria-expanded={openIdx === i}
          >
            <span>{item.q}</span>
            <span className={styles.faqChevron} aria-hidden="true">
              {openIdx === i ? <IconChevronUp /> : <IconChevronDown />}
            </span>
          </button>
          {openIdx === i && (
            <div className={styles.faqAnswer}>
              <p>{item.a}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default function ContactPage() {
  const [form, setForm]       = useState({ name: '', email: '', message: '', category: '' })
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError]     = useState('')

  const handle = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((p) => ({ ...p, [e.target.name]: e.target.value }))

  const validate = (): string | null => {
    if (!form.name.trim())                    return 'Please enter your name.'
    if (!form.email.trim())                   return 'Please enter your email address.'
    if (!validateEmail(form.email.trim()))    return 'Please enter a valid email address.'
    if (form.message.trim().length < 10)      return 'Message must be at least 10 characters.'
    if (form.message.trim().length > MAX_MSG) return `Message must be under ${MAX_MSG} characters.`
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const err = validate()
    if (err) { setError(err); return }
    setLoading(true)
    try {
      await sendContactMessage({
        name: form.name.trim(),
        email: form.email.trim(),
        message: form.message.trim(),
      })
      setSuccess(true)
    } catch (err: unknown) {
      if (isApiError(err)) setError(sanitizeMessage(err.message))
      else if (err instanceof Error) setError(err.message)
      else setError('Could not send your message. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const msgLen  = form.message.length
  const nearMax = msgLen > MAX_MSG * 0.85

  return (
    <StaticLayout>
      {/* Hero */}
      <div className={styles.pageHero}>
        <span className={styles.kicker}>Get in touch</span>
        <h1 className={styles.pageTitle}>We&apos;d Love To Hear From You</h1>
        <p className={styles.pageLead}>
          Found a bug, have a suggestion, or spotted a wrong answer in the question bank?
          Tell us — we read and respond to every message.
        </p>
      </div>

      {/* Category selector */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>What can we help with?</h2>
        <div className={styles.categoryGrid}>
          {CONTACT_CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              type="button"
              className={`${styles.categoryCard} ${form.category === cat.value ? styles.categoryCardActive : ''}`}
              onClick={() => setForm((p) => ({ ...p, category: cat.value }))}
            >
              <span className={styles.categoryIconWrap}>{cat.icon}</span>
              <span className={styles.categoryLabel}>{cat.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Support promise */}
      <div className={styles.supportPromise}>
        {SUPPORT_PROMISES.map((p) => (
          <div key={p.label} className={styles.promiseItem}>
            <span className={styles.promiseIconWrap}>{p.icon}</span>
            <span className={styles.promiseLabel}>{p.label}</span>
          </div>
        ))}
      </div>

      {/* Form */}
      {success ? (
        <div className={styles.successBlock}>
          {/* SVG circle-check — replaces ✓ unicode */}
          <div className={styles.successIcon}>
            <IconCircleCheck />
          </div>
          <h3>Message received</h3>
          <p>
            Thanks for reaching out, <strong>{form.name.split(' ')[0]}</strong>.
            We&apos;ll get back to you at <strong>{form.email}</strong> within 48 hours.
          </p>
        </div>
      ) : (
        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          <div className={styles.formRow}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="name">Your name</label>
              <input
                id="name" name="name" type="text" className={styles.input}
                placeholder="Aditi Sharma" value={form.name} onChange={handle}
                disabled={loading} autoComplete="name"
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="email">Email address</label>
              <input
                id="email" name="email" type="email" className={styles.input}
                placeholder="you@example.com" value={form.email} onChange={handle}
                disabled={loading} autoComplete="email"
              />
            </div>
          </div>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="message">Message</label>
            <textarea
              id="message" name="message" className={styles.textarea}
              placeholder="Describe your question, bug report, or feedback…"
              value={form.message} onChange={handle} disabled={loading} maxLength={MAX_MSG}
            />
            {msgLen > 0 && (
              <span className={`${styles.charCount} ${nearMax ? styles.near : ''}`}>
                {msgLen} / {MAX_MSG}
              </span>
            )}
          </div>
          {error && <p className={styles.formError}>{error}</p>}
          <button type="submit" className={styles.submitBtn} disabled={loading}>
            {loading ? 'Sending…' : 'Send Message'}
          </button>
        </form>
      )}

      <hr className={styles.divider} />

      {/* FAQ */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Frequently Asked Questions</h2>
        <FaqAccordion />
      </div>

      <hr className={styles.divider} />

      <div className={styles.infoCard}>
        <p>
          Prefer email directly?{' '}
          <a href="mailto:support@vyasmock.online">support@vyasmock.online</a>
        </p>
        <p style={{ marginTop: 8 }}>
          <strong>Response time:</strong> within 48 hours on working days.
        </p>
      </div>
    </StaticLayout>
  )
}
