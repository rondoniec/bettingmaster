"use client";

import { cn, formatSecondsCompact, type FreshnessState } from "@/lib/utils";

type Props = {
  freshness: FreshnessState;
  ageSeconds: number | null;
  className?: string;
};

const STYLES: Record<FreshnessState, { label: string; cls: string }> = {
  fresh:  { label: "Aktuálne",  cls: "border-emerald-200 text-emerald-700" },
  aging:  { label: "Starnúce",  cls: "border-amber-200 text-amber-700" },
  stale:  { label: "Zastaralé", cls: "border-red-200 text-red-600" },
  idle:   { label: "Nečinné",   cls: "border-slate-200 text-slate-500" },
};

export function FreshnessBadge({ freshness, ageSeconds, className }: Props) {
  const config = STYLES[freshness] ?? STYLES.idle;
  const ageLabel =
    ageSeconds !== null && ageSeconds !== undefined ? formatSecondsCompact(ageSeconds) : null;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border bg-white px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider tabular-nums",
        config.cls,
        className,
      )}
    >
      {config.label}
      {ageLabel ? <span className="text-slate-400">{ageLabel}</span> : null}
    </span>
  );
}
