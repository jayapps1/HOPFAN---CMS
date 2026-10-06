import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";
import { LoaderCircle } from "lucide-react";

export function Button({ children, variant = "primary", pending = false, className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost"; pending?: boolean }) {
  return <button className={`button button-${variant} ${className}`} {...props} disabled={props.disabled || pending} aria-busy={pending || undefined}>
    {pending && <LoaderCircle className="spin" size={17} aria-hidden="true" />}{children}
  </button>;
}
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(props, ref) {
  return <input {...props} ref={ref} className={`input ${props.className ?? ""}`} />;
});
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) { return <section className={`card ${className}`}>{children}</section>; }
export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "green" | "blue" }) { return <span className={`badge badge-${tone}`}>{children}</span>; }
export function Avatar({ name }: { name: string }) { return <span className="avatar" aria-hidden="true">{name.split(/\s+/).slice(0, 2).map(word => word[0]).join("").toUpperCase()}</span>; }
