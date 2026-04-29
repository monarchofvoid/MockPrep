import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import LandingPage from "./pages/LandingPage";
import Dashboard from "./pages/Dashboard";
import MockBrowser from "./pages/MockBrowser";
import TestPage from "./pages/TestPage";
import ResultsPage from "./pages/ResultsPage";
import "./styles/global.css";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/" element={<LandingPage />} />

          {/* Protected */}
          <Route
            path="/dashboard"
            element={<ProtectedRoute><Dashboard /></ProtectedRoute>}
          />
          <Route
            path="/mocks"
            element={<ProtectedRoute><MockBrowser /></ProtectedRoute>}
          />
          <Route
            path="/test/:attemptId"
            element={<ProtectedRoute><TestPage /></ProtectedRoute>}
          />
          <Route
            path="/results/:attemptId"
            element={<ProtectedRoute><ResultsPage /></ProtectedRoute>}
          />

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
