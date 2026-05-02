/**
 * StaticLayout
 * Wraps all public static pages (About, Contact, Privacy, Terms) with
 * a consistent minimal nav and footer. No auth required.
 */
import { Link } from "react-router-dom";
import VyasLogo from "./VyasLogo";
import styles from "../styles/StaticPage.module.css";

const FOOTER_LINKS = [
  { to: "/about",   label: "About" },
  { to: "/contact", label: "Contact" },
  { to: "/privacy", label: "Privacy" },
  { to: "/terms",   label: "Terms" },
];

export default function StaticLayout({ children }) {
  return (
    <div className={styles.page}>
      {/* ── Minimal sticky nav ── */}
      <nav className={styles.nav}>
        <Link to="/" className={styles.navBrand}>
          <VyasLogo variant="gold" size={28} />
          <span className={styles.navBrandName}>VYAS</span>
        </Link>
        <Link to="/" className={styles.navBack}>
          ← Back to home
        </Link>
      </nav>

      {/* ── Page content ── */}
      <main className={styles.content}>
        {children}
      </main>

      {/* ── Footer ── */}
      <footer className={styles.footer}>
        <div className={styles.footerLeft}>
          <VyasLogo variant="gold" size={24} />
          <div>
            <span className={styles.footerBrand}>VYAS</span>
            <span style={{ margin: "0 6px", color: "var(--text-muted)", fontSize: 12 }}>·</span>
            <span className={styles.footerText}>Intelligence · Discipline · Ascent</span>
          </div>
        </div>
        <nav className={styles.footerLinks}>
          {FOOTER_LINKS.map(({ to, label }) => (
            <Link key={to} to={to} className={styles.footerLink}>{label}</Link>
          ))}
        </nav>
      </footer>
    </div>
  );
}
