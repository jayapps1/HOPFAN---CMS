export type PermissionCode = string;
export interface RoleSummary { code: string; name: string }
export interface MinistryScope { id: string; code: string; name: string }
export interface MemberSummary { id: string; member_no: string; full_name: string; photo_url: null }
export type DashboardHint = "CHURCH_ADMIN" | "SUNDAY_SCHOOL" | "MINISTRY_OFFICER" | "STANDARD";
export interface CurrentUser {
  id: string;
  username: string;
  email: string | null;
  member: MemberSummary | null;
  roles: RoleSummary[];
  permissions: PermissionCode[];
  ministry_scopes: MinistryScope[];
  sunday_school_scopes: MinistryScope[];
  dashboard_profile: DashboardHint;
}
export interface CsrfResponse { csrf_token: string; authenticated: boolean }
export interface LoginResponse { status: "authenticated"; csrf_token: string }
export type LoginMethod = "password" | "totp";
