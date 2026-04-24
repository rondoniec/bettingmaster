"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Database, RefreshCw, TriangleAlert, XCircle } from "lucide-react";

import { checkHealth, type HealthResponse, type ScraperHealthStatus } from "@/lib/api";
import { BOOKMAKER_ORDER, getBookmakerDisplay } from "@/lib/constants";
import { cn, formatLastUpdated } from "@/lib/utils";

const REFRESH_INTERVAL_MS = 30_000;

const EMPTY_STATUS: ScraperHealthStatus = {
  last_scraped_at: null,
  last_run_at: null,
  last_success_at: null,
  last_failure_at: null,
  last_status: null,
  matches_found: 0,
  odds_saved: 0,
  last_error: null,
};

function formatRelativeTime(value: string | null) {
  return value ? formatLastUpdated(value) : "Never";
}

function statusStyles(status: string | null) {
  switch (status) {
    case "success":
      return {
        badge: "bg-emerald-100 text-emerald-700",
        border: "border-emerald-200",
        icon: <CheckCircle2 className="h-4 w-4" />,
        label: "Healthy",
      };
    case "partial":
      return {
        badge: "bg-amber-100 text-amber-700",
        border: "border-amber-200",
        icon: <TriangleAlert className="h-4 w-4" />,
        label: "Partial",
      };
    case "failed":
      return {
        badge: "bg-rose-100 text-rose-700",
        border: "border-rose-200",
        icon: <XCircle className="h-4 w-4" />,
        label: "Failed",
      };
    default:
      return {
        badge: "bg-slate-100 text-slate-600",
        border: "border-slate-200",
        icon: <RefreshCw className="h-4 w-4" />,
        label: "Idle",
      };
  }
}

function dbStyles(dbStatus: string | undefined) {
  return dbStatus === "connected"
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : "border-amber-200 bg-amber-50 text-amber-700";
}

export function ScraperStatusPanel() {
  const { data, error, dataUpdatedAt } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: checkHealth,
    refetchInterval: REFRESH_INTERVAL_MS,
    refetchIntervalInBackground: true,
    retry: 1,
    staleTime: 10_000,
  });

  if (error && !data) {
    return (
      <section className="border-b border-slate-200 bg-white/95">
        <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            <AlertCircle className="h-4 w-4" />
            <span>Scraper status unavailable right now.</span>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="border-b border-slate-200 bg-white/95 shadow-sm backdrop-blur">
      <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
              Admin panel
            </p>
            <h2 className="text-sm font-semibold text-slate-950">Scraper status</h2>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-medium",
                data?.status === "ok"
                  ? "border-blue-200 bg-blue-50 text-blue-700"
                  : "border-amber-200 bg-amber-50 text-amber-700"
              )}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              API {data?.status ?? "unknown"}
            </span>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-medium",
                dbStyles(data?.db)
              )}
            >
              <Database className="h-3.5 w-3.5" />
              DB {data?.db ?? "unknown"}
            </span>
            {dataUpdatedAt ? (
              <span>Updated {formatLastUpdated(new Date(dataUpdatedAt).toISOString())}</span>
            ) : null}
          </div>
        </div>

        <div className="-mx-1 mt-3 overflow-x-auto pb-1">
          <div className="flex min-w-max gap-3 px-1">
            {BOOKMAKER_ORDER.map((bookmaker) => {
              const display = getBookmakerDisplay(bookmaker);
              const scraper = data?.scrapers[bookmaker] ?? EMPTY_STATUS;
              const tone = statusStyles(scraper.last_status);

              return (
                <article
                  key={bookmaker}
                  className={cn(
                    "w-[220px] rounded-2xl border bg-white p-4 shadow-sm transition",
                    tone.border
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-950">{display.displayName}</p>
                      <p className="mt-1 text-xs text-slate-500">Last run {formatRelativeTime(scraper.last_run_at)}</p>
                    </div>
                    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium", tone.badge)}>
                      {tone.icon}
                      {tone.label}
                    </span>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <MetricCard label="Matches" value={String(scraper.matches_found)} accent={display.bgColor} />
                    <MetricCard label="Odds saved" value={String(scraper.odds_saved)} accent={display.bgColor} />
                  </div>

                  <dl className="mt-4 space-y-2 text-xs text-slate-600">
                    <StatusRow label="Last success" value={scraper.last_success_at} />
                    <StatusRow label="Last failure" value={scraper.last_failure_at} />
                    <StatusRow label="Last data" value={scraper.last_scraped_at} />
                  </dl>

                  {scraper.last_error ? (
                    <p className="mt-3 truncate rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700" title={scraper.last_error}>
                      {scraper.last_error}
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>

        {error && data ? (
          <p className="mt-2 text-xs text-amber-600">
            Live refresh is temporarily unavailable. Showing the last successful status snapshot.
          </p>
        ) : null}
      </div>
    </section>
  );
}

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 px-3 py-2" style={{ backgroundColor: accent }}>
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function StatusRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-700">{formatRelativeTime(value)}</dd>
    </div>
  );
}
