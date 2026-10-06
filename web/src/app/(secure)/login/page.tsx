import { Suspense } from "react";
import type { Metadata } from "next";
import { LoginForm } from "@/features/auth/login-form";
import { SessionLoading } from "@/components/ui/feedback";
export const metadata: Metadata = { title: "Sign in" };
export default function Login() { return <Suspense fallback={<SessionLoading />}><LoginForm /></Suspense>; }
