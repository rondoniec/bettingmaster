"use client";

import { cn } from "@/lib/utils";
import { useCountdown, type CountdownUrgency } from "@/hooks/useCountdown";

interface CountdownProps {
  startTime: string;
  status: string;
  className?: string;
}

const URGENCY_STYLES: Record<CountdownUrgency, string> = {
  live: "border-red-200 text-red-600",
  imminent: "border-amber-200 text-amber-700",
  soon: "border-slate-200 text-slate-700",
  later: "border-slate-200 text-slate-500",
  done: "border-slate-200 text-slate-400",
};

export function Countdown({ startTime, status, className }: CountdownProps) {
  const { label, urgency } = useCountdown(startTime, status);
  if (!label) return null;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 border bg-white px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider tabular-nums",
        URGENCY_STYLES[urgency],
        className,
      )}
    >
      {urgency === "live" ? (
        <span className="bm-pulse inline-block h-1.5 w-1.5 rounded-full bg-red-600" />
      ) : null}
      {label}
    </span>
  );
}
