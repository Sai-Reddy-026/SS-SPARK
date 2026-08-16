/**
 * src/lib/auth.ts
 *
 * Authentication context, hooks, and token management.
 * Provides useAuth() hook and AuthProvider component.
 */

import React, { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { API_BASE } from "./api";

// -------------------------------------------------------------------------- //
// Types
// -------------------------------------------------------------------------- //

export interface User {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string;
  role: "user" | "admin";
  status: "active" | "suspended" | "pending_verification";
  email_verified: boolean;
  provider: "local" | "google" | "github";
  created_at: string;
  total_documents: number;
  total_questions: number;
  storage_used_mb: number;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isGuest: boolean;
}

export interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  setTokens: (tokens: AuthTokens, user: User) => void;
  setGuest: () => void;
  refreshUser: () => Promise<void>;
  clearAuth: () => void;
}

// -------------------------------------------------------------------------- //
// Storage keys
// -------------------------------------------------------------------------- //

const STORAGE_KEYS = {
  ACCESS_TOKEN: "ss_spark_access_token",
  REFRESH_TOKEN: "ss_spark_refresh_token",
  USER: "ss_spark_user",
  GUEST: "ss_spark_guest",
  LEGACY_ACCESS_TOKEN: "pg_access_token",
  LEGACY_REFRESH_TOKEN: "pg_refresh_token",
  LEGACY_USER: "pg_user",
} as const;

// -------------------------------------------------------------------------- //
// Token helpers
// -------------------------------------------------------------------------- //

export function getStoredAccessToken(): string | null {
  try {
    return (
      localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN) ??
      localStorage.getItem(STORAGE_KEYS.LEGACY_ACCESS_TOKEN)
    );
  } catch {
    return null;
  }
}

export function getStoredRefreshToken(): string | null {
  try {
    return (
      localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN) ??
      localStorage.getItem(STORAGE_KEYS.LEGACY_REFRESH_TOKEN)
    );
  } catch {
    return null;
  }
}

export function setStoredTokens(access: string, refresh: string, user?: User): void {
  try {
    localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, access);
    localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refresh);
    if (user) {
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));
    }
    localStorage.removeItem(STORAGE_KEYS.GUEST);
  } catch {
    // Silently fail in restricted environments
  }
}

export function clearStoredAuth(): void {
  try {
    Object.values(STORAGE_KEYS).forEach((k) => localStorage.removeItem(k));
  } catch {
    // Silently fail
  }
}

export function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split(".");
    if (parts.length < 2 || !parts[1]) return true;
    const decoded = JSON.parse(atob(parts[1]));
    // Check expiry with 30s buffer
    return decoded.exp * 1000 < Date.now() + 30_000;
  } catch {
    return true;
  }
}

export function getTokenRole(token: string): "user" | "admin" | null {
  try {
    const parts = token.split(".");
    if (parts.length < 2 || !parts[1]) return null;
    const decoded = JSON.parse(atob(parts[1]));
    return decoded.role ?? null;
  } catch {
    return null;
  }
}

// -------------------------------------------------------------------------- //
// Context
// -------------------------------------------------------------------------- //

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth() must be used inside <AuthProvider>");
  }
  return ctx;
}

// -------------------------------------------------------------------------- //
// Provider
// -------------------------------------------------------------------------- //

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tokens, setTokensState] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGuest, setIsGuestState] = useState(false);

  // ---- Initialise from local storage ----
  useEffect(() => {
    const initAuth = async () => {
      const access = getStoredAccessToken();
      const refresh = getStoredRefreshToken();
      const guestMode = localStorage.getItem(STORAGE_KEYS.GUEST) === "true";

      // Hydrate cached user immediately to prevent unauthenticated UI flicker
      const cachedUserStr = localStorage.getItem(STORAGE_KEYS.USER);
      if (cachedUserStr) {
        try {
          const cachedUser = JSON.parse(cachedUserStr);
          setUser(cachedUser);
          if (access && refresh) {
            setTokensState({ access_token: access, refresh_token: refresh });
          }
        } catch {
          // Bad JSON format — ignore
        }
      }

      if (guestMode && !access) {
        setIsGuestState(true);
        setIsLoading(false);
        return;
      }

      if (!access || !refresh) {
        setIsLoading(false);
        return;
      }

      // Try refresh if access token is expired
      let validAccess = access;
      if (isTokenExpired(access)) {
        try {
          const response = await fetch(`${API_BASE}/api/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refresh }),
          });
          if (response.ok) {
            const data = await response.json();
            validAccess = data.data.access_token;
            localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, validAccess);
          } else {
            clearStoredAuth();
            setUser(null);
            setTokensState(null);
            setIsLoading(false);
            return;
          }
        } catch {
          // Network error during refresh — keep stored tokens/cached user for offline mode
          setIsLoading(false);
          return;
        }
      }

      // Fetch fresh user profile from backend
      try {
        const response = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${validAccess}` },
        });
        if (response.ok) {
          const data = await response.json();
          setUser(data.data);
          localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(data.data));
          setTokensState({ access_token: validAccess, refresh_token: refresh });
        } else if (response.status === 401 || response.status === 403) {
          clearStoredAuth();
          setUser(null);
          setTokensState(null);
        }
      } catch {
        // Network error — preserve cached user state and tokens for resilience
      }

      setIsLoading(false);
    };

    initAuth();
  }, []);

  // ---- Actions ----

  const setTokens = (newTokens: AuthTokens, newUser: User) => {
    setStoredTokens(newTokens.access_token, newTokens.refresh_token, newUser);
    setTokensState(newTokens);
    setUser(newUser);
    setIsGuestState(false);
  };

  const login = async (email: string, password: string) => {
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Login failed.");
    }
    setTokens(
      { access_token: data.data.access_token, refresh_token: data.data.refresh_token },
      data.data,
    );
  };

  const register = async (email: string, password: string, fullName?: string) => {
    const response = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name: fullName ?? "" }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Registration failed.");
    }
    setTokens(
      { access_token: data.data.access_token, refresh_token: data.data.refresh_token },
      data.data,
    );
  };

  const logout = async () => {
    const access = getStoredAccessToken();
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        headers: access ? { Authorization: `Bearer ${access}` } : {},
      });
    } catch {
      // Ignore network errors on logout
    }
    clearStoredAuth();
    setUser(null);
    setTokensState(null);
    setIsGuestState(false);
  };

  const setGuest = () => {
    localStorage.setItem(STORAGE_KEYS.GUEST, "true");
    setIsGuestState(true);
    setUser(null);
    setTokensState(null);
  };

  const clearAuth = () => {
    clearStoredAuth();
    setUser(null);
    setTokensState(null);
    setIsGuestState(false);
  };

  const refreshUser = async () => {
    const access = tokens?.access_token ?? getStoredAccessToken();
    if (!access) return;
    try {
      const response = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${access}` },
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data.data);
      }
    } catch {
      // Silent
    }
  };

  const value: AuthContextValue = {
    user,
    tokens,
    isLoading,
    isAuthenticated: !!user,
    isAdmin: user?.role === "admin",
    isGuest,
    login,
    register,
    logout,
    setTokens,
    setGuest,
    refreshUser,
    clearAuth,
  };

  return React.createElement(AuthContext.Provider, { value }, children);
}
