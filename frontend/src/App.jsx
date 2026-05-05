/**
 * VYAS v0.6 — App Router
 *
 * FIX (Bug): Route params for /test and /results were named ":id" but
 * TestPage and ResultsPage both destructure `{ attemptId }` from useParams().
 * Mismatch caused attemptId === undefined → URL "/results/undefined"
 * → parseInt("undefined") = NaN → GET /results/NaN → 422 → "[object Object]".
 *
 * Fix: renamed ":id" → ":attemptId" on both routes so useParams()
 * returns the correct key.
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
            <Route path="/dashboard"          element={<Dashboard />} />
            <Route path="/mocks"              element={<MockBrowser />} />
            {/* FIX: was ":id" — useParams() key must match component destructure */}
            <Route path="/test/:attemptId"    element={<TestPage />} />
            <Route path="/results/:attemptId" element={<ResultsPage />} />
            <Route path="/ai-mock"            element={<AIMockGeneratorPage />} />
            <Route path="/profile"            element={<ProfilePage />} />
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