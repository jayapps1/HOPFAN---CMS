"use client";
import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth-provider";
import { SessionLoading, ServiceUnavailable } from "@/components/ui/feedback";

export function PortalGuard({ children }: { children: ReactNode }) {
  const auth = useAuth(); const router = useRouter();
  useEffect(() => {
    if (auth.status === "unauthenticated") router.replace(auth.expired ? "/login?reason=expired" : "/login");
  }, [auth.status, auth.expired, router]);
  if (auth.status === "unavailable") return <ServiceUnavailable onRetry={() => { void auth.refresh(); }} />;
  if (auth.status !== "authenticated" || !auth.user) return <SessionLoading />;
  return children;
}
