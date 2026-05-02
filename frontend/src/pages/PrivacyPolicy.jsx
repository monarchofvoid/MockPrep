import { Link } from "react-router-dom";
import StaticLayout from "../components/StaticLayout";
import styles from "../styles/StaticPage.module.css";

export default function PrivacyPolicy() {
  return (
    <StaticLayout>
      {/* ── Header ── */}
      <div className={styles.header}>
        <span className={styles.kicker}>Legal</span>
        <h1 className={styles.pageTitle}>Privacy Policy</h1>
        <p className={styles.pageMeta}>Last updated: June 2025</p>
        <p className={styles.pageLead}>
          VYAS is committed to handling your personal data responsibly.
          This policy explains exactly what we collect, why, and what rights
          you have over it.
        </p>
      </div>

      {/* ── Sections ── */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>What data we collect</h2>
        <p>When you create an account and use VYAS, we collect:</p>
        <ul>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Account data</strong>
            {" "}— your name and email address, provided at signup.
          </li>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Authentication data</strong>
            {" "}— your password, stored as a one-way bcrypt hash.
            We cannot read your password; it is irreversible.
          </li>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Attempt data</strong>
            {" "}— your answers, time spent per question, visit count, review flags,
            and scores for each mock test you submit.
          </li>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Contact messages</strong>
            {" "}— if you submit the contact form, we store your name, email,
            and message.
          </li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>What we do not collect</h2>
        <ul>
          <li>Payment information (VYAS is free)</li>
          <li>Device identifiers or IP addresses beyond standard server logs</li>
          <li>Location data</li>
          <li>Third-party tracking or advertising cookies</li>
          <li>Any data from outside the VYAS platform</li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>How we use your data</h2>
        <ul>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Authentication</strong>
            {" "}— to verify your identity and maintain your session via JWT tokens
            stored in your browser's localStorage.
          </li>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Platform functionality</strong>
            {" "}— to display your results, analytics dashboard, and performance history.
          </li>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Transactional email</strong>
            {" "}— to send password reset links and respond to contact form submissions.
            We do not send marketing email without your explicit consent.
          </li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Third-party services</h2>
        <p>
          VYAS uses the following third-party services to operate. Each is
          governed by its own privacy policy.
        </p>
        <ul>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Supabase</strong>
            {" "}— our database host (PostgreSQL on AWS ap-south-1). Your account
            and attempt data is stored here.
          </li>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Resend</strong>
            {" "}— our transactional email provider. Email addresses are shared
            with Resend only to deliver password reset and contact confirmation emails.
          </li>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Vercel</strong>
            {" "}— hosts our frontend. Standard request logs apply.
          </li>
          <li>
            <strong style={{ color: "var(--text-primary)" }}>Render / Railway</strong>
            {" "}— hosts our backend API. Standard server logs apply.
          </li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Data retention</h2>
        <p>
          We retain your account and attempt data for as long as your account
          is active. If you request account deletion, all associated data —
          including attempts, responses, and analytics — is permanently
          deleted within 7 days.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Cookies and local storage</h2>
        <p>
          VYAS stores your authentication token and user profile in
          browser <code>localStorage</code> to keep you signed in across sessions.
          No third-party cookies are set. No advertising trackers are used.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Your rights</h2>
        <p>You have the right to:</p>
        <ul>
          <li>Access the data we hold about you</li>
          <li>Request correction of inaccurate data</li>
          <li>Request deletion of your account and all associated data</li>
          <li>Object to processing of your data</li>
        </ul>
        <p>
          To exercise any of these rights, contact us at{" "}
          <a href="mailto:sinabhinav19@gmail.com">sinabhinav19@gmail.com</a>
          {" "}with the subject line "Data Request". We will respond within 7 days.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Changes to this policy</h2>
        <p>
          If we make material changes to how we handle your data, we will
          update this page and revise the "Last updated" date. Continued
          use of VYAS after changes are posted constitutes acceptance.
        </p>
      </div>

      <hr className={styles.divider} />

      <div className={styles.infoCard}>
        <p>
          Privacy concerns?{" "}
          <Link to="/contact">Contact us</Link> or email{" "}
          <a href="mailto:sinabhinav19@gmail.com">sinabhinav19@gmail.com</a>.
          We take data protection seriously and respond within 48 hours.
        </p>
      </div>
    </StaticLayout>
  );
}
