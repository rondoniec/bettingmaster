import { ExternalLink } from "lucide-react";
import Link from "next/link";

import { getSurebets, type Surebet } from "@/lib/api";
import { getBookmakerDisplay, resolveSelectionLabel } from "@/lib/constants";
import { formatFullDate, formatLastUpdated, formatProfitPercent } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function SurebetsPage() {
  let surebets: Surebet[] = [];
  let error: string | null = null;

  try {
    surebets = await getSurebets();
  } catch (caughtError) {
    error = caughtError instanceof Error ? caughtError.message : "Could not load surebets.";
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-emerald-200 bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.18),_transparent_28%),linear-gradient(180deg,_#ffffff,_#f4fff8)] px-6 py-8 shadow-[0_24px_70px_-44px_rgba(5,150,105,0.45)] sm:px-8">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-600">
          Opportunity board
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">
          Surebets from the latest snapshots
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          These rows surface only negative-margin combinations, so each card reflects a current
          guaranteed-profit setup if the prices are still available.
        </p>
      </section>

      {error ? (
        <EmptyState title="API unavailable" body={error} />
      ) : null}

      {!error && surebets.length === 0 ? (
        <EmptyState
          title="No surebets right now"
          body="The scraper has not produced a negative-margin setup yet, or the current snapshots no longer overlap."
        />
      ) : null}

      {!error && surebets.length > 0 ? (
        <div className="grid gap-5">
          {surebets.map((surebet) => (
            <article
              key={`${surebet.match_id}-${surebet.market}`}
              className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-[0_18px_45px_-32px_rgba(15,23,42,0.45)] sm:p-6"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                    {surebet.league_id}
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                    {surebet.home_team} vs {surebet.away_team}
                  </h2>
                  <p className="mt-2 text-sm text-slate-500">
                    {formatFullDate(surebet.start_time)} • {surebet.market.toUpperCase()}
                  </p>
                </div>

                <div className="rounded-full bg-emerald-100 px-4 py-2 text-sm font-semibold text-emerald-700">
                  Profit {formatProfitPercent(surebet.profit_percent)}
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                {surebet.selections.map((selection) => {
                  const bookmaker = getBookmakerDisplay(selection.bookmaker);
                  const focusHref = `/match/${surebet.match_id}?market=${encodeURIComponent(
                    surebet.market
                  )}&selection=${encodeURIComponent(selection.selection)}&bookmaker=${encodeURIComponent(
                    selection.bookmaker
                  )}`;
                  return (
                    <div
                      key={selection.selection}
                      className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                    >
                      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                        {resolveSelectionLabel(selection.selection, surebet.home_team, surebet.away_team)}
                      </p>
                      <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
                        {selection.odds.toFixed(2)}
                      </p>
                      <p className="mt-2 text-sm font-medium" style={{ color: bookmaker.color }}>
                        {bookmaker.displayName}
                      </p>
                      <p className="mt-2 text-xs text-slate-400">
                        Price from {formatLastUpdated(selection.scraped_at)}
                        {selection.checked_at ? ` • checked ${formatLastUpdated(selection.checked_at)}` : ""}
                      </p>
                      <Link
                        href={focusHref}
                        className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-blue-600 transition hover:text-blue-700"
                      >
                        Open exact outcome
                      </Link>
                      {selection.url ? (
                        <a
                          href={selection.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-slate-600 transition hover:text-slate-950"
                        >
                          Visit bookmaker
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-[1.75rem] border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      <h2 className="text-xl font-semibold text-slate-950">{title}</h2>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-slate-500">{body}</p>
    </div>
  );
}
