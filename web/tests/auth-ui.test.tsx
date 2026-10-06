import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/features/auth/auth-provider";
import { PortalGuard } from "@/features/auth/portal-guard";
import { LoginForm } from "@/features/auth/login-form";
import { OtpInput } from "@/features/auth/otp-input";
import { WorkspaceProvider, WorkspaceSelector } from "@/features/workspace/workspace-provider";
import { ApiClient } from "@/lib/api/client";
import { choir, user } from "./fixtures";
import { useState } from "react";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), pathname: "/portal/dashboard", search: "" }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: navigation.replace }), usePathname: () => navigation.pathname, useSearchParams: () => new URLSearchParams(navigation.search) }));
vi.mock("next/image", () => ({ default: ({ priority: _priority, ...props }: React.ImgHTMLAttributes<HTMLImageElement> & { priority?: boolean }) => <img {...props} alt={props.alt ?? ""} /> }));
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

describe("authentication UI and session context", () => {
  it("loads /me centrally before showing protected content", async () => {
    let finish: (value: Response) => void = () => {};
    const fetcher = vi.fn<typeof fetch>(() => new Promise(resolve => { finish = resolve; }));
    render(<AuthProvider client={new ApiClient("http://api.example", fetcher)}><PortalGuard><h1>Protected content</h1></PortalGuard></AuthProvider>);
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    await act(async () => finish(response(user())));
    expect(await screen.findByText("Protected content")).toBeInTheDocument(); expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("redirects an unauthenticated portal visitor without showing protected content", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response({ error: { code: "AUTHENTICATION_REQUIRED" } }, 401));
    render(<AuthProvider client={new ApiClient("http://api.example", fetcher)}><PortalGuard><h1>Private</h1></PortalGuard></AuthProvider>);
    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("Private")).not.toBeInTheDocument();
  });
  it("renders password/authenticator alternatives and signs in through the actual contract", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ error: { code: "AUTHENTICATION_REQUIRED" } }, 401))
      .mockResolvedValueOnce(response({ csrf_token: "a".repeat(64), authenticated: false }))
      .mockResolvedValueOnce(response({ csrf_token: "b".repeat(64), status: "authenticated" }))
      .mockResolvedValueOnce(response(user()));
    render(<AuthProvider client={new ApiClient("http://api.example", fetcher)}><LoginForm /></AuthProvider>);
    const input = screen.getByLabelText("Email or username"); await waitFor(() => expect(input).toBeEnabled());
    await userEvent.type(input, "ama@example.invalid"); await userEvent.type(screen.getByLabelText("Password", { selector: "input" }), "synthetic-password");
    await userEvent.click(screen.getByRole("button", { name: /^Sign in$/ }));
    await waitFor(() => expect(fetcher.mock.calls.some(call => String(call[0]).endsWith("/auth/password-login"))).toBe(true));
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
  });
  it("supports OTP typing, Backspace navigation and complete-code paste", async () => {
    const complete = vi.fn();
    function Control() { const [value, setValue] = useState(""); return <><p id="otp-help">Code</p><OtpInput value={value} onChange={setValue} onComplete={complete} /></>; }
    render(<Control />);
    await userEvent.type(screen.getByLabelText("Digit 1 of 6"), "12");
    expect(screen.getByLabelText("Digit 3 of 6")).toHaveFocus();
    await userEvent.keyboard("{Backspace}"); expect(screen.getByLabelText("Digit 2 of 6")).toHaveFocus();
    await userEvent.click(screen.getByLabelText("Digit 1 of 6")); await userEvent.paste("123456");
    expect(complete).toHaveBeenCalledWith("123456");
  });
  it("sends logout to the backend before clearing the context", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response(user()))
      .mockResolvedValueOnce(response({ csrf_token: "a".repeat(64), authenticated: true }))
      .mockResolvedValueOnce(response({ status: "signed_out" }));
    function Control() { const auth = useAuth(); return <button onClick={() => { void auth.logout(); }}>{auth.user ? "Signed in" : "Signed out"}</button>; }
    render(<AuthProvider client={new ApiClient("http://api.example", fetcher)}><Control /></AuthProvider>);
    await userEvent.click(await screen.findByText("Signed in"));
    expect(await screen.findByText("Signed out")).toBeInTheDocument();
    expect(fetcher.mock.calls.some(call => String(call[0]).endsWith("/auth/logout"))).toBe(true);
  });
  it("limits a multi-scope selector to the scopes returned by /me", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response(user({ ministry_scopes: [user().ministry_scopes[0], choir] })));
    render(<AuthProvider client={new ApiClient("http://api.example", fetcher)}><PortalGuard><WorkspaceProvider><WorkspaceSelector /></WorkspaceProvider></PortalGuard></AuthProvider>);
    const select = await screen.findByLabelText("Current workspace");
    expect(screen.getAllByRole("option")).toHaveLength(2);
    await userEvent.selectOptions(select, choir.id);
    expect(navigation.replace).toHaveBeenCalledWith("/portal/dashboard?ministry=choir-id", { scroll: false });
  });
});
