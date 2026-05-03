"use client";

import { cn } from "@/lib/utils";
import { useCountdown, type CountdownUrgency } from "@/hooks/useCountdown";

interface CountdownProps {
  startTime: string;
  status: string;
  className?: string;
}

const URGENCY_STYLES: Record<CountdownUrgency, string> = {
  live: "bg-red-50 text-red-700 ring-1 ring-red-200",
  imminent: "bg-amber-50 text-amber-800 ring-1 ring-amber-200",
  soon: "bg-blue-50 text-blue-700 ring-1 ring-blue-200",
  later: "bg-slate-50 text-slate-600 ring-1 ring-slate-200",
  done: "bg-slate-100 text-slate-500 ring-1 ring-slate-200",
};

export function Countdown({ startTime, status, className }: CountdownProps) {
  const { label, urgency } = useCountdown(startTime, status);
  if (!label) return null;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium tabular-nums",
        URGENCY_STYLES[urgency],
        className
      )}
    >
      {urgency === "live" ? (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
      ) : null}
      {label}
    </span>
  );
}
