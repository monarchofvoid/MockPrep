import { useState } from "react";
import Home from "./components/Home";
import TestEngine from "./components/TestEngine";
import ResultsDashboard from "./components/ResultsDashboard";
import { startAttempt } from "./api/client";
import "./styles/global.css";

// For demo purposes, use a fixed guest user ID.
// In production, replace with proper auth (JWT, OAuth, etc.)
const GUEST_USER_ID = 1;

const SCREENS = {
  HOME: "home",
  TEST: "test",
  RESULTS: "results",
};

export default function App() {
  const [screen, setScreen] = useState(SCREENS.HOME);
  const [session, setSession] = useState(null);   // { attemptId, questions, ... }
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSelectPaper = async (paper) => {
    setLoading(true);
    setError(null);
    try {
      const data = await startAttempt(GUEST_USER_ID, paper.id);
      setSession({
        attemptId: data.attempt_id,
        mockId: data.mock_id,
        questions: data.questions,
        durationMinutes: data.duration_minutes,
        totalMarks: data.total_marks,
      });
      setScreen(SCREENS.TEST);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResults = (resultsData) => {
    setResults(resultsData);
    setScreen(SCREENS.RESULTS);
  };

  const handleRestart = () => {
    setSession(null);
    setResults(null);
    setError(null);
    setScreen(SCREENS.HOME);
  };

  if (loading)
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", flexDirection: "column", gap: 12 }}>
        <div className="spinner" />
        <p style={{ color: "#6b7280" }}>Loading test session…</p>
      </div>
    );

  if (error)
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100vh", gap: 12 }}>
        <p style={{ color: "#dc2626" }}>⚠ {error}</p>
        <button onClick={handleRestart} style={{ padding: "8px 20px", cursor: "pointer" }}>
          Go back
        </button>
      </div>
    );

  if (screen === SCREENS.HOME)
    return <Home userId={GUEST_USER_ID} onSelectPaper={handleSelectPaper} />;

  if (screen === SCREENS.TEST && session)
    return (
      <TestEngine
        attemptId={session.attemptId}
        mockId={session.mockId}
        questions={session.questions}
        durationMinutes={session.durationMinutes}
        totalMarks={session.totalMarks}
        onResults={handleResults}
      />
    );

  if (screen === SCREENS.RESULTS && results)
    return <ResultsDashboard results={results} onRestart={handleRestart} />;

  return null;
}
