import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import type { CurrentUser, PortalType } from "../api/types";
import { apiClient } from "../api/client";
import { ApiError } from "../api/errors";

export interface AuthContextValue {
  user: CurrentUser | null;
  portal: PortalType;
  isLoading: boolean;
  error: string | null;
  setUser: (user: CurrentUser | null) => void;
  fetchMe: () => Promise<CurrentUser | null>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export interface AuthProviderProps {
  portal: PortalType;
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ portal, children }) => {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMe = useCallback(async (): Promise<CurrentUser | null> => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<CurrentUser>(`/api/v1/auth/${portal}/me`);
      setUser(data);
      return data;
    } catch {
      setUser(null);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [portal]);

  const logout = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      await apiClient.post(`/api/v1/auth/${portal}/logout`);
    } catch {
      // ignore logout errors, proceed to clear local user state
    } finally {
      setUser(null);
      setIsLoading(false);
    }
  }, [portal]);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    let running = false;
    const refreshPermissions = async () => {
      if (running || document.visibilityState === "hidden") return;
      running = true;
      try {
        const updated = await apiClient.get<CurrentUser>(`/api/v1/auth/${portal}/me`);
        if (active) setUser(updated);
      } catch (err) {
        if (active && err instanceof ApiError && (err.status === 401 || err.status === 403)) setUser(null);
      } finally {
        running = false;
      }
    };
    const onVisible = () => { if (document.visibilityState === "visible") void refreshPermissions(); };
    window.addEventListener("focus", refreshPermissions);
    document.addEventListener("visibilitychange", onVisible);
    const timer = setInterval(refreshPermissions, 60_000);
    return () => {
      active = false;
      clearInterval(timer);
      window.removeEventListener("focus", refreshPermissions);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [portal, user?.id]);

  return (
    <AuthContext.Provider
      value={{
        user,
        portal,
        isLoading,
        error,
        setUser,
        fetchMe,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
