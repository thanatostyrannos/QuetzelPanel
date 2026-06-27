/**
 * useAuth — authentication state hook.
 *
 * Stores the JWT in localStorage and restores it on mount by calling /auth/me.
 * Clears the token if /me returns 401.
 */
import { useCallback, useEffect, useState } from "react";
import { api, setAuthToken } from "../api";
import type { User } from "../types";

const TOKEN_KEY = "quetzel_token";

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

export function useAuth(): AuthState {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount: restore session from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setLoading(false);
      return;
    }
    setAuthToken(stored);
    api
      .me()
      .then((me) => {
        setUser({
          id: me.userId,
          username: me.username,
          role: me.role as User["role"],
          customerId: me.customerId,
        });
      })
      .catch(() => {
        // Invalid / expired token — clear it
        localStorage.removeItem(TOKEN_KEY);
        setAuthToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const resp = await api.login(username, password);
    localStorage.setItem(TOKEN_KEY, resp.token);
    setAuthToken(resp.token);
    setUser(resp.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setAuthToken(null);
    setUser(null);
  }, []);

  return {
    user,
    isAuthenticated: user !== null,
    login,
    logout,
    loading,
  };
}
