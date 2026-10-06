"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/features/auth/auth-provider";
import { useWorkspace } from "./workspace-provider";
import { useResource } from "./use-resource";
import { RecordState, MemberList, Pagination, Empty } from "./records-ui";
import { Badge, Button, Input } from "@/components/ui/primitives";
import { parseMembers, parseMinistries, type MemberRow, type MinistryRow, type Page } from "@/lib/api/workspace";

export function useFilters() {
  const params = useSearchParams(); const pathname = usePathname(); const router = useRouter();
  const update = (values: Record<string, string>) => {
    const next = new URLSearchParams(params.toString());
    if (!("page" in values)) next.delete("page");
    for (const [key, value] of Object.entries(values)) { if (value && value !== "ALL") next.set(key, value); else next.delete(key); }
    router.push(pathname + (next.size ? "?" + next.toString() : ""), { scroll: false });
  };
  const raw = Number(params.get("page") ?? "1");
  return { params, update, page: Number.isInteger(raw) && raw > 0 && raw <= 100000 ? raw : 1 };
}
export function Directory({ kind, ministryId }: { kind: "members" | "ministries"; ministryId?: string }) {
  const { user } = useAuth(); const workspace = useWorkspace(); const { params, update, page } = useFilters();
  const search = params.get("search") ?? ""; const status = params.get("status") ?? "ALL";
  const query = new URLSearchParams({ search, status, page: String(page), page_size: "25" });
  const selected = ministryId ?? workspace.ministryId;
  if (selected) query.set("ministry_id", selected);
  if (kind === "members") query.set("sort", params.get("sort") ?? "name");
  else query.set("category", params.get("category") ?? "ALL");
  const resource = useResource<Page<MemberRow> | Page<MinistryRow>>(
    user ? (ministryId ? `/api/v1/ministries/${encodeURIComponent(ministryId)}/members` : "/api/v1/" + kind) + "?" + query.toString() : null, kind === "members" ? parseMembers : parseMinistries);
  return <>
    {!ministryId && <div className="page-heading"><div><p className="eyebrow">CHURCH COMMUNITY</p><h1>{kind === "members" ? "Members" : "Ministries"}</h1><p>{kind === "members" ? "Find people and explore their church connections." : "Explore ministry membership and current leadership."}</p></div><Badge tone="blue">{workspace.ministry?.name ?? "All authorised records"}</Badge></div>}
    <form className="record-filters" onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); update({ search: String(data.get("search") ?? "") }); }}>
      <label className="search-field">Search<Input name="search" key={search} defaultValue={search} placeholder={kind === "members" ? "Name, member number or phone" : "Ministry name or code"} maxLength={200} /></label>
      <Button variant="secondary" type="submit">Search</Button>
      <label>Status<select value={status} onChange={event => update({ status: event.target.value })}><option value="ALL">All statuses</option>{(kind === "members" ? ["ACTIVE", "INACTIVE", "TRANSFERRED", "DECEASED"] : ["ACTIVE", "INACTIVE", "ARCHIVED"]).map(value => <option key={value}>{value}</option>)}</select></label>
      {kind === "members" ? <label>Sort by<select value={params.get("sort") ?? "name"} onChange={event => update({ sort: event.target.value })}><option value="name">Name</option><option value="member_no">Member number</option><option value="joined_date">Joined date</option></select></label>
        : <label>Category<select value={params.get("category") ?? "ALL"} onChange={event => update({ category: event.target.value })}>{["ALL", "MINISTRY", "FELLOWSHIP", "DEPARTMENT", "UNIT", "OTHER"].map(value => <option key={value}>{value}</option>)}</select></label>}
      <Button type="button" variant="ghost" onClick={() => update({ search: "", status: "", sort: "", category: "" })}>Clear filters</Button>
    </form>
    <RecordState {...resource} />
    {resource.data && <><div className="section-heading"><h2>{resource.data.total.toLocaleString()} {kind}</h2></div>
      {kind === "members" ? <MemberList items={resource.data.items as MemberRow[]} /> : <MinistryList items={resource.data.items as MinistryRow[]} />}
      <Pagination {...resource.data} change={next => update({ page: String(next) })} /></>}
  </>;
}
function MinistryList({ items }: { items: MinistryRow[] }) {
  if (!items.length) return <Empty title="No ministries found">Try another search or adjust your filters.</Empty>;
  return <div className="ministry-grid">{items.map(item => <Link className="card ministry-card" href={`/portal/ministries/${item.id}`} key={item.id}>
    <div className="card-heading"><Badge tone="blue">{item.category}</Badge><Badge tone={item.status === "ACTIVE" ? "green" : "neutral"}>{item.status}</Badge></div>
    <h2>{item.name}</h2><small className="muted">{item.code}</small><p>{item.description || "A place to connect and serve together."}</p>
    <div className="ministry-card-count">{item.member_count == null ? "Member summary unavailable" : `${item.member_count} members · ${item.active_member_count} active`}</div><span className="card-link">View ministry →</span>
  </Link>)}</div>;
}
