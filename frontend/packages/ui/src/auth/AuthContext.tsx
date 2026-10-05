import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import type { CurrentUser, PortalType } from "../api/types";
import { apiClient } from "../api/client";

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
