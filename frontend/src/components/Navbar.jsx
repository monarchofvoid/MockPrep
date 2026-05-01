import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import VyasLogo from "./VyasLogo";
import styles from "../styles/Navbar.module.css";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const initials = user?.name
    ?.split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "V";

  return (
    <nav className={`${styles.nav} ${scrolled ? styles.scrolled : ""}`}>
      <button className={styles.brand} onClick={() => navigate("/dashboard")}>
        <VyasLogo variant="gold" size={28} />
        <span className={styles.brandName}>VYAS</span>
      </button>

      {user && (
        <div className={styles.right}>
          <div className={styles.links}>
            <NavLink className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ""}`} to="/dashboard">
              Dashboard
            </NavLink>
            <NavLink className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ""}`} to="/mocks">
              Papers
            </NavLink>
          </div>
          <div className={styles.userBlock}>
            <span className={styles.avatar}>{initials}</span>
            <span className={styles.greeting}>{user.name.split(" ")[0]}</span>
          </div>
          <button className={styles.logoutBtn} onClick={handleLogout}>
            Sign out
          </button>
        </div>
      )}
    </nav>
  );
}
