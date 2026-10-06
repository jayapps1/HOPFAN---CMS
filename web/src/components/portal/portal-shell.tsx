"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, LogOut, Menu, ShieldCheck, UserRound, X } from "lucide-react";
import { Sidebar } from "./sidebar";
import { useAuth } from "@/features/auth/auth-provider";
import { WorkspaceSelector, useWorkspace } from "@/features/workspace/workspace-provider";
import { modules } from "@/lib/permissions";
import { ThemeControl } from "@/components/theme-provider";
import { Avatar, Button } from "@/components/ui/primitives";
import { AccessDenied, ErrorMessage } from "@/components/ui/feedback";
import { ApiError } from "@/lib/api/client";

export function PortalShell({ children }: { children: ReactNode }) {
  const auth = useAuth(); const router = useRouter(); const pathname = usePathname();
  const refresh = auth.refresh;
  const workspace = useWorkspace();
  const [drawer, setDrawer] = useState(false); const [profile, setProfile] = useState(false);
  const [error, setError] = useState(""); const [loggingOut, setLoggingOut] = useState(false);
  const lastChecked = useRef(0);
  useEffect(() => {
    if (!lastChecked.current) { lastChecked.current = Date.now(); return; }
    if (Date.now() - lastChecked.current > 30_000) { lastChecked.current = Date.now(); void refresh(); }
  }, [pathname, refresh]);
  if (!auth.user) return null;
  const user = auth.user; const name = user.member?.full_name || user.username;
  const title = modules.find(module => pathname === `/portal/${module.id}` || pathname.startsWith(`/portal/${module.id}/`))?.label ?? "Dashboard";
  const logout = async () => {
    if (loggingOut) return;
    setLoggingOut(true); setError("");
    try { await auth.logout(); router.replace("/login"); }
    catch (failure) { setError(failure instanceof ApiError ? failure.message : "Unable to sign out. Please try again."); }
    finally { setLoggingOut(false); }
  };
  return <div className="portal-shell">
    <a href="#portal-main" className="skip-link">Skip to main content</a>
    <aside className="desktop-sidebar"><Sidebar /></aside>
    <div className="portal-main-column">
      <header className="topbar">
        <Dialog.Root open={drawer} onOpenChange={setDrawer}><Dialog.Trigger asChild><button className="icon-button mobile-menu" aria-label="Open navigation"><Menu size={21} /></button></Dialog.Trigger>
          <Dialog.Portal><Dialog.Overlay className="dialog-overlay mobile-overlay" /><Dialog.Content className="mobile-drawer">
            <Dialog.Title className="sr-only">Navigation</Dialog.Title><Dialog.Description className="sr-only">Your authorised HOPFAN workspaces.</Dialog.Description>
            <Dialog.Close className="drawer-close icon-button" aria-label="Close navigation"><X size={21} /></Dialog.Close><Sidebar onNavigate={() => setDrawer(false)} />
          </Dialog.Content></Dialog.Portal></Dialog.Root>
        <div className="topbar-breadcrumb"><span>Portal</span><span aria-hidden="true">/</span><strong>{title}</strong></div>
        <div className="topbar-workspace"><WorkspaceSelector /></div>
        <div className="topbar-controls"><ThemeControl />
          <DropdownMenu.Root><DropdownMenu.Trigger className="account-trigger" aria-label="Account menu"><Avatar name={name} /><span className="account-name"><strong>{name}</strong><small>{user.roles[0]?.name ?? "HOPFAN account"}</small></span><ChevronDown size={14} aria-hidden="true" /></DropdownMenu.Trigger>
            <DropdownMenu.Portal><DropdownMenu.Content className="dropdown-content" align="end" sideOffset={12}>
              <DropdownMenu.Label className="account-menu-label"><strong>{name}</strong><span>{user.email ?? user.username}</span></DropdownMenu.Label>
              <DropdownMenu.Separator className="dropdown-separator" />
              <DropdownMenu.Item className="dropdown-item" onSelect={() => setProfile(true)}><UserRound size={16} aria-hidden="true" />Your profile</DropdownMenu.Item>
              <DropdownMenu.Item className="dropdown-item" disabled={loggingOut} onSelect={() => { void logout(); }}><LogOut size={16} aria-hidden="true" />{loggingOut ? "Signing out…" : "Sign out"}</DropdownMenu.Item>
            </DropdownMenu.Content></DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </header>
      <main className="portal-content" id="portal-main" tabIndex={-1}>{error && <ErrorMessage message={error} />}{workspace.invalid ? <AccessDenied /> : children}</main>
      <footer className="portal-footer"><span>HOPFAN · House of Prayer for All Nations</span><span><ShieldCheck size={13} aria-hidden="true" /> Secure workspace</span></footer>
    </div>
    <Dialog.Root open={profile} onOpenChange={setProfile}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content profile-dialog">
      <Dialog.Title>Your profile</Dialog.Title><Dialog.Description>Your HOPFAN account and church connection.</Dialog.Description>
      <div className="profile-summary"><Avatar name={name} /><div><strong>{name}</strong><p>{user.email ?? user.username}</p></div></div>
      <dl className="profile-details"><dt>Software roles</dt><dd>{user.roles.map(role => role.name).join(", ") || "No roles assigned"}</dd>
        {user.member && <><dt>Member number</dt><dd>{user.member.member_no}</dd></>}
        <dt>Ministry workspaces</dt><dd>{user.ministry_scopes.map(scope => scope.name).join(", ") || "No ministry scopes assigned"}</dd>
      </dl>
      <Dialog.Close asChild><Button variant="secondary">Close</Button></Dialog.Close><Dialog.Close className="dialog-close" aria-label="Close profile"><X size={19} /></Dialog.Close>
    </Dialog.Content></Dialog.Portal></Dialog.Root>
  </div>;
}
