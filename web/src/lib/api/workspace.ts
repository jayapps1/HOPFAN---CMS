export interface Summary { id: string; name: string }
export interface Page<T> { items: T[]; page: number; page_size: number; total: number; pages: number }
export interface MemberRow { id: string; member_no: string; full_name: string; gender: string; phone: string; status: string; photo_url: string | null; ministries: Summary[] }
export interface Leadership { id: string; ministry_id: string; ministry_name: string; member_id: string; full_name: string; member_no: string; position_id: string; position_name: string; position_code: string; is_leadership: boolean; is_current: boolean; start_date: string; end_date: string | null }
export interface LeadershipCounts { positions: number; current: number; members: number; vacant: number }
export interface MinistryRow { id: string; code: string; name: string; description: string; category: string; status: string; member_count: number | null; active_member_count: number | null }
export interface MinistryDetail extends MinistryRow { leadership: LeadershipCounts | null; can_view_members: boolean; can_view_leadership: boolean }
export interface MemberDetail extends MemberRow {
  identity: { first_name: string; middle_name: string; last_name: string; date_of_birth: string; marital_status: string };
  contact: { phone: string; alternate_phone: string; email: string; address: string };
  membership: { date_joined: string; baptized: boolean; baptism_date: string };
  leadership?: Leadership[];
  household?: { id: string; household_name: string; household_code: string; status: string; relationship_label: string };
  sunday_school?: { student: boolean; class_id?: string | null; class_name?: string; status?: string; teachers: { class_name: string; role_label: string }[] };
}
export interface DashboardData { scope: string; metrics: { key: string; label: string; value: number | null; detail: string }[]; recent_members: MemberRow[]; unavailable: string[] }
type Obj = Record<string, unknown>;
export function obj(v: unknown): Obj { if (!v || typeof v !== "object" || Array.isArray(v)) throw new Error(); return v as Obj; }
export function str(v: unknown): string { if (typeof v !== "string") throw new Error(); return v; }
export function num(v: unknown): number { if (typeof v !== "number" || !Number.isFinite(v)) throw new Error(); return v; }
export function bool(v: unknown): boolean { if (typeof v !== "boolean") throw new Error(); return v; }
export function nullable<T>(v: unknown, parse: (v: unknown) => T): T | null { return v == null ? null : parse(v); }
export function array<T>(v: unknown, parse: (v: unknown) => T): T[] { if (!Array.isArray(v)) throw new Error(); return v.map(parse); }
export function parseOptions(v: unknown): Summary[] { return array(v, value => { const o = obj(value); return { id: str(o.id), name: str(o.name) }; }); }
export function parseMember(v: unknown): MemberRow { const o = obj(v); return { id: str(o.id), member_no: str(o.member_no), full_name: str(o.full_name), gender: str(o.gender), phone: str(o.phone), status: str(o.status), photo_url: nullable(o.photo_url, str), ministries: parseOptions(o.ministries) }; }
export function parseLeadership(v: unknown): Leadership { const o = obj(v); return { id: str(o.id), ministry_id: str(o.ministry_id), ministry_name: str(o.ministry_name), member_id: str(o.member_id), full_name: str(o.full_name), member_no: str(o.member_no), position_id: str(o.position_id), position_name: str(o.position_name), position_code: str(o.position_code), is_leadership: bool(o.is_leadership), is_current: bool(o.is_current), start_date: str(o.start_date), end_date: nullable(o.end_date, str) }; }
export function parseMinistry(v: unknown): MinistryRow { const o = obj(v); return { id: str(o.id), code: str(o.code), name: str(o.name), description: str(o.description), category: str(o.category), status: str(o.status), member_count: nullable(o.member_count, num), active_member_count: nullable(o.active_member_count, num) }; }
export function parseMinistryDetail(v: unknown): MinistryDetail { const o = obj(v); return { ...parseMinistry(v), can_view_members: bool(o.can_view_members), can_view_leadership: bool(o.can_view_leadership), leadership: nullable(o.leadership, value => { const l = obj(value); return { positions: num(l.positions), current: num(l.current), members: num(l.members), vacant: num(l.vacant) }; }) }; }
export function parseMemberDetail(v: unknown): MemberDetail {
  const o = obj(v); const i = obj(o.identity); const c = obj(o.contact); const m = obj(o.membership);
  const result: MemberDetail = { ...parseMember(v), identity: { first_name: str(i.first_name), middle_name: str(i.middle_name), last_name: str(i.last_name), date_of_birth: str(i.date_of_birth), marital_status: str(i.marital_status) },
    contact: { phone: str(c.phone), alternate_phone: str(c.alternate_phone), email: str(c.email), address: str(c.address) },
    membership: { date_joined: str(m.date_joined), baptized: bool(m.baptized), baptism_date: str(m.baptism_date) } };
  if (o.leadership != null) result.leadership = array(o.leadership, parseLeadership);
  if (o.household != null) { const h = obj(o.household); result.household = { id: str(h.id), household_name: str(h.household_name), household_code: str(h.household_code), status: str(h.status), relationship_label: str(h.relationship_label) }; }
  if (o.sunday_school != null) { const s = obj(o.sunday_school); result.sunday_school = { student: bool(s.student), class_name: s.class_name === undefined ? undefined : str(s.class_name), status: s.status === undefined ? undefined : str(s.status), teachers: array(s.teachers, value => { const t = obj(value); return { class_name: str(t.class_name), role_label: str(t.role_label) }; }) }; }
  return result;
}
export function parsePage<T>(parse: (v: unknown) => T): (v: unknown) => Page<T> { return v => { const o = obj(v); return { items: array(o.items, parse), page: num(o.page), page_size: num(o.page_size), total: num(o.total), pages: num(o.pages) }; }; }
export const parseMembers = parsePage(parseMember);
export const parseMinistries = parsePage(parseMinistry);
export const parseLeaders = parsePage(parseLeadership);
export function parseDashboard(v: unknown): DashboardData { const o = obj(v); return { scope: str(o.scope), metrics: array(o.metrics, value => { const m = obj(value); return { key: str(m.key), label: str(m.label), value: nullable(m.value, num), detail: str(m.detail) }; }), recent_members: array(o.recent_members, parseMember), unavailable: array(o.unavailable, str) }; }
