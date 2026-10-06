"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowRight, Eye, EyeOff, KeyRound, LockKeyhole, ShieldCheck, X } from "lucide-react";
import { useAuth } from "./auth-provider";
import { OtpInput } from "./otp-input";
import { api, ApiError } from "@/lib/api/client";
import { ThemeControl } from "@/components/theme-provider";
import { Button, Input } from "@/components/ui/primitives";
import { ErrorMessage } from "@/components/ui/feedback";
import type { LoginMethod } from "@/types/auth";

export function LoginForm() {
  const auth = useAuth(); const router = useRouter(); const params = useSearchParams();
  const [method, setMethod] = useState<LoginMethod>("password");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [code, setCode] = useState("");
  const [visible, setVisible] = useState(false); const [pending, setPending] = useState(false); const [error, setError] = useState("");
  const [connectionFailed, setConnectionFailed] = useState(false);
  const submitting = useRef(false);
  useEffect(() => { if (auth.status === "authenticated") router.replace("/portal/dashboard"); }, [auth.status, router]);
  const choose = (next: LoginMethod) => { if (pending) return; setMethod(next); setPassword(""); setCode(""); setError(""); };
  const submit = async (credential = method === "password" ? password : code) => {
    if (submitting.current || auth.status === "loading") return;
    if (!email.trim()) { setError("Enter your email or username first."); return; }
    if (!credential || method === "totp" && !/^[0-9]{6}$/.test(credential)) { setError("Enter your sign-in details."); return; }
    submitting.current = true; setPending(true); setError(""); setConnectionFailed(false);
    try { await auth.login(method, email.trim(), credential); setPassword(""); setCode(""); router.replace("/portal/dashboard"); }
    catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Unable to sign in. Please try again.");
      if (failure instanceof ApiError && failure.code === "NETWORK_ERROR")
        setConnectionFailed(!(await api.connectivity()));
      setPassword(""); if (method === "totp") setCode("");
    } finally { submitting.current = false; setPending(false); }
  };
  const onSubmit = (event: FormEvent) => { event.preventDefault(); void submit(); };
  const locked = pending || auth.status === "loading";
  const expired = auth.expired || params.get("reason") === "expired";
  return <main className="login-page"><div className="login-surface">
    <aside className="brand-panel" aria-label="HOPFAN church identity">
      <div className="brand-orbit orbit-one" aria-hidden="true" /><div className="brand-orbit orbit-two" aria-hidden="true" />
      <a className="brand-heading" href="/login"><span className="logo-tile"><Image src="/brand/hopfan-logo.png" alt="HOPFAN official church logo" width={65} height={69} priority /></span>
        <span><strong>HOPFAN</strong><small>HOUSE OF PRAYER FOR ALL NATIONS</small></span></a>
      <div className="brand-message"><span className="brand-eyebrow">NO JESUS CHRIST. NO LIFE.</span>
        <h1>Connected<br />in faith.<br /><span>United in service.</span></h1>
        <p>A trusted workspace for our church community.<br className="desktop-break" /> Everything you need to serve, organise and lead.</p>
        <div className="brand-rule"><span /><span /><span /></div>
      </div>
      <div className="brand-footer"><ShieldCheck size={20} aria-hidden="true" /><span>House of Prayer for All Nations<br /><small>Church Management Platform</small></span></div>
    </aside>
    <section className="sign-in-panel" aria-labelledby="sign-in-title">
      <div className="login-theme"><ThemeControl /></div>
      <div className="sign-in-content">
        <span className="secure-label"><LockKeyhole size={14} aria-hidden="true" /> SECURE PORTAL</span>
        <h2 id="sign-in-title">Welcome back</h2><p className="login-description">Sign in to your HOPFAN workspace.</p>
        {expired && <div className="info-message" role="status">Your session expired. Please sign in again.</div>}
        {auth.status === "unavailable" && <div className="info-message" role="status">HOPFAN couldn’t be reached. You can try signing in again.</div>}
        <div className="login-tabs" role="tablist" aria-label="Sign-in method">
          {(["password", "totp"] as const).map(item => <button type="button" role="tab" id={`tab-${item}`} key={item}
            aria-selected={method === item} aria-controls="login-panel" tabIndex={method === item ? 0 : -1} disabled={pending}
            onClick={() => choose(item)} onKeyDown={event => { if (["ArrowRight", "ArrowLeft"].includes(event.key)) { event.preventDefault(); choose(method === "password" ? "totp" : "password"); document.getElementById(`tab-${method === "password" ? "totp" : "password"}`)?.focus(); } }}>
            {item === "password" ? <KeyRound size={16} aria-hidden="true" /> : <ShieldCheck size={16} aria-hidden="true" />}
            {item === "password" ? "Password" : "Authenticator"}
          </button>)}
        </div>
        <form onSubmit={onSubmit} id="login-panel" role="tabpanel" aria-labelledby={`tab-${method}`}>
          <div className="field"><label htmlFor="email">Email or username</label>
            <Input id="email" name="email" type="text" inputMode="email" autoComplete="username" placeholder="Your email or username"
              required maxLength={254} value={email} disabled={locked} onChange={event => setEmail(event.target.value)} />
          </div>
          {method === "password" ? <div className="field"><label htmlFor="password">Password</label>
            <div className="password-field"><Input id="password" name="password" type={visible ? "text" : "password"} autoComplete="current-password"
              placeholder="Enter your password" required maxLength={4096} value={password} disabled={locked} onChange={event => setPassword(event.target.value)} aria-describedby={error ? "login-error" : undefined} />
              <button type="button" className="password-toggle" aria-label={visible ? "Hide password" : "Show password"} disabled={locked} onClick={() => setVisible(!visible)}>
                {visible ? <EyeOff size={19} aria-hidden="true" /> : <Eye size={19} aria-hidden="true" />}</button>
            </div></div> : <fieldset className="field otp-field"><legend>Authenticator code</legend>
            <OtpInput value={code} onChange={setCode} onComplete={value => { void submit(value); }} disabled={locked} invalid={!!error} />
            <p id="otp-help" className="field-help">Enter the six-digit code from your authenticator app. You can paste all six digits.</p>
          </fieldset>}
          <div className="login-error-slot">{error && <ErrorMessage message={error} id="login-error" />}
          {connectionFailed && <div className="connection-retry"><span>Server unavailable</span><Button type="button" variant="ghost" onClick={async()=>{
            const reachable=await api.connectivity();setConnectionFailed(!reachable);
            if(reachable){setError("");void auth.refresh();}
          }}>Retry connection</Button></div>}</div>
          {method === "password" && <Dialog.Root><Dialog.Trigger asChild><button type="button" className="text-button forgot-link">Forgot password?</button></Dialog.Trigger>
            <Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog-content">
              <Dialog.Title>Help signing in</Dialog.Title><Dialog.Description>Contact your church administrator for help recovering your account. You can also use the password recovery option in the HOPFAN desktop application.</Dialog.Description>
              <Dialog.Close asChild><Button variant="secondary">Close</Button></Dialog.Close><Dialog.Close className="dialog-close" aria-label="Close help"><X size={19} /></Dialog.Close>
            </Dialog.Content></Dialog.Portal></Dialog.Root>}
          <Button type="submit" className="sign-in-button" pending={pending} disabled={auth.status === "loading"}>
            {pending ? "Signing in…" : "Sign in"}{!pending && <ArrowRight size={17} aria-hidden="true" />}
          </Button>
        </form>
        <p className="login-support">Need access? Contact your church administrator.</p>
      </div>
      <footer className="login-footer"><LockKeyhole size={13} aria-hidden="true" /><span>Your account. Your authorised workspace.</span><span>HOPFAN</span></footer>
    </section>
  </div></main>;
}
