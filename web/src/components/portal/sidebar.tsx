"use client";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ShieldCheck } from "lucide-react";
import { useAuth } from "@/features/auth/auth-provider";
import { visibleModules } from "@/lib/permissions";
import { ModuleIcon } from "./icons";

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth(); const pathname = usePathname();
  if (!user) return null;
  return <div className="sidebar-inner">
    <Link href="/portal/dashboard" className="sidebar-brand" onClick={onNavigate}><span className="sidebar-logo"><Image src="/brand/hopfan-logo.png" alt="" width={38} height={40} /></span>
      <span><strong>HOPFAN</strong><small>SECURE PORTAL</small></span></Link>
    <div className="sidebar-section-label">YOUR WORKSPACE</div>
    <nav className="portal-navigation" aria-label="Main navigation">
      <Link href="/portal/dashboard" onClick={onNavigate} aria-current={pathname === "/portal/dashboard" ? "page" : undefined}><LayoutDashboard size={19} aria-hidden="true" /><span>Dashboard</span></Link>
      {visibleModules(user).map(module => <Link key={module.id} href={`/portal/${module.id}`} onClick={onNavigate} aria-current={pathname === `/portal/${module.id}` || pathname.startsWith(`/portal/${module.id}/`) ? "page" : undefined}>
        <ModuleIcon name={module.icon} size={19} /><span>{module.label}</span>
      </Link>)}
    </nav>
    <div className="sidebar-footer"><ShieldCheck size={18} aria-hidden="true" /><span>House of Prayer<br /><small>for All Nations</small></span></div>
  </div>;
}
