import { googleLogout } from "@react-oauth/google";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

/** Minimal token response we store after Google login (implicit flow). */
export interface AuthUser {
  access_token: string;
  expires_in: number;
}

const AUTH_STORAGE_KEY = "lumos_google_auth";

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  setUser: (user: AuthUser | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadStoredUser(): AuthUser | null {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as AuthUser;
    if (data?.access_token) return data;
  } catch {
    /* ignore */
  }
  return null;
}

function saveUser(user: AuthUser | null) {
  if (user) {
    sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
  } else {
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<AuthUser | null>(loadStoredUser);

  const setUser = useCallback((next: AuthUser | null) => {
    setUserState(next);
    saveUser(next);
  }, []);

  const logout = useCallback(() => {
    setUserState(null);
    saveUser(null);
    googleLogout();
  }, []);

  useEffect(() => {
    // Re-hydrate from storage in case of new tab or refresh
    setUserState(loadStoredUser());
  }, []);

  const value: AuthContextValue = {
    user,
    isAuthenticated: !!user,
    setUser,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
