"use client";
import { createContext, useContext, useState, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/features/auth/auth-provider";
import { churchWide, hasAny } from "@/lib/permissions";
import { useResource } from "./use-resource";
import { parseOptions, type Summary } from "@/lib/api/workspace";
import { parseAttendanceOptions, parseClassOptions, loadClassOptions } from "@/lib/api/operations";

interface WorkspaceContextValue {
  ministry: Summary | null; schoolClass: Summary | null;
  schoolMode: boolean; global: boolean; options: Summary[];
  invalid: boolean;
  ministryId: string | null;
  classId: string | null;
  choose: (id: string) => void;
}
const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth(); const pathname = usePathname(); const search = useSearchParams(); const router = useRouter();
  const [ministryId, setMinistryId] = useState<string | null>(null); const [classId, setClassId] = useState<string | null>(null);
  const globalOptions = useResource(user?.permissions.includes("MEMBERS_VIEW_ALL") ? "/api/v1/members/options" : null, parseOptions);
  const attendanceMode = pathname.startsWith("/portal/attendance");
  const attendanceOptions = useResource(user && attendanceMode ? "/api/v1/attendance/options" : null, parseAttendanceOptions);
  const schoolOptions = useResource(user && pathname.startsWith("/portal/sunday-school") ? "/api/v1/sunday-school/options" : null, parseClassOptions, loadClassOptions);
  if (!user) return null;
  const ministryQuery = search.get("ministry"); const classQuery = search.get("schoolClass");
  const globalMinistry = attendanceMode ? hasAny(user, ["ATTENDANCE_VIEW_ALL"]) : churchWide(user); const globalSchool = hasAny(user, ["SUNDAY_SCHOOL_VIEW_ALL"]);
  const ministryOptions = attendanceMode ? attendanceOptions.data?.ministries ?? user.ministry_scopes : globalOptions.data ?? user.ministry_scopes;
  const classOptions = schoolOptions.data?.items ?? user.sunday_school_scopes;
  const invalid = (ministryQuery && !globalMinistry && !user.ministry_scopes.some(scope => scope.id === ministryQuery)) ||
    (classQuery && !globalSchool && !user.sunday_school_scopes.some(scope => scope.id === classQuery));
  const ministry = ministryOptions.find(scope => scope.id === (ministryQuery ?? ministryId)) ?? (globalMinistry ? null : user.ministry_scopes[0] ?? null);
  const schoolClass = classOptions.find(scope => scope.id === (classQuery ?? classId)) ?? (globalSchool ? null : classOptions[0] ?? null);
  const schoolMode = pathname.startsWith("/portal/sunday-school") || pathname === "/portal/dashboard" && user.dashboard_profile === "SUNDAY_SCHOOL";
  const global = schoolMode ? globalSchool : globalMinistry;
  const options = schoolMode ? classOptions : ministryOptions;
  const choose = (id: string) => {
    if (id !== "global" && !options.some(scope => scope.id === id)) return;
    if (id === "global" && !global) return;
    const params = new URLSearchParams(search.toString()); const key = schoolMode ? "schoolClass" : "ministry";
    params.delete("page");
    if (id === "global") params.delete(key); else params.set(key, id);
    if (schoolMode) setClassId(id === "global" ? null : id); else setMinistryId(id === "global" ? null : id);
    router.replace(pathname + (params.size ? `?${params.toString()}` : ""), { scroll: false });
  };
  return <WorkspaceContext.Provider value={{ ministry, ministryId: ministryQuery ?? ministry?.id ?? null, classId: classQuery ?? schoolClass?.id ?? null, schoolClass, schoolMode, global, options, choose, invalid: !!invalid }}>
    {children}
  </WorkspaceContext.Provider>;
}
export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("WorkspaceProvider is required");
  return value;
}
export function WorkspaceSelector() {
  const workspace = useWorkspace(); const selected = workspace.schoolMode ? workspace.schoolClass : workspace.ministry;
  const label = workspace.schoolMode ? "Class workspace" : "Current workspace";
  if (workspace.options.length + Number(workspace.global) <= 1) return <div className="workspace-label"><small>{label}</small>
    <strong>{selected?.name ?? (workspace.global ? workspace.schoolMode ? "All Sunday School classes" : "Church-wide" : "Your account")}</strong></div>;
  return <label className="workspace-selector"><small>{label}</small><select aria-label={label} value={selected?.id ?? "global"} onChange={event => workspace.choose(event.target.value)}>
    {workspace.global && <option value="global">{workspace.schoolMode ? "All Sunday School classes" : "Church-wide"}</option>}
    {workspace.options.map(scope => <option key={scope.id} value={scope.id}>{scope.name}</option>)}
  </select></label>;
}
