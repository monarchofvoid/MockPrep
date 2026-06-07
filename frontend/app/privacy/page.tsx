import type { Metadata } from 'next'
import Link from 'next/link'
import StaticLayout from '@/components/Staticlayout'
import styles from '@/styles/StaticPage.module.css'

export const metadata: Metadata = {
  title: 'Privacy Policy — VYAS',
  description: 'Privacy policy for the VYAS exam preparation platform. Your data belongs to you.',
}

/* ── SVG icons ────────────────────────────────────────────────────────────── */
const IconNoSell = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
    <circle cx="12" cy="12" r="10" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
  </svg>
)
const IconLock = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0110 0v4" />
  </svg>
)
const IconShield = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
)
const IconEye = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
  </svg>
)
/* Inline SVG check for security badges — replaces ✓ unicode */
const SvgTick = () => (
  <svg viewBox="0 0 12 12" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="2,6 5,9 10,3" />
  </svg>
)

const HIGHLIGHTS = [
  { icon: <IconNoSell />, title: "We Don't Sell Data",     desc: 'Your personal information is never sold or shared with advertisers.' },
  { icon: <IconLock />,   title: 'Secure Accounts',        desc: 'Industry-standard security for authentication, sessions, and account recovery.' },
  { icon: <IconShield />, title: 'Protected Payments',     desc: 'All payment processing is handled by a certified payment gateway. We never receive your card details.' },
  { icon: <IconEye />,    title: 'Transparent Practices',  desc: 'We collect only what we need to make the platform work for you, and nothing more.' },
]

const SECURITY_FEATURES = [
  'Secure password storage',
  'Encrypted sessions',
  'Protected account recovery',
  'Payment isolation',
  'HTTPS enforced',
  'Rate limiting',
  'Access controls',
  'Audit logging',
]

const PRIVACY_SECTIONS = [
  {
    id: '1',
    title: '1. Information We Collect',
    content: [
      'Account details — your name, email address, and a secure version of your password — collected when you register.',
      'Practice data — mock attempts, answers, scores, and topic performance — stored to power your analytics dashboard.',
      'Wallet and transaction data — credit balance and purchase history — so your wallet reflects the correct balance at all times.',
      'Support messages — name, email, and message content — so we can respond and investigate reported issues.',
      'Standard server logs — including request timestamps — used only for security and debugging.',
    ],
  },
  {
    id: '2',
    title: '2. How We Use Your Information',
    content: [
      'To authenticate your account and maintain a secure, persistent session.',
      'To power your performance dashboard — scores, topic mastery, attempt history, and improvement trends.',
      'To generate AI mocks calibrated to your level and focused on your weak areas.',
      'To process credit purchases, maintain wallet balances, and generate payment records.',
      'To respond to support requests, bug reports, and account recovery.',
    ],
  },
  {
    id: '3',
    title: '3. Cookies and Sessions',
    content: [
      'VYAS uses secure session management for authentication. Your session cannot be read or hijacked by third-party scripts.',
      'We do not use advertising cookies or third-party tracking pixels.',
      'Your browser may store non-sensitive display data for faster interface loading. This data is never used for authentication.',
    ],
  },
  {
    id: '4',
    title: '4. Payments',
    content: [
      'All payment processing is handled by a PCI-compliant payment gateway.',
      'VYAS never receives, stores, or processes your card number, UPI ID, net banking credentials, or any payment instrument details.',
      'We store only payment status, credit grant records, and transaction history — the same information visible in your wallet.',
      'For refund requests, contact us with your order ID.',
    ],
  },
  {
    id: '5',
    title: '5. Account Recovery',
    content: [
      'Password reset links are single-use and expire automatically after a short window.',
      'When your password is reset, all existing sessions are ended. You will need to sign in again on any active devices.',
      'We do not send marketing emails. You will only receive transactional emails — password reset, payment confirmation — when they are triggered by your own actions.',
    ],
  },
  {
    id: '6',
    title: '6. Data Sharing',
    content: [
      'We do not sell your personal information, ever.',
      'We share data only with service providers required to operate VYAS — hosting, email delivery, payment processing, and AI generation services.',
      'All third-party providers are contractually prohibited from using your data for their own purposes.',
      'We may disclose data if required by law or to protect the rights, safety, or property of VYAS or our users.',
    ],
  },
  {
    id: '7',
    title: '7. Data Retention',
    content: [
      'Your account and practice data is retained as long as your account is active.',
      'Payment and transaction records are retained for compliance with applicable accounting requirements.',
      'Contact form messages are retained for up to 2 years.',
      'When an account is deleted, associated personal data is removed in accordance with our deletion policy.',
    ],
  },
  {
    id: '8',
    title: '8. Your Rights and Choices',
    content: [
      'You can update your profile information from the app at any time.',
      'You can request a full export of your personal data by contacting us.',
      'You can request permanent account deletion. We will delete your account and associated personal data within 30 days, except where retention is required by law.',
      'For any privacy questions, contact us at support@vyasmock.online.',
    ],
  },
]

export default function PrivacyPage() {
  return (
    <StaticLayout>
      {/* Hero */}
      <div className={styles.pageHero}>
        <span className={styles.kicker}>Legal</span>
        <h1 className={styles.pageTitle}>Your Data Belongs To You</h1>
        <p className={styles.pageMeta}>Last updated: May 2026</p>
        <p className={styles.pageLead}>
          This policy explains what VYAS collects, why we collect it, and how we protect it.
          Plain language — no tricks.
        </p>
      </div>

      {/* Highlights */}
      <div className={styles.highlightsGrid}>
        {HIGHLIGHTS.map((h) => (
          <div key={h.title} className={styles.highlightCard}>
            <div className={styles.highlightIconWrap}>{h.icon}</div>
            <h3 className={styles.highlightTitle}>{h.title}</h3>
            <p className={styles.highlightDesc}>{h.desc}</p>
          </div>
        ))}
      </div>

      {/* Security features — ✓ replaced with SVG */}
      <div className={styles.securityShowcase}>
        <h3 className={styles.securityTitle}>Security features</h3>
        <div className={styles.securityBadges}>
          {SECURITY_FEATURES.map((b) => (
            <span key={b} className={styles.securityBadge}>
              <span className={styles.securityBadgeTick}><SvgTick /></span>
              {b}
            </span>
          ))}
        </div>
      </div>

      <hr className={styles.divider} />

      {/* Full policy */}
      {PRIVACY_SECTIONS.map((section) => (
        <div key={section.id} className={styles.section}>
          <h2 className={styles.sectionTitle}>{section.title}</h2>
          <ul>
            {section.content.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      ))}

      <hr className={styles.divider} />

      <div className={styles.infoCard}>
        <p>
          Questions about privacy?{' '}
          <Link href="/contact">Contact us</Link>. You can also review our{' '}
          <Link href="/terms">Terms &amp; Conditions</Link>.
        </p>
      </div>
    </StaticLayout>
  )
}
