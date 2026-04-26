"use client";

import { AlertTriangle, CheckCircle2, Clock3, PauseCircle } from "lucide-react";

import { cn, formatSecondsCompact, type FreshnessState } from "@/lib/utils";

type Props = {
  freshness: FreshnessState;
  ageSeconds?: number | null;
  className?: string;
};

const STYLES = {
  fresh: {
    label: "Fresh",
    className: "bg-emerald-100 text-emerald-700",
    Icon: CheckCircle2,
  },
  aging: {
    label: "Aging",
    className: "bg-amber-100 text-amber-700",
    Icon: Clock3,
  },
  stale: {
    label: "Stale",
    className: "bg-rose-100 text-rose-700",
    Icon: AlertTriangle,
  },
  idle: {
    label: "Idle",
    className: "bg-slate-100 text-slate-600",
    Icon: PauseCircle,
  },
} as const;

export function FreshnessBadge({ freshness, ageSeconds, className }: Props) {
  const config = STYLES[freshness] ?? STYLES.idle;
  const Icon = config.Icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-[11px] font-semibold",
        config.className,
        className
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      <span>{config.label}</span>
      {ageSeconds !== null && ageSeconds !== undefined ? (
        <span className="opacity-75">{formatSecondsCompact(ageSeconds)}</span>
      ) : null}
    </span>
  );
}
