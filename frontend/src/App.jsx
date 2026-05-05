/**
 * VYAS v0.6 — App Router
 *
 * Changes vs v0.5:
 *   - Added /profile route → ProfilePage (Feature 1 / D2)
 *   - LandingPage replaced with redesigned version (Feature 3)
 *
 * FIX v0.6.1:
 *   - Removed erroneous <Route element={<StaticLayout />}> layout wrapper.
 *     About, Contact, PrivacyPolicy, and Terms already self-wrap in
 *     <StaticLayout children={...}> — nesting them inside a layout route
 *     caused StaticLayout to render with no children (undefined), producing
 *     a double-wrapped and ultimately blank static page area.
 *   - ForgotPassword and ResetPassword have their own standalone layout
 *     (VyasLogo-based) — they were also incorrectly grouped inside the
 *     StaticLayout route, which would have hidden their content.
 *   - ProtectedRoute now correctly uses <Outlet /> (see that file).
 */

import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";

import ProtectedRoute   from "./components/ProtectedRoute";

// Pages
import LandingPage      from "./pages/LandingPage";
import Dashboard        from "./pages/Dashboard";
import MockBrowser      from "./pages/MockBrowser";
import TestPage         from "./pages/TestPage";
import ResultsPage      from "./pages/ResultsPage";
import AIMockGeneratorPage from "./pages/AIMockGeneratorPage";
import ProfilePage      from "./pages/ProfilePage";

// Static / Auth pages  (each self-wraps in its own layout)
import About            from "./pages/About";
import Contact          from "./pages/Contact";
import PrivacyPolicy    from "./pages/PrivacyPolicy";
import Terms            from "./pages/Terms";
import ForgotPassword   from "./pages/ForgotPassword";
import ResetPassword    from "./pages/ResetPassword";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>

          {/* ── Public ─────────────────────────────────────────────────── */}
          <Route path="/"               element={<LandingPage />} />

          {/* ── Static pages — each self-wraps in <StaticLayout> ────────── */}
          <Route path="/about"           element={<About />} />
          <Route path="/contact"         element={<Contact />} />
          <Route path="/privacy"         element={<PrivacyPolicy />} />
          <Route path="/terms"           element={<Terms />} />

          {/* ── Auth pages — own standalone layout (VyasLogo) ───────────── */}
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password"  element={<ResetPassword />} />

          {/* ── Protected — require auth ────────────────────────────────── */}
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard"   element={<Dashboard />} />
            <Route path="/mocks"       element={<MockBrowser />} />
            <Route path="/test/:id"    element={<TestPage />} />
            <Route path="/results/:id" element={<ResultsPage />} />
            <Route path="/ai-mock"     element={<AIMockGeneratorPage />} />
            <Route path="/profile"     element={<ProfilePage />} />
          </Route>

          {/* ── 404 fallback ─────────────────────────────────────────────── */}
          <Route path="*" element={
            <div style={{
              display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center",
              minHeight: "100vh", gap: "1rem",
              background: "#080b12", color: "#e8ecf4",
            }}>
              <h1 style={{ fontSize: "4rem", margin: 0 }}>404</h1>
              <p style={{ color: "#8b95a8" }}>Page not found.</p>
              <a href="/" style={{ color: "#f5c842" }}>Go Home →</a>
            </div>
          } />

        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
