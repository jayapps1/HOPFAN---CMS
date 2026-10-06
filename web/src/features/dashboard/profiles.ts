import type { CurrentUser } from "@/types/auth";
export type DashboardProfile = "CHURCH_ADMIN" | "CHURCH_SECRETARY" | "GENERAL_OVERSEER" | "MINISTRY_OFFICER" | "SUNDAY_SCHOOL" | "STANDARD_USER";
export const presentations: Record<DashboardProfile, { label: string; title: string; detail: string; priority: string[] }> = {
  CHURCH_ADMIN: { label: "Church administration", title: "Your church, at a glance.", detail: "A connected workspace for the people, ministries and activities you oversee.", priority: ["members", "attendance", "ministries", "sunday-school"] },
  CHURCH_SECRETARY: { label: "Church secretary", title: "Keep your church connected.", detail: "Your place for member records, church attendance and daily coordination.", priority: ["members", "attendance", "reports", "sms"] },
  GENERAL_OVERSEER: { label: "General Overseer", title: "A clear view of the church.", detail: "A strategic workspace for the areas you are authorised to oversee.", priority: ["attendance", "reports", "sunday-school", "ministries"] },
  MINISTRY_OFFICER: { label: "Ministry workspace", title: "Serve your ministry with purpose.", detail: "The people, records and activities of your assigned ministries, together.", priority: ["members", "attendance", "ministries", "reports"] },
  SUNDAY_SCHOOL: { label: "Sunday School", title: "A place to teach. A place to grow.", detail: "Your assigned classes and the learning community you serve.", priority: ["sunday-school", "reports"] },
  STANDARD_USER: { label: "Your workspace", title: "Welcome to your HOPFAN workspace.", detail: "Your church connections and the areas available to your account.", priority: ["households", "administration"] },
};
export function dashboardProfile(user: CurrentUser): DashboardProfile {
  // These roles select presentation only. Every module/action separately checks
  // permissions; a title never grants a capability or a ministry/class scope.
  if (user.roles.some(role => role.code === "GENERAL_OVERSEER")) return "GENERAL_OVERSEER";
  if (user.roles.some(role => role.code === "CHURCH_SECRETARY")) return "CHURCH_SECRETARY";
  return user.dashboard_profile === "STANDARD" ? "STANDARD_USER" : user.dashboard_profile;
}
