"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth } from "@/features/auth/auth-provider";
import { useWorkspace } from "./workspace-provider";
import { useResource } from "./use-resource";
import { useFilters, Directory } from "./directories";
import { MemberAvatar, RecordState, Empty, Pagination } from "./records-ui";
import { Badge, Card } from "@/components/ui/primitives";
import { parseMemberDetail, parseMinistryDetail, parseLeaders, type Leadership } from "@/lib/api/workspace";

function Details({ values }: { values: Record<string, string> }) {
  return <dl className="record-details">{Object.entries(values).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value || "Not provided"}</dd></div>)}</dl>;
}
export function MemberProfile() {
  const { memberId } = useParams<{ memberId: string }>(); const { user } = useAuth(); const workspace = useWorkspace();
  const scope = workspace.ministryId ? "?ministry=" + workspace.ministryId : "";
  const resource = useResource(user ? `/api/v1/members/${encodeURIComponent(memberId)}` : null, parseMemberDetail);
  const member = resource.data;
  return <><Link className="back-link" href={"/portal/members" + scope}>← Members</Link><RecordState {...resource} />
    {member && <><div className="profile-banner"><MemberAvatar key={member.id} member={member} /><div><p className="eyebrow">{member.member_no}</p><h1>{member.full_name}</h1><p>{member.ministries.map(item => item.name).join(" · ") || "No current ministry"}</p></div><Badge tone={member.status === "ACTIVE" ? "green" : "neutral"}>{member.status}</Badge></div>
      <div className="profile-grid"><Card><h2>Identity</h2><Details values={{ "First name": member.identity.first_name, "Middle name": member.identity.middle_name, "Last name": member.identity.last_name, Gender: member.gender, "Date of birth": member.identity.date_of_birth, "Marital status": member.identity.marital_status }} /></Card>
      <Card><h2>Contact</h2><Details values={{ Phone: member.contact.phone, "Alternate phone": member.contact.alternate_phone, Email: member.contact.email, Address: member.contact.address }} /></Card>
      <Card><h2>Membership</h2><Details values={{ "Joined date": member.membership.date_joined, Baptized: member.membership.baptized ? "Yes" : "No", "Baptism date": member.membership.baptism_date }} /><h3>Ministries</h3><div className="record-chips">{member.ministries.map(item => <Badge key={item.id} tone="blue">{item.name}</Badge>)}</div></Card>
      {member.household && <Card><h2>Household</h2><Details values={{ Household: member.household.household_name, Code: member.household.household_code, Relationship: member.household.relationship_label }} /></Card>}
      {member.sunday_school && <Card><h2>Sunday School</h2><Details values={{ Class: member.sunday_school.class_name ?? "", Status: member.sunday_school.status ?? "" }} />{member.sunday_school.teachers.map((item, index) => <p key={index}>{item.role_label} · {item.class_name}</p>)}</Card>}
      {member.leadership && <Card className="profile-wide"><h2>Leadership appointments</h2><LeadershipList items={member.leadership} /></Card>}</div></>}
  </>;
}
export function MinistryProfile() {
  const { ministryId } = useParams<{ ministryId: string }>(); const { user } = useAuth(); const { params, update } = useFilters();
  const resource = useResource(user ? `/api/v1/ministries/${encodeURIComponent(ministryId)}` : null, parseMinistryDetail);
  const ministry = resource.data; const tab = params.get("tab") ?? "overview";
  return <><Link className="back-link" href="/portal/ministries">← Ministries</Link><RecordState {...resource} />
    {ministry && <><div className="page-heading"><div><p className="eyebrow">{ministry.code} · {ministry.category}</p><h1>{ministry.name}</h1><p>{ministry.description || "Connect and serve with this ministry."}</p></div><Badge tone={ministry.status === "ACTIVE" ? "green" : "neutral"}>{ministry.status}</Badge></div>
      <nav className="record-tabs" aria-label="Ministry sections">{["overview", ...(ministry.can_view_members ? ["members"] : []), ...(ministry.can_view_leadership ? ["leadership"] : [])].map(value => <button key={value} aria-current={tab === value ? "page" : undefined} onClick={() => update({ tab: value, page: "", search: "", status: "", category: "", sort: "" })}>{value[0].toUpperCase() + value.slice(1)}</button>)}</nav>
      {tab === "overview" ? <div className="metric-grid">{ministry.member_count != null && <Card><p className="muted">Current members</p><strong className="metric-value">{ministry.member_count}</strong><p>{ministry.active_member_count} active members</p></Card>}{ministry.leadership && <><Card><p className="muted">Current appointments</p><strong className="metric-value">{ministry.leadership.current}</strong><p>{ministry.leadership.members} people serving</p></Card><Card><p className="muted">Vacant positions</p><strong className="metric-value">{ministry.leadership.vacant}</strong><p>{ministry.leadership.positions} configured positions</p></Card></>}</div>
        : tab === "members" && ministry.can_view_members ? <Directory kind="members" ministryId={ministryId} />
        : tab === "leadership" && ministry.can_view_leadership ? <MinistryLeadership ministryId={ministryId} />
        : <Empty title="Section unavailable">You do not have access to this section.</Empty>}</>}
  </>;
}
function MinistryLeadership({ ministryId }: { ministryId: string }) {
  const { page, update } = useFilters();
  const resource = useResource(`/api/v1/ministries/${encodeURIComponent(ministryId)}/leadership?page=${page}`, parseLeaders);
  return <><RecordState {...resource} />{resource.data && <><LeadershipList items={resource.data.items} /><Pagination {...resource.data} change={value => update({ page: String(value) })} /></>}</>;
}
function LeadershipList({ items }: { items: Leadership[] }) {
  if (!items.length) return <Empty title="No leadership appointments">No appointments are recorded in this section.</Empty>;
  return <div className="leadership-list">{items.map(item => <article className="leadership-row" key={item.id}><div><Badge tone="blue">{item.position_name}</Badge><h3>{item.full_name}</h3><p>{item.member_no} · {item.ministry_name}</p></div><div><Badge tone={item.is_current ? "green" : "neutral"}>{item.is_current ? "Current" : "Past"}</Badge><p>From {item.start_date}{item.end_date ? " to " + item.end_date : ""}</p></div></article>)}</div>;
}
