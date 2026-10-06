import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "@/lib/api/client";
import { user } from "./fixtures";

const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
const csrf = (letter: string) => ({ csrf_token: letter.repeat(64), authenticated: false });
describe("API contracts and browser security", () => {
  it("uses cookie credentials and refreshes a rejected CSRF token once", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response(csrf("a")))
      .mockResolvedValueOnce(response({ error: { code: "CSRF_INVALID", message: "private raw detail" } }, 403))
      .mockResolvedValueOnce(response(csrf("b")))
      .mockResolvedValueOnce(response({ status: "authenticated", csrf_token: "c".repeat(64) }))
      .mockResolvedValueOnce(response(user()));
    const api = new ApiClient("http://api.example", fetcher);
    expect((await api.login("password", "ama@example.invalid", "synthetic-password")).username).toBe("ama");
    expect(fetcher).toHaveBeenCalledTimes(5);
    for (const [, options] of fetcher.mock.calls) expect(options?.credentials).toBe("include");
    expect(fetcher.mock.calls[1][1]?.headers).toMatchObject({ "X-CSRF-Token": "a".repeat(64) });
    expect(fetcher.mock.calls[3][1]?.headers).toMatchObject({ "X-CSRF-Token": "b".repeat(64) });
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
  });
  it("deduplicates concurrent current-user bootstrap requests", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response(user()));
    const api = new ApiClient("http://api.example", fetcher);
    const [first, second] = await Promise.all([api.currentUser(), api.currentUser()]);
    expect(first).toEqual(second); expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("expires authenticated state on 401 and does not expire it for wrong login credentials", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ error: { code: "AUTHENTICATION_REQUIRED" } }, 401))
      .mockResolvedValueOnce(response(csrf("a"))).mockResolvedValueOnce(response({ error: { code: "INVALID_CREDENTIALS", message: "raw database path" } }, 401));
    const api = new ApiClient("http://api.example", fetcher); const expired = vi.fn(); api.onUnauthorized(expired);
    await expect(api.currentUser()).rejects.toMatchObject({ status: 401 });
    expect(expired).toHaveBeenCalledTimes(1);
    await expect(api.login("password", "ama", "synthetic-password")).rejects.toMatchObject({ message: "Invalid email or password." });
    expect(expired).toHaveBeenCalledTimes(1);
  });
  it("strips unexpected private fields and uses generic messages for raw server failures", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ ...user(), password_hash: "PRIVATE-SENTINEL", totp_secret: "PRIVATE-SENTINEL" }))
      .mockResolvedValueOnce(response({ error: { code: "SQL_EXCEPTION", message: "PRIVATE-SENTINEL" } }, 500));
    const api = new ApiClient("http://api.example", fetcher);
    expect(JSON.stringify(await api.currentUser())).not.toContain("PRIVATE-SENTINEL");
    await expect(api.currentUser()).rejects.toMatchObject({ message: "HOPFAN encountered a server error. Please try again." });
  });
  it("does not claim logout succeeded after a backend failure", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response(csrf("a"))).mockResolvedValueOnce(response({}, 503));
    await expect(new ApiClient("http://api.example", fetcher).logout()).rejects.toBeInstanceOf(ApiError);
  });
  it("reports a safe timeout without raw network details", async () => {
    const fetcher = vi.fn<typeof fetch>((_url, options) => new Promise((_resolve, reject) => {
      options?.signal?.addEventListener("abort", () => reject(new Error("PRIVATE-NETWORK-SENTINEL")));
    }));
    await expect(new ApiClient("http://api.example", fetcher, 10).currentUser()).rejects.toMatchObject({ code: "REQUEST_TIMEOUT" });
  });
});
