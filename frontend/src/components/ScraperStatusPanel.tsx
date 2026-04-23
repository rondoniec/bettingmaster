"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, AlertCircle, CheckCircle2, Clock3 } from "lucide-react";

import { checkHealth, type ScraperHealth } from "@/lib/api";
import { BOOKMAKER_ORDER, getBookmakerDisplay } from "@/lib/constants";
import { formatLastUpdated } from "@/lib/utils";

const EMPTY_STATUS: ScraperHealth = {
  last_scraped_at: null,
  last_run_at: null,
  last_success_at: null,
  last_failure_at: null,
  last_status: null,
  matches_found: 0,
  odds_saved: 0,
  last_error: null,
};

function statusBadgeClass(status: string | null) {
  switch (status) {
    case "success":
      return "bg-emerald-50 text-emerald-700 ring-emerald-200";
    case "partial":
      return "bg-amber-50 text-amber-700 ring-amber-200";
    case "failed":
      return "bg-rose-50 text-rose-700 ring-rose-200";
    default:
      return "bg-slate-100 text-slate-600 ring-slate-200";
  }
}

function statusLabel(status: string | null) {
  switch (status) {
    case "success":
      return "Healthy";
    case "partial":
      return "Partial";
    case "failed":
      return "Failed";
    default:
      return "No runs yet";
  }
}

function formatStatusTime(value: string | null) {
  if (!value) {
    return "—";
  }

  return formatLastUpdated(value);
}

function absoluteTime(value: string | null) {
  if (!value) {
    return undefined;
  }

  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function ScraperStatusPanel() {
  const { data, error, isPending } = useQuery({
    queryKey: ["scraper-health"],
    queryFn: checkHealth,
    refetchInterval: 15_000,
    retry: 1,
  });

  const overallStatus = data?.status ?? "unknown";
  const dbStatus = data?.db ?? "unknown";

  return (
    <section className="border-b border-slate-200/80 bg-white/95 shadow-sm backdrop-blur">
      <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-[0_18px_40px_-28px_rgba(15,23,42,0.45)]">
          <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                <Activity className="h-3.5 w-3.5" />
                Scraper admin panel
              </div>
              <h2 className="mt-2 text-sm font-semibold text-slate-950 sm:text-base">
                Latest bookmaker worker activity
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Last run, last success, last failure, matches found, and odds saved for every scraper.
              </p>
            </div>

            <div className="flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-[0.2em]">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 ${
                  overallStatus === "ok"
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-amber-50 text-amber-700"
                }`}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                API {overallStatus}
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 ${
                  dbStatus === "connected"
                    ? "bg-blue-50 text-blue-700"
                    : "bg-rose-50 text-rose-700"
                }`}
              >
                <Clock3 className="h-3.5 w-3.5" />
                DB {dbStatus}
              </span>
            </div>
          </div>

          {error ? (
            <div className="mt-4 flex items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>Status unavailable. Showing placeholders until the health endpoint responds again.</span>
            </div>
          ) : null}

          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {BOOKMAKER_ORDER.map((bookmaker) => {
              const bookmakerData = getBookmakerDisplay(bookmaker);
              const scraper = data?.scrapers?.[bookmaker] ?? EMPTY_STATUS;

              return (
                <article
                  key={bookmaker}
                  className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-950">
                        {bookmakerData.displayName}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Data freshness: {formatStatusTime(scraper.last_scraped_at)}
                      </p>
                    </div>
                    <span
                      className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ${statusBadgeClass(
                        scraper.last_status
                      )}`}
                    >
                      {statusLabel(scraper.last_status)}
                    </span>
                  </div>

                  <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                    <div>
                      <dt className="text-xs uppercase tracking-[0.18em] text-slate-400">Last run</dt>
                      <dd className="mt-1 font-medium text-slate-700" title={absoluteTime(scraper.last_run_at)}>
                        {formatStatusTime(scraper.last_run_at)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-[0.18em] text-slate-400">Last success</dt>
                      <dd
                        className="mt-1 font-medium text-slate-700"
                        title={absoluteTime(scraper.last_success_at)}
                      >
                        {formatStatusTime(scraper.last_success_at)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-[0.18em] text-slate-400">Last failure</dt>
                      <dd
                        className="mt-1 font-medium text-slate-700"
                        title={absoluteTime(scraper.last_failure_at)}
                      >
                        {formatStatusTime(scraper.last_failure_at)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-[0.18em] text-slate-400">Matches found</dt>
                      <dd className="mt-1 font-medium text-slate-900">{scraper.matches_found}</dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-[0.18em] text-slate-400">Odds saved</dt>
                      <dd className="mt-1 font-medium text-slate-900">{scraper.odds_saved}</dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-[0.18em] text-slate-400">Loaded</dt>
                      <dd className="mt-1 font-medium text-slate-700">
                        {isPending && !data ? "Refreshing…" : "Live poll"}
                      </dd>
                    </div>
                  </dl>

                  {scraper.last_error ? (
                    <p className="mt-4 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                      {scraper.last_error}
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
