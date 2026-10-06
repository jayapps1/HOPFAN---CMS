import type { CurrentUser, CsrfResponse, LoginResponse, MinistryScope, RoleSummary } from "@/types/auth";

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Invalid contract");
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== "string") throw new Error("Invalid contract");
  return value;
}
function array<T>(value: unknown, parse: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) throw new Error("Invalid contract");
  return value.map(parse);
}
function scope(value: unknown): MinistryScope {
  const item = record(value);
  return { id: text(item.id), code: text(item.code), name: text(item.name) };
}
function role(value: unknown): RoleSummary {
  const item = record(value);
  return { code: text(item.code), name: text(item.name) };
}
export function parseUser(value: unknown): CurrentUser {
  const user = record(value);
  const hint = text(user.dashboard_profile);
  if (!["CHURCH_ADMIN", "SUNDAY_SCHOOL", "MINISTRY_OFFICER", "STANDARD"].includes(hint)) throw new Error("Invalid contract");
  const member = user.member === null ? null : record(user.member);
  return {
    id: text(user.id), username: text(user.username), email: user.email === null ? null : text(user.email),
    member: member ? { id: text(member.id), member_no: text(member.member_no), full_name: text(member.full_name), photo_url: null } : null,
    roles: array(user.roles, role), permissions: array(user.permissions, text),
    ministry_scopes: array(user.ministry_scopes, scope), sunday_school_scopes: array(user.sunday_school_scopes, scope),
    dashboard_profile: hint as CurrentUser["dashboard_profile"],
  };
}
function token(value: unknown): string {
  const result = text(value);
  if (!/^[0-9a-f]{64}$/.test(result)) throw new Error("Invalid contract");
  return result;
}
export function parseCsrf(value: unknown): CsrfResponse {
  const result = record(value);
  if (typeof result.authenticated !== "boolean") throw new Error("Invalid contract");
  return { csrf_token: token(result.csrf_token), authenticated: result.authenticated };
}
export function parseLogin(value: unknown): LoginResponse {
  const result = record(value);
  if (result.status !== "authenticated") throw new Error("Invalid contract");
  return { status: "authenticated", csrf_token: token(result.csrf_token) };
}
