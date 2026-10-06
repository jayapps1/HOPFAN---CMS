"use client";
import { AlertTriangle, LockKeyhole, ShieldX, WifiOff } from "lucide-react";
import { Button } from "./primitives";
import Link from "next/link";

export function SessionLoading() {
  return <main className="session-screen" aria-busy="true" aria-label="Checking your session"><div className="session-card">
    <LockKeyhole size={28} aria-hidden="true" /><h1>Opening your workspace</h1><p>Checking your secure session…</p>
    <div className="skeleton" /><div className="skeleton skeleton-short" />
  </div></main>;
}
export function ServiceUnavailable({ onRetry }: { onRetry: () => void }) {
  return <main className="session-screen"><div className="session-card"><WifiOff size={30} aria-hidden="true" />
    <h1>We couldn’t connect to HOPFAN</h1><p>Please check your connection and try again.</p><Button onClick={onRetry}>Try again</Button>
  </div></main>;
}
export function AccessDenied() {
  return <section className="empty-state"><span className="empty-icon"><ShieldX size={27} aria-hidden="true" /></span>
    <h1>Access denied</h1><p>You do not have permission to access this area.</p><p className="muted">Contact your church administrator if you need this workspace.</p>
    <Link className="button button-secondary" href="/portal/dashboard">Return to dashboard</Link>
  </section>;
}
export function ErrorMessage({ message, id }: { message: string; id?: string }) {
  return <div className="error-message" role="alert" id={id}><AlertTriangle size={17} aria-hidden="true" /><span>{message}</span></div>;
}
