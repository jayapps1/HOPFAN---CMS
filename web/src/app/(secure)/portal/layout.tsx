import { Suspense, type ReactNode } from "react";
import { PortalGuard } from "@/features/auth/portal-guard";
import { WorkspaceProvider } from "@/features/workspace/workspace-provider";
import { PortalShell } from "@/components/portal/portal-shell";
import { SessionLoading } from "@/components/ui/feedback";
export default function PortalLayout({ children }: { children: ReactNode }) {
  return <PortalGuard><Suspense fallback={<SessionLoading />}><WorkspaceProvider><PortalShell>{children}</PortalShell></WorkspaceProvider></Suspense></PortalGuard>;
}
