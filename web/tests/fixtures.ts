import type { CurrentUser } from "@/types/auth";
export const youth = { id: "youth-id", code: "YOUTH", name: "Youth Ministry" };
export const choir = { id: "choir-id", code: "CHOIR", name: "Choir Ministry" };
export function user(changes: Partial<CurrentUser> = {}): CurrentUser {
  return { id: "synthetic-user", username: "ama", email: "ama@example.invalid", member: null,
    roles: [{ code: "MINISTRY_SECRETARY", name: "Ministry Secretary" }],
    permissions: ["MEMBERS_VIEW_OWN_MINISTRY", "ATTENDANCE_VIEW_OWN_MINISTRY", "MINISTRIES_VIEW_OWN"],
    ministry_scopes: [youth], sunday_school_scopes: [], dashboard_profile: "MINISTRY_OFFICER", ...changes };
}
