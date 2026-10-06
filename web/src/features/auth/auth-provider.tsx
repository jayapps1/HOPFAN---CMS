"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError, type ApiClient } from "@/lib/api/client";
import type { CurrentUser, LoginMethod } from "@/types/auth";

type Status = "loading" | "authenticated" | "unauthenticated" | "unavailable";
interface AuthContextValue {
  user: CurrentUser | null; status: Status; expired: boolean;
  refresh: () => Promise<void>;
  login: (method: LoginMethod, email: string, credential: string) => Promise<void>;
  logout: () => Promise<void>;
}
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children, client = api }: { children: ReactNode; client?: ApiClient }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [expired, setExpired] = useState(false);
  const generation = useRef(0);
  const hadSession = useRef(false);
  const busy = useRef(false);

  const forget = useCallback((wasExpired: boolean) => {
    generation.current += 1; hadSession.current = false;
    client.clearSession(); setUser(null); setStatus("unauthenticated"); setExpired(wasExpired);
  }, [client]);

  const refresh = useCallback(async () => {
    const current = generation.current;
    try {
      const profile = await client.currentUser();
      if (current !== generation.current) return;
      hadSession.current = true; setUser(profile); setStatus("authenticated"); setExpired(false);
    } catch (error) {
      if (current !== generation.current) return;
      if (error instanceof ApiError && error.status === 401) forget(hadSession.current);
      else { setUser(null); setStatus("unavailable"); }
    }
  }, [client, forget]);

  useEffect(() => client.onUnauthorized(() => forget(hadSession.current)), [client, forget]);
  useEffect(() => { const timer = setTimeout(() => { void refresh(); }, 0); return () => clearTimeout(timer); }, [refresh]);

  useEffect(() => {
    if (status !== "authenticated") return;
    // CSRF checks validate the server session without refreshing idle activity.
    // No perpetual /me heartbeat can keep an abandoned session signed in.
    let stopped = false;
    let pending = false;
    const check = async () => {
      if (pending || document.visibilityState === "hidden") return;
      pending = true; const current = generation.current;
      try {
        const result = await client.csrf();
        if (!stopped && current === generation.current && !result.authenticated) forget(true);
      } catch { /* A transient connection failure does not claim logout succeeded. */ }
      finally { pending = false; }
    };
    const timer = setInterval(() => { void check(); }, 5 * 60_000);
    const visible = () => { void check(); };
    window.addEventListener("focus", visible); document.addEventListener("visibilitychange", visible);
    return () => { stopped = true; clearInterval(timer); window.removeEventListener("focus", visible); document.removeEventListener("visibilitychange", visible); };
  }, [client, status, forget]);

  const login = useCallback(async (method: LoginMethod, email: string, credential: string) => {
    if (busy.current) return;
    busy.current = true; const current = ++generation.current;
    try {
      const profile = await client.login(method, email, credential);
      if (current !== generation.current) return;
      hadSession.current = true; setUser(profile); setStatus("authenticated"); setExpired(false);
    } finally { busy.current = false; }
  }, [client]);

  const logout = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    generation.current += 1;
    try { await client.logout(); forget(false); }
    finally { busy.current = false; }
  }, [client, forget]);

  return <AuthContext.Provider value={{ user, status, expired, refresh, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const result = useContext(AuthContext);
  if (!result) throw new Error("AuthProvider is required");
  return result;
}
