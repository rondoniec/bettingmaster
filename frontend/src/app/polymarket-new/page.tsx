import { ExternalLink, Radar, Sparkles } from "lucide-react";

import { getNewPolymarketMarkets, type NewPolymarketMarket } from "@/lib/api";
import { formatFullDate, formatLastUpdated } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function NewPolymarketMarketsPage() {
  let markets: NewPolymarketMarket[] = [];
  let error: string | null = null;

  try {
    markets = await getNewPolymarketMarkets();
  } catch (caughtError) {
    error = caughtError instanceof Error ? caughtError.message : "Could not load Polymarket markets.";
  }

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-[2rem] border border-blue-200 bg-[radial-gradient(circle_at_top_left,_rgba(37,99,235,0.18),_transparent_30%),radial-gradient(circle_at_top_right,_rgba(16,185,129,0.18),_transparent_28%),linear-gradient(135deg,_#ffffff,_#f8fbff)] px-6 py-8 shadow-[0_24px_70px_-44px_rgba(37,99,235,0.45)] sm:px-8">
        <div className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-blue-700">
          <Radar className="h-3.5 w-3.5" />
          Opening lines
        </div>
        <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
          Newly opened football markets on Polymarket.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-600">
          Far-future football markets can open with soft prices. This page watches newly created
          Polymarket events around Premier League, La Liga, and Champions League.
        </p>
      </section>

      {error ? <EmptyState title="Polymarket unavailable" body={error} /> : null}

      {!error && markets.length === 0 ? (
        <EmptyState
          title="No fresh far-future markets found"
          body="Nothing new matched the watched football leagues right now. Try again after Polymarket opens more markets."
        />
      ) : null}

      {!error && markets.length > 0 ? (
        <div className="grid gap-4">
          {markets.map((market) => (
            <a
              key={market.slug}
              href={market.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-[0_18px_45px_-34px_rgba(15,23,42,0.45)] transition hover:border-blue-200 hover:shadow-[0_20px_55px_-34px_rgba(37,99,235,0.55)]"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    {market.league_hint ? (
                      <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
                        {market.league_hint}
                      </span>
                    ) : null}
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                      <Sparkles className="h-3 w-3" />
                      {market.market_count} market{market.market_count === 1 ? "" : "s"}
                    </span>
                  </div>
                  <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950 group-hover:text-blue-700">
                    {market.title}
                  </h2>
                  <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-500">
                    {market.start_time ? <span>Starts {formatFullDate(market.start_time)}</span> : null}
                    {market.created_at ? (
                      <span>Opened {formatLastUpdated(market.created_at)}</span>
                    ) : null}
                  </div>
                </div>
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white">
                  Open
                  <ExternalLink className="h-3.5 w-3.5" />
                </span>
              </div>
            </a>
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
