import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { authApi } from '../api/client';

export type Role = 'admin' | 'faculty' | 'student';

export interface User {
  user_id: number;
  full_name: string;
  email?: string;
  role: Role;
  access_token: string;
}

/** Home route for each role — the single source of truth for role-based redirects. */
export const ROLE_HOME: Record<Role, string> = {
  admin: '/admin',
  faculty: '/faculty',
  student: '/student',
};

export const ROLE_LABEL: Record<Role, string> = {
  admin: 'Administrator',
  faculty: 'Faculty',
  student: 'Student',
};

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  homePath: string;
  isAdmin: boolean;
  isFaculty: boolean;
  isStudent: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

const STORAGE_KEYS = ['access_token', 'role', 'full_name', 'user_id', 'email'];

function persist(user: User) {
  localStorage.setItem('access_token', user.access_token);
  localStorage.setItem('role', user.role);
  localStorage.setItem('full_name', user.full_name);
  localStorage.setItem('user_id', String(user.user_id));
  if (user.email) localStorage.setItem('email', user.email);
}

function clearStorage() {
  STORAGE_KEYS.forEach((k) => localStorage.removeItem(k));
}

/** Decode the JWT payload (no signature check — the server verifies) to detect expiry early. */
function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return typeof payload.exp === 'number' && payload.exp * 1000 < Date.now();
  } catch {
    return true;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore the session: the role always comes from the server, never trusted from storage.
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token || isTokenExpired(token)) {
      clearStorage();
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then((res) => {
        const u: User = {
          access_token: token,
          user_id: res.data.user_id,
          full_name: res.data.full_name,
          email: res.data.email,
          role: res.data.role,
        };
        persist(u);
        setUser(u);
      })
      .catch(() => {
        clearStorage();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login(email.trim(), password);
    const data = res.data;
    const u: User = {
      access_token: data.access_token,
      role: data.role,
      full_name: data.full_name,
      user_id: data.user_id,
      email: email.trim().toLowerCase(),
    };
    persist(u);
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(() => {
    clearStorage();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        homePath: user ? ROLE_HOME[user.role] : '/login',
        isAdmin: user?.role === 'admin',
        isFaculty: user?.role === 'faculty',
        isStudent: user?.role === 'student',
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
