/**
 * VYAS v0.6 — Navbar
 * FIX: Added VyasLogo before brand name; corrected CSS class references
 */

import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import VyasLogo from "./VyasLogo";
import styles from "../styles/Navbar.module.css";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate         = useNavigate();
  const location         = useLocation();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const isActive = path =>
    location.pathname === path ? styles.active : "";

  return (
    <nav className={styles.nav}>
      <Link to="/" className={styles.brand}>
        <VyasLogo variant="gold" size={30} />
        <span className={styles.brandName}>VYAS</span>
      </Link>

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
    </nav>
  );
}