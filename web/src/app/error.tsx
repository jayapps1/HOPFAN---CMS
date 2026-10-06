"use client";
import { ServiceUnavailable } from "@/components/ui/feedback";
export default function ErrorPage({ reset }: { reset: () => void }) { return <ServiceUnavailable onRetry={reset} />; }
