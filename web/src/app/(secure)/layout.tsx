import { AuthProvider } from "@/features/auth/auth-provider";
import type { ReactNode } from "react";
import type { Metadata } from "next";
export const metadata: Metadata = { robots: { index: false, follow: false } };
export default function SecureLayout({ children }: { children: ReactNode }) { return <AuthProvider>{children}</AuthProvider>; }
