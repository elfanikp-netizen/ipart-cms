import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { User } from "./types";
import { login as apiLogin, setAuthToken, setOnUnauthorized } from "./api";

interface AuthState {
  user: User | null;
  login: (username: string, password: string, remember?: boolean) => Promise<void>;
  logout: (expired?: boolean) => void;
}

const AuthContext = createContext<AuthState>({ user: null, login: async () => {}, logout: () => {} });

const LS_TOKEN = "scraper_token";
const LS_USER = "scraper_user";
const LS_EXPIRED = "scraper_expired";

// Attach a persisted token immediately at module load — before any page's
// first fetch — so API calls never race ahead of the Authorization header.
setAuthToken(localStorage.getItem(LS_TOKEN));

function tokenExpired(token: string | null): boolean {
  if (!token) return true;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const token = localStorage.getItem(LS_TOKEN);
    // if the persisted token is already expired, don't restore a dead session
    if (tokenExpired(token)) {
      localStorage.removeItem(LS_TOKEN);
      localStorage.removeItem(LS_USER);
      localStorage.setItem(LS_EXPIRED, "1");
      setAuthToken(null);
      return null;
    }
    try {
      const raw = localStorage.getItem(LS_USER);
      return raw ? (JSON.parse(raw) as User) : null;
    } catch {
      return null;
    }
  });

  const logout = useCallback((expired = false) => {
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_USER);
    if (expired) localStorage.setItem(LS_EXPIRED, "1");
    setAuthToken(null);
    setUser(null);
  }, []);

  // token rejected by the API (expired/invalid) -> auto logout to /login
  useEffect(() => {
    setOnUnauthorized(() => logout(true));
    return () => setOnUnauthorized(null);
  }, [logout]);

  // proactively log out when the token's exp passes while the app is open
  useEffect(() => {
    if (!user) return;
    const t = setInterval(() => {
      if (tokenExpired(localStorage.getItem(LS_TOKEN))) logout(true);
    }, 30_000);
    return () => clearInterval(t);
  }, [user, logout]);

  const login = useCallback(async (username: string, password: string, remember = false) => {
    const res = await apiLogin(username, password, remember);
    localStorage.setItem(LS_TOKEN, res.token);
    localStorage.setItem(LS_USER, JSON.stringify(res.user));
    localStorage.removeItem(LS_EXPIRED);
    setAuthToken(res.token);
    setUser(res.user);
  }, []);

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
