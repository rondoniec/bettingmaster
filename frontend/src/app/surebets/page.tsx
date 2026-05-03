import { ArrowRight, ExternalLink } from "lucide-react";
import Link from "next/link";

import { BookmakerChip, Kicker } from "@/components/Primitives";
import { getSurebets, type Surebet } from "@/lib/api";
import { resolveSelectionLabel } from "@/lib/constants";
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
      <section className="border border-slate-200 bg-white p-6">
        <Kicker>Príležitosti</Kicker>
        <h1 className="mt-2 text-[26px] font-semibold tracking-[-0.02em] text-slate-900">
          Sigurebety z aktuálnych snapshotov
        </h1>
        <p className="mt-2 max-w-2xl text-[13px] leading-6 text-slate-600">
          Zobrazujeme len kombinácie so zápornou maržou — každá karta je aktuálna garantovaná
          výhra ak kurzy ostanú dostupné.
        </p>
      </section>

      {error ? <EmptyState title="API nedostupné" body={error} /> : null}

      {!error && surebets.length === 0 ? (
        <EmptyState
          title="Žiadne sigurebety"
          body="Scraper zatiaľ nenašiel kombináciu so zápornou maržou."
        />
      ) : null}

      {!error && surebets.length > 0 ? (
        <div className="flex flex-col gap-4">
          {surebets.map((surebet) => (
            <article
              key={`${surebet.match_id}-${surebet.market}`}
              className="border border-slate-200 border-l-[3px] border-l-emerald-700 bg-white"
            >
              <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
                <div>
                  <Kicker>{surebet.league_id.replace(/-/g, " ").toUpperCase()}</Kicker>
                  <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-900">
                    {surebet.home_team}
                    <span className="mx-2 text-slate-400">vs</span>
                    {surebet.away_team}
                  </h2>
                  <p className="mt-1 font-mono text-[11px] tabular-nums text-slate-500">
                    {formatFullDate(surebet.start_time)} · {surebet.market.toUpperCase()}
                  </p>
                </div>
                <span className="border border-emerald-200 bg-emerald-50 px-2.5 py-1 font-mono text-[12px] font-semibold tabular-nums text-emerald-700">
                  Profit {formatProfitPercent(surebet.profit_percent)}
                </span>
              </header>

              <div className="m-4 grid gap-px border border-slate-200 bg-slate-200 p-px sm:grid-cols-3">
                {surebet.selections.map((selection) => {
                  const focusHref = `/match/${surebet.match_id}?market=${encodeURIComponent(
                    surebet.market,
                  )}&selection=${encodeURIComponent(selection.selection)}&bookmaker=${encodeURIComponent(
                    selection.bookmaker,
                  )}`;
                  return (
                    <div key={selection.selection} className="bg-white p-4">
                      <Kicker>
                        {resolveSelectionLabel(
                          selection.selection,
                          surebet.home_team,
                          surebet.away_team,
                        )}
                      </Kicker>
                      <p className="mt-2 font-mono text-[28px] font-semibold tabular-nums tracking-[-0.02em] text-emerald-700">
                        {selection.odds.toFixed(2)}
                      </p>
                      <BookmakerChip bookmaker={selection.bookmaker} className="mt-2" />
                      <p className="mt-2 font-mono text-[10px] text-slate-400">
                        skontrolované {formatLastUpdated(selection.checked_at ?? selection.scraped_at)}
                      </p>
                      <div className="mt-3 flex flex-wrap items-center gap-3 font-mono text-[10px] font-semibold uppercase tracking-wider">
                        <Link
                          href={focusHref}
                          className="inline-flex items-center gap-1 text-slate-700 hover:text-slate-900"
                        >
                          Otvoriť výsledok
                          <ArrowRight className="h-3 w-3" />
                        </Link>
                        {selection.url ? (
                          <a
                            href={selection.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-emerald-700 hover:text-emerald-800"
                          >
                            Stávkovka
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : null}
                      </div>
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
    <div className="border border-dashed border-slate-300 bg-white p-12 text-center">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      <p className="mx-auto mt-2 max-w-2xl text-[13px] leading-6 text-slate-500">{body}</p>
    </div>
  );
}
