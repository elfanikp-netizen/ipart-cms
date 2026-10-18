import { createContext, useCallback, useContext, useState } from "react";
import type { ReactNode } from "react";
import type { User } from "./types";
import { login as apiLogin, setAuthToken } from "./api";

interface AuthState {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({ user: null, login: async () => {}, logout: () => {} });

const LS_TOKEN = "scraper_token";
const LS_USER = "scraper_user";

// Attach a persisted token immediately at module load — before any page's
// first fetch — so API calls never race ahead of the Authorization header.
setAuthToken(localStorage.getItem(LS_TOKEN));

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const raw = localStorage.getItem(LS_USER);
      return raw ? (JSON.parse(raw) as User) : null;
    } catch {
      return null;
    }
  });

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiLogin(username, password);
    localStorage.setItem(LS_TOKEN, res.token);
    localStorage.setItem(LS_USER, JSON.stringify(res.user));
    setAuthToken(res.token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_USER);
    setAuthToken(null);
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
