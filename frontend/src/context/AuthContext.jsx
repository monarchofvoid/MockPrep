import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { getStoredUser, getToken, saveAuth, clearAuth } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true); // true while hydrating from localStorage

  // Hydrate auth state from localStorage on first render
  useEffect(() => {
    const storedUser  = getStoredUser();
    const storedToken = getToken();
    if (storedUser && storedToken) {
      setUser(storedUser);
    }
    setLoading(false);
  }, []);

  const login = useCallback((authPayload) => {
    // authPayload = { access_token, token_type, user }
    saveAuth(authPayload);
    setUser(authPayload.user);
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
