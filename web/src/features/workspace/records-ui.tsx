"use client";
import { useState, type ReactNode } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api/client";
import { Avatar, Badge, Button, Card } from "@/components/ui/primitives";
import { AccessDenied, ErrorMessage } from "@/components/ui/feedback";
import type { MemberRow } from "@/lib/api/workspace";

export function RecordState({ loading, error, retry }: { loading: boolean; error?: ApiError; retry: () => void }) {
  if (error?.status === 403) return <AccessDenied />;
  if (error) return <Card className="record-state"><ErrorMessage message={error.message} /><Button variant="secondary" onClick={retry}>Try again</Button></Card>;
  if (loading) return <Card className="record-state" ><div role="status" aria-label="Loading records"><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /><span className="sr-only">Loading records</span></div></Card>;
  return null;
}
export function MemberAvatar({ member }: { member: MemberRow }) {
  return <PrivateAvatar name={member.full_name} photo={member.photo_url} />;
}
export function PrivateAvatar({ name, photo }: { name: string; photo: string | null }) {
  const [failed, setFailed] = useState<string | null>(null);
  const url = photo ? api.photoUrl(photo) : "";
  if (!url || failed === url) return <Avatar name={name} />;
  // Direct cookie-authenticated request. Next image proxy cannot forward the
  // user's private session. Server emits bounded JPEG with no-store.
  return <img className="member-photo" src={url} alt="" width={44} height={44} onError={() => setFailed(url)} />;
}
export function MemberList({ items }: { items: MemberRow[] }) {
  if (!items.length) return <Empty title="No members found">Try another search or adjust your filters.</Empty>;
  return <div className="records-table-wrap"><table className="records-table"><caption className="sr-only">Member directory</caption><thead><tr><th scope="col">Member</th><th scope="col">Phone</th><th scope="col">Ministries</th><th scope="col">Status</th></tr></thead>
    <tbody>{items.map(member => <tr key={member.id}><td><Link className="member-link" href={`/portal/members/${member.id}`}><MemberAvatar member={member} /><span><strong>{member.full_name}</strong><small>{member.member_no}</small></span></Link></td><td data-label="Phone">{member.phone || "Not provided"}</td><td data-label="Ministries">{member.ministries.map(ministry => ministry.name).join(", ") || "No current ministry"}</td><td data-label="Status"><Badge tone={member.status === "ACTIVE" ? "green" : "neutral"}>{member.status}</Badge></td></tr>)}</tbody></table></div>;
}
export function Empty({ title, children }: { title: string; children: ReactNode }) { return <Card className="record-state"><h2>{title}</h2><p className="muted">{children}</p></Card>; }
export function Pagination({ page, pages, total, change }: { page: number; pages: number; total: number; change: (page: number) => void }) {
  return <nav className="pagination" aria-label="Pagination"><span>{total.toLocaleString()} records · Page {page} of {Math.max(pages, 1)}</span><div><Button variant="secondary" disabled={page <= 1} onClick={() => change(page - 1)}>Previous</Button><Button variant="secondary" disabled={page >= pages} onClick={() => change(page + 1)}>Next</Button></div></nav>;
}
