/**
 * VYAS v2.0 — ProtectedRoute
 * ============================
 * v2.0 changes:
 *   - Waits for sessionChecked before rendering or redirecting.
 *     (Previously used `loading` which could cause a flash-of-redirect
 *      while the silent /auth/refresh was still in-flight.)
 *   - Shows a minimal spinner during session restoration.
 *   - After session confirmed, redirects unauthenticated users to /
 *     with the attempted path preserved for post-login redirect.
 */

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute() {
  const { user, sessionChecked } = useAuth();
  const location = useLocation();

  // Wait for silent refresh to complete before deciding
  if (!sessionChecked) {
    return (
      <div style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--surface-0)",
      }}>
        <div style={{
          width: 40,
          height: 40,
          border: "3px solid rgba(212,168,67,0.2)",
          borderTop: "3px solid var(--vyas-gold)",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!user) {
    // Preserve the attempted path so we can redirect back after login
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
