"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, CheckCircle2, Clock3, PauseCircle } from "lucide-react";

import { getHealth, type HealthStatus } from "@/lib/api";
import { getBookmakerDisplay } from "@/lib/constants";
import { cn, formatLastUpdated, formatSecondsCompact } from "@/lib/utils";

type Props = {
  initialHealth: HealthStatus;
};

const FRESHNESS_STYLES = {
  fresh: {
    label: "Fresh",
    badgeClass: "bg-emerald-100 text-emerald-700",
    cardClass: "border-emerald-200 bg-emerald-50/70",
    Icon: CheckCircle2,
  },
  aging: {
    label: "Aging",
    badgeClass: "bg-amber-100 text-amber-700",
    cardClass: "border-amber-200 bg-amber-50/70",
    Icon: Clock3,
  },
  stale: {
    label: "Stale",
    badgeClass: "bg-rose-100 text-rose-700",
    cardClass: "border-rose-200 bg-rose-50/70",
    Icon: AlertTriangle,
  },
  idle: {
    label: "Idle",
    badgeClass: "bg-slate-100 text-slate-600",
    cardClass: "border-slate-200 bg-slate-50/80",
    Icon: PauseCircle,
  },
} as const;

function getFreshnessStyle(freshness: string) {
  return FRESHNESS_STYLES[freshness as keyof typeof FRESHNESS_STYLES] ?? FRESHNESS_STYLES.idle;
}

export function ScrapeHealthPanel({ initialHealth }: Props) {
  const { data = initialHealth, error } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    initialData: initialHealth,
    refetchInterval: 30_000,
  });

  const scraperEntries = Object.entries(data.scrapers);
  const freshCount = scraperEntries.filter(([, scraper]) => scraper.freshness === "fresh").length;
  const staleCount = scraperEntries.filter(([, scraper]) => scraper.freshness === "stale").length;

  return (
    <section className="rounded-[1.9rem] border border-slate-200 bg-white px-6 py-6 shadow-[0_18px_45px_-32px_rgba(15,23,42,0.45)] sm:px-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
            <Activity className="h-3.5 w-3.5" />
            Scrape health
          </div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">
            Bookmaker freshness
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            This shows when each scraper last produced checked data, compared with its own scrape cadence.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <StatPill label="API" value={data.status} tone={data.status === "ok" ? "good" : "warn"} />
          <StatPill label="DB" value={data.db} tone={data.db === "connected" ? "good" : "warn"} />
          <StatPill label="Fresh" value={String(freshCount)} tone="good" />
          <StatPill label="Stale" value={String(staleCount)} tone={staleCount > 0 ? "warn" : "neutral"} />
        </div>
      </div>

      {error ? (
        <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Health auto-refresh failed. Showing the last successful snapshot.
        </div>
      ) : null}

      <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {scraperEntries.map(([bookmaker, scraper]) => {
          const bookmakerData = getBookmakerDisplay(bookmaker);
          const style = getFreshnessStyle(scraper.freshness);
          const Icon = style.Icon;

          return (
            <article
              key={bookmaker}
              className={cn(
                "rounded-2xl border px-4 py-4 transition-colors",
                style.cardClass
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div
                    className="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold"
                    style={{
                      backgroundColor: bookmakerData.bgColor,
                      color: bookmakerData.color,
                    }}
                  >
                    {bookmakerData.displayName}
                  </div>
                  <p className="mt-3 text-sm font-medium text-slate-500">Configured cadence</p>
                  <p className="mt-1 text-lg font-semibold text-slate-950">
                    every {formatSecondsCompact(scraper.interval_seconds)}
                  </p>
                </div>

                <div className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold", style.badgeClass)}>
                  <Icon className="h-3.5 w-3.5" />
                  {style.label}
                </div>
              </div>

              <div className="mt-4 space-y-2 text-sm text-slate-600">
                <p>
                  {scraper.last_scraped_at
                    ? `Last checked ${formatLastUpdated(scraper.last_scraped_at)}`
                    : "No checked odds saved yet"}
                </p>
                <p className="text-slate-500">
                  {scraper.age_seconds !== null && scraper.age_seconds !== undefined
                    ? `Current age ${formatSecondsCompact(scraper.age_seconds)}`
                    : "Waiting for first successful save"}
                </p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function StatPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "good" | "warn" | "neutral";
}) {
  const tones = {
    good: "bg-emerald-50 text-emerald-700",
    warn: "bg-amber-50 text-amber-700",
    neutral: "bg-slate-100 text-slate-700",
  } as const;

  return (
    <div className={cn("rounded-full px-3 py-1.5 text-sm font-semibold", tones[tone])}>
      <span className="mr-2 text-xs uppercase tracking-[0.18em] opacity-70">{label}</span>
      {value}
    </div>
  );
}
