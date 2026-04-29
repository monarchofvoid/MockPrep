import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import styles from "../styles/Navbar.module.css";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  return (
    <nav className={styles.nav}>
      <button className={styles.brand} onClick={() => navigate("/dashboard")}>
        <span className={styles.logo}>VY</span>
        <span className={styles.brandName}>VYAS</span>
      </button>
      {user && (
        <div className={styles.right}>
          <span className={styles.greeting}>Hello, {user.name.split(" ")[0]}</span>
          <button className={styles.logoutBtn} onClick={handleLogout}>
            Sign out
          </button>
        </div>
      )}
    </nav>
  );
}
