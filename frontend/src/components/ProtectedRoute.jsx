/**
 * ProtectedRoute — guards all authenticated routes.
 *
 * FIX v0.6.1: Replaced `return children` with `return <Outlet />`.
 *
 * In React Router v6, when a component is used as a *layout route*
 * (i.e. <Route element={<ProtectedRoute />}> with nested child routes),
 * the framework renders child routes through the <Outlet /> component —
 * NOT through `props.children`. `children` is always `undefined` in this
 * pattern, so the original code silently returned nothing, making every
 * protected page appear as a blank screen.
 */

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        height: "100vh", flexDirection: "column", gap: 12,
      }}>
        <div className="spinner" />
        <p style={{ color: "#6b7280", fontSize: 14 }}>Authenticating…</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  // Renders whichever child route matched (Dashboard, MockBrowser, etc.)
  return <Outlet />;
}
