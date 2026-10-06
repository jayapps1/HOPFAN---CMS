"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/features/auth/auth-provider";
import { api, ApiError } from "@/lib/api/client";
import { useSearchParams } from "next/navigation";

// Key every response by identity, effective access and URL. A changed key hides
// old data immediately; abort and cleanup also discard late responses.
export function useResource<T>(path: string | null, decoder: (v: unknown) => T,
    loader?: (path: string, signal: AbortSignal) => Promise<T>) {
  const { user } = useAuth();
  const search = useSearchParams();
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([user?.id, user?.permissions, user?.ministry_scopes, user?.sunday_school_scopes,
    search.get("ministry"), search.get("schoolClass"), path, attempt]);
  const [state, setState] = useState<{ key: string; data?: T; error?: ApiError }>({ key: "" });
  useEffect(() => {
    if (!user || !path) return;
    const controller = new AbortController();
    void (loader ? loader(path, controller.signal) : api.get(path, decoder, controller.signal)).then(data => {
      if (!controller.signal.aborted) setState({ key, data });
    }).catch(error => {
      if (!controller.signal.aborted) setState({ key, error: error instanceof ApiError ? error : new ApiError(0, "NETWORK_ERROR", "Unable to load this workspace.") });
    });
    return () => controller.abort();
  }, [key, path, decoder, user, loader]);
  const current = state.key === key ? state : null;
  return { data: current?.data, error: current?.error, loading: !!path && !current?.data && !current?.error,
    update: (transform: (data: T) => T) => setState(previous => previous.key === key && previous.data
      ? { key, data: transform(previous.data) } : previous),
    retry: () => setAttempt(value => value + 1) };
}
