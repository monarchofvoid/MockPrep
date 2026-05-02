import { Link } from "react-router-dom";
import StaticLayout from "../components/StaticLayout";
import styles from "../styles/StaticPage.module.css";

export default function Terms() {
  return (
    <StaticLayout>
      {/* ── Header ── */}
      <div className={styles.header}>
        <span className={styles.kicker}>Legal</span>
        <h1 className={styles.pageTitle}>Terms &amp; Conditions</h1>
        <p className={styles.pageMeta}>Last updated: June 2025</p>
        <p className={styles.pageLead}>
          By creating an account or using VYAS, you agree to these terms.
          Please read them carefully — they are written plainly, not in legalese.
        </p>
      </div>

      {/* ── Sections ── */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>1. Acceptance of terms</h2>
        <p>
          Access to and use of VYAS (the "Platform") is conditional on your
          acceptance of and compliance with these Terms &amp; Conditions ("Terms").
          These Terms apply to all visitors, users, and anyone else who accesses
          or uses the Platform.
        </p>
        <p>
          If you disagree with any part of these Terms, you do not have
          permission to access the Platform.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>2. Your account</h2>
        <ul>
          <li>
            You must provide accurate, complete information when creating
            an account and keep it up to date.
          </li>
          <li>
            You are responsible for maintaining the confidentiality of your
            password and for all activity that occurs under your account.
          </li>
          <li>
            You must be at least 13 years of age to create an account.
          </li>
          <li>
            One account per person. Creating multiple accounts to circumvent
            restrictions or misrepresent performance is prohibited.
          </li>
          <li>
            Notify us immediately if you believe your account has been
            compromised.
          </li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>3. Acceptable use</h2>
        <p>You agree not to:</p>
        <ul>
          <li>
            Use the Platform for any unlawful purpose or in violation of
            any applicable local, national, or international law.
          </li>
          <li>
            Attempt to gain unauthorised access to any part of the Platform,
            its servers, or any system or network connected to it.
          </li>
          <li>
            Reverse-engineer, decompile, disassemble, scrape, or otherwise
            attempt to derive the source code or underlying data of the Platform.
          </li>
          <li>
            Use automated scripts, bots, or crawlers to interact with the
            Platform without prior written permission.
          </li>
          <li>
            Attempt to access, alter, or delete another user's data or account.
          </li>
          <li>
            Submit false, misleading, or malicious content through any
            Platform feature including the contact form.
          </li>
        </ul>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>4. Intellectual property</h2>
        <p>
          The VYAS name, logo, interface design, and any original software
          are the intellectual property of the Platform's operators and are
          protected by applicable copyright and trademark law.
        </p>
        <p>
          Questions and past paper content are sourced from publicly available
          materials published by their respective conducting bodies (such as
          NTA and IITs). VYAS does not claim ownership over such content and
          uses it solely for educational and practice purposes.
        </p>
        <p>
          You may not reproduce, distribute, or create derivative works from
          VYAS's original content without written permission.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>5. Platform rights and availability</h2>
        <p>
          We reserve the right to modify, suspend, or discontinue the
          Platform — or any part of it — at any time, with or without notice.
        </p>
        <p>
          We may add, remove, or change features, question banks, or access
          tiers at our discretion. We are not liable to you or any third
          party for any such modification or interruption.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>6. Limitation of liability</h2>
        <p>
          VYAS is provided "as is" and "as available" without warranty of
          any kind, express or implied. We do not guarantee that the Platform
          will be uninterrupted, error-free, or that the content is accurate
          or complete at all times.
        </p>
        <p>
          We make no guarantee that use of VYAS will result in any specific
          exam outcome, score improvement, or selection result.
        </p>
        <p>
          To the maximum extent permitted by applicable law, VYAS and its
          operators shall not be liable for any indirect, incidental, special,
          or consequential damages arising from your use of — or inability
          to use — the Platform.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>7. Termination</h2>
        <p>
          We reserve the right to suspend or permanently terminate any
          account that violates these Terms, engages in abusive behaviour,
          or compromises the integrity of the Platform — with or without
          prior notice.
        </p>
        <p>
          You may terminate your account at any time by contacting us.
          Upon termination, your data will be deleted in accordance with
          our <Link to="/privacy">Privacy Policy</Link>.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>8. Governing law</h2>
        <p>
          These Terms shall be governed by and construed in accordance with
          the laws of India. Any disputes arising out of or relating to
          these Terms or your use of the Platform shall be subject to the
          exclusive jurisdiction of the courts of India.
        </p>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>9. Changes to these terms</h2>
        <p>
          We may update these Terms from time to time. Material changes will
          be indicated by an updated "Last updated" date at the top of this page.
          Continued use of VYAS after changes are posted constitutes your
          acceptance of the revised Terms.
        </p>
      </div>

      <hr className={styles.divider} />

      <div className={styles.infoCard}>
        <p>
          Questions about these Terms?{" "}
          <Link to="/contact">Contact us</Link> — we'll respond within
          48 hours. Also see our{" "}
          <Link to="/privacy">Privacy Policy</Link> for information on
          how we handle your data.
        </p>
      </div>
    </StaticLayout>
  );
}
