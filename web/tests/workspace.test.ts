import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "@/lib/api/client";
import { parseMembers, parseMemberDetail, parseDashboard } from "@/lib/api/workspace";
const member = { id: "00000000-0000-4000-8000-000000000001", member_no: "TEST-1", full_name: "Synthetic Person", gender: "FEMALE", phone: "", photo_url: null, status: "ACTIVE", ministries: [] };
describe("business API response contracts", () => {
  it("projects safe member fields and rejects malformed counts", () => {
    const data = parseMembers({ items: [{ ...member, photo_path: "PRIVATE-SENTINEL", notes: "PRIVATE-SENTINEL" }], page: 1, page_size: 25, total: 1, pages: 1 });
    expect(JSON.stringify(data)).not.toContain("PRIVATE-SENTINEL");
    expect(() => parseMembers({ ...data, total: "1" })).toThrow();
  });
  it("omits profile sections not provided by the authorized server", () => {
    const data = parseMemberDetail({ ...member, identity: { first_name: "Synthetic", middle_name: "", last_name: "Person", date_of_birth: "", marital_status: "" },
      contact: { phone: "", alternate_phone: "", email: "", address: "" }, membership: { date_joined: "", baptized: false, baptism_date: "" }, welfare_notes: "PRIVATE-SENTINEL" });
    expect(data.household).toBeUndefined(); expect(data.sunday_school).toBeUndefined();
    expect(JSON.stringify(data)).not.toContain("PRIVATE-SENTINEL");
  });
  it("accepts omitted nullable profile fields from the API projection", () => {
    const data = parseMemberDetail({ ...member, photo_url: undefined,
      identity: { first_name: "Synthetic", middle_name: "", last_name: "Person", date_of_birth: "", marital_status: "" },
      contact: { phone: "", alternate_phone: "", email: "", address: "" }, membership: { date_joined: "", baptized: false, baptism_date: "" },
      leadership: [{ id: "appointment", ministry_id: "ministry", ministry_name: "Youth", member_id: member.id,
        full_name: member.full_name, member_no: member.member_no, position_id: "position", position_name: "Mentor", position_code: "MENTOR",
        is_leadership: true, is_current: true, start_date: "2026-01-01" }] });
    expect(data.photo_url).toBeNull(); expect(data.leadership?.[0].end_date).toBeNull();
  });
  it("accepts actual zero counts and explicit unavailable metrics", () => {
    expect(parseDashboard({ scope: "all", metrics: [{ key: "members", label: "Members", value: 0, detail: "" }], recent_members: [], unavailable: ["School"] }).metrics[0].value).toBe(0);
  });
  it("fetches authenticated no-store data, signals cancellation and handles permission failures", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ error: { code: "ACCESS_DENIED", message: "PRIVATE-SENTINEL" } }), { status: 403 }));
    const client = new ApiClient("http://localhost:8000", fetcher); const controller = new AbortController();
    await expect(client.get("/api/v1/members", parseMembers, controller.signal)).rejects.toMatchObject({ status: 403, message: "You do not have permission to access this area." });
    expect(fetcher.mock.calls[0][1]).toMatchObject({ credentials: "include", cache: "no-store" });
    expect(fetcher.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal);
    expect(client.photoUrl("/etc/passwd")).toBe("");
  });
});
