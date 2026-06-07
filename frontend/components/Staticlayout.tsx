/**
 * VYAS v2.0 — StaticLayout (Premium Upgrade)
 * ============================================
 * Shared layout wrapper for About, Contact, Privacy, Terms.
 * Preserves all original functionality; upgrades visual presentation.
 */

import Link from 'next/link'
import VyasLogo from '@/components/VyasLogo'
import styles from '@/styles/StaticPage.module.css'

interface StaticLayoutProps {
  children: React.ReactNode
}

export default function StaticLayout({ children }: StaticLayoutProps) {
  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link href="/" className={styles.brand}>
            <VyasLogo variant="gold" size={32} />
            <span className={styles.brandName}>VYAS</span>
          </Link>
          <nav className={styles.headerNav} aria-label="Main navigation">
            <Link href="/about" className={styles.navLink}>About</Link>
            <Link href="/contact" className={styles.navLink}>Contact</Link>
            <Link href="/dashboard" className={styles.navCta}>Dashboard →</Link>
          </nav>
        </div>
      </header>

      {/* Page content */}
      <main className={styles.main}>
        <div className={styles.mainInner}>
          {children}
        </div>
      </main>

      {/* Footer */}
      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div className={styles.footerBrandRow}>
            <VyasLogo variant="gold" size={26} />
            <span className={styles.footerBrandName}>VYAS</span>
            <span className={styles.footerVersion}>v2.0</span>
          </div>
          <nav className={styles.footerLinks} aria-label="Footer navigation">
            <Link href="/" className={styles.footerLink}>Home</Link>
            <Link href="/about" className={styles.footerLink}>About</Link>
            <Link href="/contact" className={styles.footerLink}>Contact</Link>
            <Link href="/privacy" className={styles.footerLink}>Privacy</Link>
            <Link href="/terms" className={styles.footerLink}>Terms</Link>
          </nav>
          <p className={styles.footerCopyright}>
            © {new Date().getFullYear()} VYAS · All rights reserved
          </p>
        </div>
      </footer>
    </div>
  )
}
