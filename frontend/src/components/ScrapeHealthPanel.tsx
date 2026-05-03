"use client";

import { useQuery } from "@tanstack/react-query";

import { BookmakerName, Kicker } from "@/components/Primitives";
import { getHealth, type HealthStatus } from "@/lib/api";
import { cn, formatSecondsCompact } from "@/lib/utils";

type Props = {
  initialHealth: HealthStatus;
};

const FRESHNESS_LABEL: Record<string, { label: string; cls: string }> = {
  fresh: { label: "Aktuálne", cls: "border-emerald-200 text-emerald-700" },
  aging: { label: "Starnúce", cls: "border-amber-200 text-amber-700" },
  stale: { label: "Zastaralé", cls: "border-red-200 text-red-600" },
  idle:  { label: "Nečinné",   cls: "border-slate-200 text-slate-500" },
};

export function ScrapeHealthPanel({ initialHealth }: Props) {
  const { data = initialHealth, error } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    initialData: initialHealth,
    refetchInterval: 30_000,
  });

  const scraperEntries = Object.entries(data.scrapers);
  const freshCount = scraperEntries.filter(([, s]) => s.freshness === "fresh").length;
  const staleCount = scraperEntries.filter(([, s]) => s.freshness === "stale").length;

  return (
    <section className="border border-slate-200 bg-white">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div>
          <Kicker>Scrape health</Kicker>
          <h2 className="mt-1 text-base font-semibold text-slate-900">Stav stávkových kancelárií</h2>
        </div>
        <div className="flex flex-wrap gap-2 font-mono text-[11px] uppercase tracking-wider tabular-nums">
          <Stat label="API" value={data.status === "ok" ? "ok" : "warn"} tone={data.status === "ok" ? "good" : "warn"} />
          <Stat label="DB" value={data.db === "connected" ? "ok" : "err"} tone={data.db === "connected" ? "good" : "warn"} />
          <Stat label="Aktuálne" value={String(freshCount)} tone="good" />
          <Stat label="Zastaralé" value={String(staleCount)} tone={staleCount > 0 ? "warn" : "neutral"} />
        </div>
      </header>

      {error ? (
        <div className="border-b border-amber-200 bg-amber-50 px-5 py-3 font-mono text-[11px] text-amber-800">
          Health auto-refresh failed. Showing the last successful snapshot.
        </div>
      ) : null}

      <div className="grid gap-px bg-slate-100 sm:grid-cols-2 lg:grid-cols-3">
        {scraperEntries.map(([bookmaker, scraper]) => {
          const fresh = FRESHNESS_LABEL[scraper.freshness] ?? FRESHNESS_LABEL.idle;
          return (
            <article key={bookmaker} className="bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <BookmakerName bookmaker={bookmaker} />
                <span
                  className={cn(
                    "inline-flex items-center gap-1 border bg-white px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider",
                    fresh.cls,
                  )}
                >
                  {fresh.label}
                </span>
              </div>
              <div className="mt-3 space-y-1 font-mono text-[11px] tabular-nums">
                <p className="text-slate-500">
                  <span className="text-slate-400">Cadence</span>{" "}
                  <span className="text-slate-700">každé {formatSecondsCompact(scraper.interval_seconds)}</span>
                </p>
                <p className="text-slate-500">
                  <span className="text-slate-400">Last checked</span>{" "}
                  <span className="text-slate-700">
                    {scraper.age_seconds !== null && scraper.age_seconds !== undefined
                      ? `pred ${formatSecondsCompact(scraper.age_seconds)}`
                      : "—"}
                  </span>
                </p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "good" | "warn" | "neutral";
}) {
  const cls =
    tone === "good"
      ? "border-emerald-200 text-emerald-700"
      : tone === "warn"
        ? "border-amber-200 text-amber-700"
        : "border-slate-200 text-slate-600";
  return (
    <span className={cn("inline-flex items-center gap-1.5 border px-2 py-0.5", cls)}>
      <span className="text-slate-400">{label}</span>
      <span>{value}</span>
    </span>
  );
}
