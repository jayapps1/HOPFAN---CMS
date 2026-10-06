"use client";
import { Monitor, ShieldCheck } from "lucide-react";
import { useAuth } from "@/features/auth/auth-provider";
import { useWorkspace } from "@/features/workspace/workspace-provider";
import { canAccess, hasAny, modules, type ModuleId } from "@/lib/permissions";
import { AccessDenied } from "@/components/ui/feedback";
import { Badge, Card } from "@/components/ui/primitives";
import { ModuleIcon } from "@/components/portal/icons";

export function ModuleWorkspace({ moduleId }: { moduleId: ModuleId }) {
  const { user } = useAuth(); const workspace = useWorkspace(); const module = modules.find(item => item.id === moduleId);
  if (!user || !module) return null;
  if (!canAccess(user, module)) return <AccessDenied />;
  const selected = moduleId === "sunday-school" ? workspace.schoolClass : workspace.ministry;
  const effective = selected ?? (!hasAny(user, module.global) && module.scoped?.length ? user.ministry_scopes[0] : null);
  return <><div className="page-heading"><div><p className="eyebrow">YOUR WORKSPACE</p><h1>{module.label}</h1><p>{module.description}</p></div>
    <Badge tone="blue">{effective?.name ?? "Your authorised access"}</Badge></div>
    <Card className="module-empty"><span className="large-module-icon"><ModuleIcon name={module.icon} size={37} /></span>
      <Badge tone="green">Online workspace</Badge><h2>Your {module.label.toLowerCase()} workspace is being prepared</h2>
      <p>Continue managing these records in the HOPFAN desktop application. Online records and summaries will appear here when this workspace opens.</p>
      <div className="module-availability"><Monitor size={19} aria-hidden="true" /><span>Available in HOPFAN desktop</span></div>
    </Card><div className="access-note"><ShieldCheck size={16} aria-hidden="true" /><span>Your assigned permissions and workspace access apply to every record.</span></div></>;
}
