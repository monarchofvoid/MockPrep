/**
 * VYAS v0.6 — Navbar
 * FIX: Added mobile hamburger menu to prevent nav from overflowing
 * the viewport on small screens (< 640px). The full link row at
 * 320 px width overflowed the page, causing a wider-than-content
 * layout and horizontal scroll.
 */

import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import VyasLogo from "./VyasLogo";
import styles from "../styles/Navbar.module.css";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate         = useNavigate();
  const location         = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const handleLogout = () => {
    logout();
    setMenuOpen(false);
    navigate("/");
  };

  const isActive = path =>
    location.pathname === path ? styles.active : "";

  // Close menu on route change
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  // Close menu when clicking outside
  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  return (
    <nav className={styles.nav} ref={menuRef}>
      <Link to="/" className={styles.brand}>
        <VyasLogo variant="gold" size={30} />
        <span className={styles.brandName}>VYAS</span>
      </Link>

      {/* ── Desktop links (hidden on mobile) ─────────────────────── */}
      <div className={styles.links}>
        {user ? (
          <>
            <Link to="/dashboard" className={`${styles.navLink} ${isActive("/dashboard")}`}>
              Dashboard
            </Link>
            <Link to="/mocks" className={`${styles.navLink} ${isActive("/mocks")}`}>
              Papers
            </Link>
            <Link to="/ai-mock" className={`${styles.navLink} ${isActive("/ai-mock")}`}>
              AI Mock
            </Link>
            <Link to="/profile" className={`${styles.navLink} ${isActive("/profile")}`}>
              Profile
            </Link>
            <button onClick={handleLogout} className={styles.logoutBtn}>
              Sign Out
            </button>
          </>
        ) : (
          <>
            <Link to="/about"   className={styles.navLink}>About</Link>
            <Link to="/contact" className={styles.navLink}>Contact</Link>
            <button onClick={() => navigate("/")} className={styles.logoutBtn}>
              Sign In
            </button>
          </>
        )}
      </div>

      {/* ── Mobile hamburger button (shown only on mobile) ─────────── */}
      <button
        className={styles.hamburger}
        onClick={() => setMenuOpen((o) => !o)}
        aria-label={menuOpen ? "Close menu" : "Open menu"}
        aria-expanded={menuOpen}
      >
        <span className={`${styles.bar} ${menuOpen ? styles.barOpen1 : ""}`} />
        <span className={`${styles.bar} ${menuOpen ? styles.barOpen2 : ""}`} />
        <span className={`${styles.bar} ${menuOpen ? styles.barOpen3 : ""}`} />
      </button>

      {/* ── Mobile drawer ──────────────────────────────────────────── */}
      {menuOpen && (
        <div className={styles.mobileMenu}>
          {user ? (
            <>
              <Link to="/dashboard" className={`${styles.mobileLink} ${isActive("/dashboard")}`}>
                Dashboard
              </Link>
              <Link to="/mocks" className={`${styles.mobileLink} ${isActive("/mocks")}`}>
                Papers
              </Link>
              <Link to="/ai-mock" className={`${styles.mobileLink} ${isActive("/ai-mock")}`}>
                AI Mock
              </Link>
              <Link to="/profile" className={`${styles.mobileLink} ${isActive("/profile")}`}>
                Profile
              </Link>
              <button onClick={handleLogout} className={styles.mobileLogoutBtn}>
                Sign Out
              </button>
            </>
          ) : (
            <>
              <Link to="/about"   className={styles.mobileLink}>About</Link>
              <Link to="/contact" className={styles.mobileLink}>Contact</Link>
              <button onClick={() => { navigate("/"); setMenuOpen(false); }} className={styles.mobileLogoutBtn}>
                Sign In
              </button>
            </>
          )}
        </div>
      )}
    </nav>
  );
}