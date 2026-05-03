"use client";

import { cn } from "@/lib/utils";
import { BOOKMAKERS } from "@/lib/constants";

/** Uppercase mono kicker label. */
export function Kicker({
  children,
  className,
  tone = "slate",
}: {
  children: React.ReactNode;
  className?: string;
  tone?: "slate" | "emerald" | "red";
}) {
  const colorClass =
    tone === "emerald"
      ? "text-emerald-700"
      : tone === "red"
        ? "text-red-600"
        : "text-slate-500";
  return (
    <div
      className={cn(
        "font-mono text-[10px] font-semibold uppercase tracking-[0.14em]",
        colorClass,
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * Bookmaker chip — neutral slate background with a tiny brand-colored dot.
 * Used wherever a bookmaker is attributed (best-odds cells, filter rows, etc.).
 */
export function BookmakerChip({
  bookmaker,
  size = "sm",
  className,
}: {
  bookmaker: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const meta = BOOKMAKERS[bookmaker];
  if (!meta) return null;
  // The dot uses brand bgColor unless white (Tipos) — fall back to its color.
  const dot = meta.bgColor.toLowerCase() === "#ffffff" ? meta.color : meta.bgColor;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border border-slate-200 bg-slate-50 font-medium text-slate-700",
        size === "sm" ? "rounded-sm px-1.5 py-0.5 text-[10px]" : "rounded-sm px-2.5 py-1 text-[11px]",
        className,
      )}
    >
      <span
        className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ backgroundColor: dot }}
      />
      {meta.displayName}
    </span>
  );
}

/** Bookmaker text token for table rows: small brand-color square + name. */
export function BookmakerName({
  bookmaker,
  className,
}: {
  bookmaker: string;
  className?: string;
}) {
  const meta = BOOKMAKERS[bookmaker];
  if (!meta) return null;
  return (
    <span className={cn("inline-flex items-center gap-2 text-[13px] font-medium text-slate-900", className)}>
      <span
        className="inline-block h-2 w-2 shrink-0 rounded-[2px]"
        style={{ backgroundColor: meta.bgColor }}
      />
      {meta.displayName}
    </span>
  );
}

/** Underline tab — replaces capsule pills everywhere. */
export function Tab({
  active,
  children,
  onClick,
  tone = "slate",
}: {
  active: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  tone?: "slate" | "emerald";
}) {
  const activeColor = tone === "emerald" ? "border-emerald-700 text-emerald-700" : "border-slate-900 text-slate-900";
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "border-b-2 bg-transparent px-0 py-2 text-[13px] transition",
        active ? `font-semibold ${activeColor}` : "border-transparent font-medium text-slate-500 hover:text-slate-700",
      )}
    >
      {children}
    </button>
  );
}

/** Live indicator: red dot + LIVE text. */
export function LiveBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-red-600",
        className,
      )}
    >
      <span className="bm-pulse inline-block h-1.5 w-1.5 rounded-full bg-red-600" />
      LIVE
    </span>
  );
}

/** Margin chip — neutral slate, emerald only when negative (surebet). */
export function MarginChip({ margin, className }: { margin: number; className?: string }) {
  const isSurebet = margin < 0;
  const sign = margin >= 0 ? "+" : "";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 border px-2 py-0.5 font-mono text-[11px] font-semibold tabular-nums",
        isSurebet
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-slate-200 bg-slate-50 text-slate-600",
        className,
      )}
    >
      <span className="text-[9px] uppercase tracking-wider">Marža</span>
      {sign}
      {margin.toFixed(2)}%
    </span>
  );
}
