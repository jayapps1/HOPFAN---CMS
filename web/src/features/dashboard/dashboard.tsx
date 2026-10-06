"use client";
import Link from "next/link";
import { ArrowRight, Layers3 } from "lucide-react";
import { useAuth } from "@/features/auth/auth-provider";
import { useWorkspace } from "@/features/workspace/workspace-provider";
import { useResource } from "@/features/workspace/use-resource";
import { MemberList, RecordState, Empty } from "@/features/workspace/records-ui";
import { parseDashboard } from "@/lib/api/workspace";
import { dashboardProfile, presentations } from "./profiles";
import { visibleModules } from "@/lib/permissions";
import { Badge, Card } from "@/components/ui/primitives";
import { ModuleIcon } from "@/components/portal/icons";

export function Dashboard() {
  const { user } = useAuth(); const workspace = useWorkspace();
  const query = new URLSearchParams();
  if (workspace.schoolMode && workspace.schoolClass) query.set("class_id", workspace.schoolClass.id);
  else if (workspace.ministryId) query.set("ministry_id", workspace.ministryId);
  const resource = useResource(user ? "/api/v1/dashboard?" + query.toString() : null, parseDashboard);
  if (!user) return null;
  const name = user.member?.full_name || user.username;
  const profile = dashboardProfile(user); const presentation = presentations[profile];
  const available = visibleModules(user); const scope = workspace.schoolMode ? workspace.schoolClass : workspace.ministry;
  const quick = available.filter(item => ["members", "ministries"].includes(item.id));
  return <>
    <div className="page-heading"><div><p className="eyebrow">{presentation.label}</p><h1>Welcome back, {name.split(" ")[0]}.</h1><p>Your church community at a glance.</p></div>
      <span className="today-label">{new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(new Date())}</span></div>
    <section className="welcome-banner"><div><Badge tone="green"><span className="status-dot" />{scope?.name ?? (workspace.global ? "Church-wide workspace" : "Your authorised workspace")}</Badge>
      <h2>{presentation.title}</h2><p>{presentation.detail}</p></div><div className="banner-emblem" aria-hidden="true"><Layers3 size={68} strokeWidth={1.1} /></div></section>
    <RecordState {...resource} />
    {resource.data && <>
      {resource.data.metrics.length ? <div className="metric-grid">{resource.data.metrics.map(metric => <Card key={metric.key}><p className="muted">{metric.label}</p><strong className="metric-value">{metric.value?.toLocaleString() ?? "Unavailable"}</strong>{metric.detail && <p className="muted">{metric.detail}</p>}</Card>)}</div>
        : <Empty title="No summaries available">Your account does not have access to dashboard metrics. Contact your church administrator if you need additional access.</Empty>}
      {resource.data.recent_members.length > 0 && <><div className="section-heading"><h2>Recently added members</h2><Link href="/portal/members">View members →</Link></div><MemberList items={resource.data.recent_members} /></>}
      {resource.data.unavailable.length > 0 && <p className="summary-note muted">Unavailable in this workspace: {resource.data.unavailable.join(", ")}.</p>}
    </>}
    <div className="section-heading"><h2>Your workspaces</h2><span>Based on your assigned access</span></div>
    <div className="workspace-cards">{available.slice(0, 4).map(module => <Link href={`/portal/${module.id}`} className="workspace-card" key={module.id}>
      <span className={`module-icon module-${module.id}`}><ModuleIcon name={module.icon} size={23} /></span><h3>{module.label}</h3><p>{module.description}</p>
      <span className="card-link">Open workspace <ArrowRight size={15} aria-hidden="true" /></span>
    </Link>)}</div>
    {quick.length > 0 && <Card className="quick-card"><h2>Quick actions</h2><div className="live-actions">{quick.map(item => <Link className="button button-secondary" key={item.id} href={`/portal/${item.id}`}>View {item.label.toLowerCase()}</Link>)}</div></Card>}
  </>;
}
