import type { CurrentUser } from "@/types/auth";

export type ModuleId = "members" | "households" | "attendance" | "ministries" | "sunday-school" | "sms" | "reports" | "administration" | "finance" | "welfare" | "events" | "announcements" | "visitors" | "website" | "prayer-requests";
export interface ModuleDefinition { id: ModuleId; label: string; description: string; icon: string; global: string[]; scoped?: string[]; grants?: string[] }
export const modules: ModuleDefinition[] = [
  { id:"events",label:"Events",icon:"calendar",description:"Scoped event planning and approved publication.",global:["EVENT_VIEW_ALL"],scoped:["EVENT_VIEW_OWN_MINISTRY"] },
  { id:"announcements",label:"Announcements",icon:"message",description:"Approved church and ministry communications.",global:["ANNOUNCEMENT_VIEW_ALL"],scoped:["ANNOUNCEMENT_VIEW_OWN_MINISTRY"] },
  { id:"visitors",label:"Visitors",icon:"users",description:"Private visitor inquiries and reviewed Member conversion.",global:[],grants:["VISITOR_VIEW_ALL","VISITOR_VIEW_OWN"] },
  { id:"website",label:"Website",icon:"site",description:"Drafts, public pages, sermons, gallery and publishing.",global:[],grants:["WEBSITE_PAGE_VIEW"] },
  { id:"prayer-requests",label:"Prayer requests",icon:"heart",description:"Private pastoral prayer follow-up.",global:[],grants:["PRAYER_REQUEST_VIEW"] },
  { id: "members", label: "Members", icon: "users", description: "Member records and the people in your church community.", global: ["MEMBERS_VIEW_ALL"], scoped: ["MEMBERS_VIEW_OWN_MINISTRY"] },
  { id: "households", label: "Households", icon: "house", description: "Family relationships and household connections.", global: ["HOUSEHOLD_VIEW_ALL"], grants: ["HOUSEHOLD_VIEW"] },
  { id: "attendance", label: "Attendance", icon: "clipboard", description: "Church services, ministry meetings and attendance records.", global: ["ATTENDANCE_VIEW_ALL"], scoped: ["ATTENDANCE_VIEW_OWN_MINISTRY"] },
  { id: "ministries", label: "Ministries", icon: "network", description: "Ministry membership, offices and church leadership.", global: ["MINISTRIES_VIEW_ALL"], scoped: ["MINISTRIES_VIEW_OWN"] },
  { id: "sunday-school", label: "Sunday School", icon: "book", description: "Your classes, students, teaching and lessons.", global: ["SUNDAY_SCHOOL_VIEW_ALL"], grants: ["SUNDAY_SCHOOL_VIEW"] },
  { id: "sms", label: "Messaging", icon: "message", description: "Stay connected with church and ministry members.", global: ["SMS_VIEW_ALL"], scoped: ["SMS_VIEW_OWN"] },
  { id: "reports", label: "Reports", icon: "chart", description: "Attendance reporting and authorised Sunday School insights.", global: [], grants: ["ATTENDANCE_EXPORT", "SUNDAY_SCHOOL_REPORT_VIEW"] },
  { id: "administration", label: "Administration", icon: "settings", description: "Account administration, software roles and security.", global: [], grants: ["ADMINISTRATION_VIEW", "USER_VIEW", "ROLE_VIEW", "PERMISSION_VIEW", "SECURITY_AUDIT_VIEW"] },
  { id: "finance", label: "Finance", icon: "wallet", description: "Your authorised church finance workspace.", global: [], grants: ["FINANCE_VIEW","DONATIONS_VIEW"] },
  { id: "welfare", label: "Welfare", icon: "heart", description: "Your authorised care and welfare workspace.", global: [], grants: ["WELFARE_VIEW"] },
];
export function hasAny(user: CurrentUser, permissions: readonly string[]): boolean {
  return permissions.some(permission => user.permissions.includes(permission));
}
export function canAccess(user: CurrentUser, module: ModuleDefinition): boolean {
  if (hasAny(user, module.global)) return true;
  if (hasAny(user, module.scoped ?? []) && user.ministry_scopes.length > 0) return true;
  if (module.id === "households") return hasAny(user, module.grants ?? []) && user.member !== null;
  if (module.id === "sunday-school") return hasAny(user, module.grants ?? []) && user.sunday_school_scopes.length > 0;
  if (module.id === "reports") return (hasAny(user, ["ATTENDANCE_EXPORT"]) &&
    (hasAny(user, ["ATTENDANCE_VIEW_ALL"]) || (hasAny(user, ["ATTENDANCE_VIEW_OWN_MINISTRY"]) && user.ministry_scopes.length > 0))) || hasAny(user, ["SUNDAY_SCHOOL_REPORT_VIEW"]);
  return hasAny(user, module.grants ?? []);
}
export function visibleModules(user: CurrentUser): ModuleDefinition[] { return modules.filter(module => canAccess(user, module)); }
export function churchWide(user: CurrentUser): boolean { return hasAny(user, ["MEMBERS_VIEW_ALL", "MINISTRIES_VIEW_ALL", "ATTENDANCE_VIEW_ALL"]); }
