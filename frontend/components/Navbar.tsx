/**
 * VYAS v2.0 — Navbar (Updated)
 * =============================
 * Changes from original:
 *   - Wallet balance chip: shows current credit balance next to user links
 *   - "Buy Credits" link visible when balance is low (low_credit_warning=true)
 *     or always visible in the mobile drawer
 *   - /wallet and /purchase routes added to nav and mobile menu
 *   - Low credit warning badge on the wallet chip
 *
 * All original structure, styling refs, and mobile hamburger logic preserved.
 */

'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import { useAuthStore } from '@/stores/authStore'
import VyasLogo from '@/components/VyasLogo'
import styles from '@/styles/Navbar.module.css'

export default function Navbar() {
  const { user, logout, walletBalanceCredits, lowCreditWarning } = useAuthStore()
  const router = useRouter()
  const pathname = usePathname()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLElement>(null)

  const handleLogout = async () => {
    await logout()
    setMenuOpen(false)
    router.push('/')
  }

  const isActive = (path: string) => (pathname === path ? styles.active : '')

  // Close menu on route change
  useEffect(() => {
    setMenuOpen(false)
  }, [pathname])

  // Close menu when clicking outside
  useEffect(() => {
    if (!menuOpen) return
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [menuOpen])

  return (
    <nav className={styles.nav} ref={menuRef}>
      <Link href="/" className={styles.brand}>
        <VyasLogo variant="gold" size={30} />
        <span className={styles.brandName}>VYAS</span>
      </Link>

      {/* ── Desktop links ──────────────────────────────────────────── */}
      <div className={styles.links}>
        {user ? (
          <>
            <Link href="/dashboard" className={`${styles.navLink} ${isActive('/dashboard')}`}>
              Dashboard
            </Link>
            <Link href="/mocks" className={`${styles.navLink} ${isActive('/mocks')}`}>
              Papers
            </Link>
            <Link href="/ai-mock" className={`${styles.navLink} ${isActive('/ai-mock')}`}>
              AI Mock
            </Link>
            <Link href="/profile" className={`${styles.navLink} ${isActive('/profile')}`}>
              Profile
            </Link>

            {/* Wallet balance chip — always visible when logged in */}
            <Link
              href="/wallet"
              className={`${styles.walletChip} ${lowCreditWarning ? styles.walletChipLow : ''}`}
              title={lowCreditWarning ? 'Low credits — click to top up' : 'View wallet'}
            >
              {lowCreditWarning && <span className={styles.walletWarnDot} />}
              <span className={styles.walletIcon}>⬡</span>
              <span className={styles.walletBalance}>
                {walletBalanceCredits.toFixed(1)}
              </span>
            </Link>

            {/* Buy credits — always visible, highlighted when low */}
            <Link
              href="/purchase"
              className={`${styles.buyCreditsBtn} ${lowCreditWarning ? styles.buyCreditsUrgent : ''}`}
            >
              + Credits
            </Link>

            <button onClick={handleLogout} className={styles.logoutBtn}>
              Sign Out
            </button>
          </>
        ) : (
          <>
            <Link href="/about" className={styles.navLink}>
              About
            </Link>
            <Link href="/contact" className={styles.navLink}>
              Contact
            </Link>
            <button onClick={() => router.push('/')} className={styles.logoutBtn}>
              Sign In
            </button>
          </>
        )}
      </div>

      {/* ── Mobile hamburger button ─────────────────────────────────── */}
      <button
        className={styles.hamburger}
        onClick={() => setMenuOpen((o) => !o)}
        aria-label={menuOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={menuOpen}
      >
        <span className={`${styles.bar} ${menuOpen ? styles.barOpen1 : ''}`} />
        <span className={`${styles.bar} ${menuOpen ? styles.barOpen2 : ''}`} />
        <span className={`${styles.bar} ${menuOpen ? styles.barOpen3 : ''}`} />
      </button>

      {/* ── Mobile drawer ───────────────────────────────────────────── */}
      {menuOpen && (
        <div className={styles.mobileMenu}>
          {user ? (
            <>
              <Link href="/dashboard" className={`${styles.mobileLink} ${isActive('/dashboard')}`}>
                Dashboard
              </Link>
              <Link href="/mocks" className={`${styles.mobileLink} ${isActive('/mocks')}`}>
                Papers
              </Link>
              <Link href="/ai-mock" className={`${styles.mobileLink} ${isActive('/ai-mock')}`}>
                AI Mock
              </Link>
              <Link href="/profile" className={`${styles.mobileLink} ${isActive('/profile')}`}>
                Profile
              </Link>
              <Link href="/wallet" className={`${styles.mobileLink} ${isActive('/wallet')}`}>
                Wallet
                {user.wallet && (
                  <span className={styles.mobileCreditCount}>
                    {' '}({walletBalanceCredits.toFixed(1)} cr)
                  </span>
                )}
              </Link>
              <Link href="/purchase" className={styles.mobileBuyLink}>
                Buy Credits
              </Link>
              <button onClick={handleLogout} className={styles.mobileLogoutBtn}>
                Sign Out
              </button>
            </>
          ) : (
            <>
              <Link href="/about" className={styles.mobileLink}>
                About
              </Link>
              <Link href="/contact" className={styles.mobileLink}>
                Contact
              </Link>
              <button
                onClick={() => {
                  router.push('/')
                  setMenuOpen(false)
                }}
                className={styles.mobileLogoutBtn}
              >
                Sign In
              </button>
            </>
          )}
        </div>
      )}
    </nav>
  )
}