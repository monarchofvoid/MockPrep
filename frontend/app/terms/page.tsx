import type { Metadata } from 'next';
import Link from 'next/link';
import StaticLayout from '@/components/Staticlayout';
import styles from '@/styles/StaticPage.module.css';

export const metadata: Metadata = {
  title: 'Terms & Conditions — VYAS',
  description: 'Terms and conditions for using the VYAS platform. Simple terms, no hidden tricks.',
};

/* ── SVG icons replacing unicode ✓ and ✕ ─────────────────────────────────── */
const SvgCheck = () => (
  <svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="2,7 5.5,10.5 12,3" />
  </svg>
)
const SvgX = () => (
  <svg viewBox="0 0 14 14" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
    <line x1="2" y1="2" x2="12" y2="12" />
    <line x1="12" y1="2" x2="2" y2="12" />
  </svg>
)

export default function TermsPage() {
  return (
    <StaticLayout>
      {/* Hero */}
      <div className={styles.pageHero}>
        <span className={styles.kicker}>Legal</span>
        <h1 className={styles.pageTitle}>Simple Terms. No Hidden Tricks.</h1>
        <p className={styles.pageMeta}>Last updated: June 2025</p>
        <p className={styles.pageLead}>
          By creating an account or using VYAS, you agree to these terms.
          Written plainly — not in legalese.
        </p>
      </div>

      {/* Quick summary cards — SVG icons, no unicode */}
      <div className={styles.termsSummaryGrid}>
        <div className={styles.termsSummaryCard}>
          <h3 className={styles.termsSummaryTitle}>
            <span className={styles.termsSummaryIcon}><SvgCheck /></span>
            You Can
          </h3>
          <ul className={styles.termsSummaryList}>
            <li>Take mock tests</li>
            <li>Generate AI papers</li>
            <li>Track your progress</li>
            <li>Purchase and use credits</li>
            <li>Contact support any time</li>
          </ul>
        </div>
        <div className={`${styles.termsSummaryCard} ${styles.termsSummaryCardNo}`}>
          <h3 className={styles.termsSummaryTitle}>
            <span className={`${styles.termsSummaryIcon} ${styles.termsSummaryIconNo}`}><SvgX /></span>
            You Cannot
          </h3>
          <ul className={`${styles.termsSummaryList} ${styles.termsSummaryListNo}`}>
            <li>Abuse or disrupt the platform</li>
            <li>Scrape content with bots</li>
            <li>Create fraudulent accounts</li>
            <li>Reverse engineer systems</li>
            <li>Access other users&apos; data</li>
          </ul>
        </div>
      </div>

      <hr className={styles.divider} />

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>1. Acceptance of Terms</h2>
        <p>
          Access to and use of VYAS (the &quot;Platform&quot;) is conditional on your acceptance of and compliance with
          these Terms &amp; Conditions (&quot;Terms&quot;). These Terms apply to all visitors, users, and anyone else who
          accesses or uses the Platform.
        </p>
        <p>
          If you disagree with any part of these Terms, you do not have permission to access the Platform.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>2. Your Account</h2>
        <ul>
          <li>You must provide accurate, complete information when creating an account and keep it up to date.</li>
          <li>You are responsible for maintaining the confidentiality of your password and for all activity under your account.</li>
          <li>You must be at least 13 years of age to create an account.</li>
          <li>One account per person. Creating multiple accounts to circumvent restrictions or misrepresent performance is prohibited.</li>
          <li>Notify us immediately if you believe your account has been compromised.</li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>3. Acceptable Use</h2>
        <p>You agree not to:</p>
        <ul>
          <li>Use the Platform for any unlawful purpose or in violation of any applicable local, national, or international law.</li>
          <li>Attempt to gain unauthorised access to any part of the Platform, its servers, or connected systems.</li>
          <li>Reverse-engineer, decompile, disassemble, scrape, or otherwise attempt to derive the source code or underlying data of the Platform.</li>
          <li>Use automated scripts, bots, or crawlers to interact with the Platform without prior written permission.</li>
          <li>Attempt to access, alter, or delete another user&apos;s data or account.</li>
          <li>Submit false, misleading, or malicious content through any Platform feature.</li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>4. Credits and Payments</h2>
        <ul>
          <li>Credits are a virtual currency used to access AI Mock Generation and other premium features.</li>
          <li>Credits are purchased through Razorpay and credited to your wallet on confirmed payment.</li>
          <li>Credits are non-transferable and non-refundable once consumed.</li>
          <li>Unused credits may be refunded at our discretion within 7 days of purchase if no credits have been consumed.</li>
          <li>We reserve the right to modify credit pricing and the credit cost of features with reasonable notice.</li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>5. Intellectual Property</h2>
        <p>
          The VYAS name, logo, interface design, and any original software are the intellectual property of the
          Platform&apos;s operators and are protected by applicable copyright and trademark law.
        </p>
        <p>
          Questions and past paper content are sourced from publicly available materials published by their respective
          conducting bodies (such as NTA and IITs). VYAS does not claim ownership over such content and uses it solely
          for educational and practice purposes.
        </p>
        <p>You may not reproduce, distribute, or create derivative works from VYAS&apos;s original content without written permission.</p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>6. Platform Rights and Availability</h2>
        <p>
          We reserve the right to modify, suspend, or discontinue the Platform — or any part of it — at any time,
          with or without notice.
        </p>
        <p>
          We may add, remove, or change features, question banks, or access tiers at our discretion. We are not liable
          to you or any third party for any such modification or interruption.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>7. Limitation of Liability</h2>
        <p>
          VYAS is provided &quot;as is&quot; and &quot;as available&quot; without warranty of any kind, express or implied.
          We do not guarantee that the Platform will be uninterrupted, error-free, or that the content is accurate
          or complete at all times.
        </p>
        <p>We make no guarantee that use of VYAS will result in any specific exam outcome, score improvement, or selection result.</p>
        <p>
          To the maximum extent permitted by applicable law, VYAS and its operators shall not be liable for any indirect,
          incidental, special, or consequential damages arising from your use of — or inability to use — the Platform.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>8. Termination</h2>
        <p>
          We reserve the right to suspend or permanently terminate any account that violates these Terms, engages in
          abusive behaviour, or compromises the integrity of the Platform — with or without prior notice.
        </p>
        <p>
          You may terminate your account at any time by contacting us. Upon termination, your data will be deleted
          in accordance with our{' '}
          <Link href="/privacy">Privacy Policy</Link>.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>9. Governing Law</h2>
        <p>
          These Terms shall be governed by and construed in accordance with the laws of India. Any disputes arising
          out of or relating to these Terms or your use of the Platform shall be subject to the exclusive jurisdiction
          of the courts of India.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>10. Changes to These Terms</h2>
        <p>
          We may update these Terms from time to time. Material changes will be indicated by an updated
          &quot;Last updated&quot; date at the top of this page. Continued use of VYAS after changes are posted constitutes
          your acceptance of the revised Terms.
        </p>
      </div>

      <hr className={styles.divider} />

      <div className={styles.infoCard}>
        <p>
          Questions about these Terms?{' '}
          <Link href="/contact">Contact us</Link> — we&apos;ll respond within 48 hours. Also see our{' '}
          <Link href="/privacy">Privacy Policy</Link> for information on how we handle your data.
        </p>
      </div>
    </StaticLayout>
  );
}
