import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";

// Public auth
import LandingPage      from "./pages/LandingPage";
import ForgotPassword   from "./pages/ForgotPassword";
import ResetPassword    from "./pages/ResetPassword";

// Static / info pages
import About            from "./pages/About";
import Contact          from "./pages/Contact";
import PrivacyPolicy    from "./pages/PrivacyPolicy";
import Terms            from "./pages/Terms";

// Protected
import Dashboard        from "./pages/Dashboard";
import MockBrowser      from "./pages/MockBrowser";
import TestPage         from "./pages/TestPage";
import ResultsPage      from "./pages/ResultsPage";
import AIMockGeneratorPage from "./pages/AIMockGeneratorPage";   // Phase 2B

import "./styles/global.css";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>

          {/* ── Public ──────────────────────────────────────────────────── */}
          <Route path="/"                element={<LandingPage />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password"  element={<ResetPassword />} />

          {/* ── Info / legal ─────────────────────────────────────────────── */}
          <Route path="/about"           element={<About />} />
          <Route path="/contact"         element={<Contact />} />
          <Route path="/privacy"         element={<PrivacyPolicy />} />
          <Route path="/terms"           element={<Terms />} />

          {/* ── Protected ────────────────────────────────────────────────── */}
          <Route path="/dashboard"   element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/mocks"       element={<ProtectedRoute><MockBrowser /></ProtectedRoute>} />
          <Route path="/ai-mock"     element={<ProtectedRoute><AIMockGeneratorPage /></ProtectedRoute>} />
          <Route path="/test/:attemptId"    element={<ProtectedRoute><TestPage /></ProtectedRoute>} />
          <Route path="/results/:attemptId" element={<ProtectedRoute><ResultsPage /></ProtectedRoute>} />

          {/* ── Catch-all ────────────────────────────────────────────────── */}
          <Route path="*" element={<Navigate to="/" replace />} />

        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}