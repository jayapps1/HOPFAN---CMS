import { describe, expect, it } from "vitest";
import { visibleModules } from "@/lib/permissions";
import { dashboardProfile } from "@/features/dashboard/profiles";
import { choir, user, youth } from "./fixtures";

describe("presentation and permission boundaries", () => {
  it("shows only ministry modules with actual grants and assigned scopes", () => {
    expect(visibleModules(user()).map(module => module.id)).toEqual(["members", "attendance", "ministries"]);
    expect(visibleModules(user({ ministry_scopes: [] }))).toEqual([]);
  });
  it("allows global permissions without fake scope assignments", () => {
    expect(visibleModules(user({ permissions: ["MEMBERS_VIEW_ALL", "ATTENDANCE_VIEW_ALL"], ministry_scopes: [] })).map(module => module.id)).toEqual(["members", "attendance"]);
  });
  it("does not give a secretary finance or user administration through a title", () => {
    const secretary = user({ roles: [{ code: "CHURCH_SECRETARY", name: "Church Secretary" }] });
    expect(dashboardProfile(secretary)).toBe("CHURCH_SECRETARY");
    expect(visibleModules(secretary).map(module => module.id)).not.toContain("finance");
    expect(visibleModules(secretary).map(module => module.id)).not.toContain("administration");
  });
  it("uses Overseer presentation without granting permissions", () => {
    const overseer = user({ roles: [{ code: "GENERAL_OVERSEER", name: "General Overseer" }], permissions: [], ministry_scopes: [] });
    expect(dashboardProfile(overseer)).toBe("GENERAL_OVERSEER"); expect(visibleModules(overseer)).toEqual([]);
  });
  it("uses school scopes without showing unrelated member or ministry access", () => {
    const teacher = user({ dashboard_profile: "SUNDAY_SCHOOL", permissions: ["SUNDAY_SCHOOL_VIEW"], ministry_scopes: [], sunday_school_scopes: [youth] });
    expect(visibleModules(teacher).map(module => module.id)).toEqual(["sunday-school"]);
  });
  it("handles multiple assigned scopes without a special Youth rule", () => {
    expect(visibleModules(user({ ministry_scopes: [choir, youth] }))).toHaveLength(3);
  });
});
