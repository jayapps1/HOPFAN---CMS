"use client";
import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";

export function OtpInput({ value, onChange, onComplete, disabled, invalid = false }:
  { value: string; onChange: (value: string) => void; onComplete: (value: string) => void; disabled?: boolean; invalid?: boolean }) {
  const fields = useRef<(HTMLInputElement | null)[]>([]);
  const digits = Array.from({ length: 6 }, (_, index) => value[index] ?? "");
  const update = (incoming: string, index: number) => {
    const clean = incoming.replace(/[^0-9]/g, "");
    let next = [...digits];
    if (clean.length > 1) next = Array.from({ length: 6 }, (_, offset) => clean[offset] ?? "");
    else if (!clean) next = next.map((digit, offset) => offset < index ? digit : "");
    else next[index] = clean;
    const code = next.join(""); onChange(code);
    if (clean) fields.current[Math.min(clean.length > 1 ? clean.length - 1 : index + 1, 5)]?.focus();
    if (next.every(digit => /^[0-9]$/.test(digit))) onComplete(code);
  };
  const paste = (event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault(); update(event.clipboardData.getData("text"), 0);
  };
  const key = (event: KeyboardEvent<HTMLInputElement>, index: number) => {
    if (event.key === "Backspace" && !digits[index] && index > 0) {
      event.preventDefault(); const next = [...digits]; next[index - 1] = ""; onChange(next.join("")); fields.current[index - 1]?.focus();
    } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault(); fields.current[Math.max(0, Math.min(5, index + (event.key === "ArrowLeft" ? -1 : 1)))]?.focus();
    }
  };
  return <div className="otp-fields" role="group" aria-label="Six-digit authenticator code">
    {digits.map((digit, index) => <input key={index} ref={field => { fields.current[index] = field; }}
      aria-label={`Digit ${index + 1} of 6`} aria-describedby="otp-help login-error" aria-invalid={invalid || undefined}
      type="text" inputMode="numeric" pattern="[0-9]*" autoComplete={index === 0 ? "one-time-code" : "off"}
      name={`otp-digit-${index}`} maxLength={6} value={digit} disabled={disabled} className="otp-digit"
      onFocus={event => event.target.select()} onChange={event => update(event.target.value, index)} onPaste={paste} onKeyDown={event => key(event, index)} />)}
  </div>;
}
