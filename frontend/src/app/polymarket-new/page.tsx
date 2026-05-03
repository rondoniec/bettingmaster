import { ExternalLink } from "lucide-react";

import { Kicker } from "@/components/Primitives";
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
      <section className="border border-slate-200 bg-white p-6">
        <Kicker>Otváracie kurzy</Kicker>
        <h1 className="mt-2 text-[26px] font-semibold tracking-[-0.02em] text-slate-900">
          Novo otvorené futbalové trhy na Polymarkete
        </h1>
        <p className="mt-2 max-w-2xl text-[13px] leading-6 text-slate-600">
          Vzdialené futbalové trhy môžu otvoriť s mäkkými kurzami. Sledujeme nové eventy okolo
          Premier League, La Ligy a Champions League.
        </p>
      </section>

      {error ? <EmptyState title="Polymarket nedostupný" body={error} /> : null}

      {!error && markets.length === 0 ? (
        <EmptyState
          title="Žiadne nové trhy"
          body="Aktuálne nie sú novootvorené trhy v sledovaných ligách."
        />
      ) : null}

      {!error && markets.length > 0 ? (
        <div className="flex flex-col gap-3">
          {markets.map((market) => (
            <a
              key={market.slug}
              href={market.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group block border border-slate-200 bg-white p-5 transition hover:border-slate-400"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    {market.league_hint ? <Kicker>{market.league_hint}</Kicker> : null}
                    <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
                      {market.market_count} {market.market_count === 1 ? "trh" : "trhov"}
                    </span>
                  </div>
                  <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-900 group-hover:text-emerald-700">
                    {market.title}
                  </h2>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] tabular-nums text-slate-500">
                    {market.start_time ? <span>začína {formatFullDate(market.start_time)}</span> : null}
                    {market.created_at ? <span>otvorené {formatLastUpdated(market.created_at)}</span> : null}
                  </div>
                </div>
                <span className="inline-flex items-center gap-1 bg-slate-900 px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-white group-hover:bg-slate-700">
                  Otvoriť
                  <ExternalLink className="h-3 w-3" />
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
    <div className="border border-dashed border-slate-300 bg-white p-12 text-center">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      <p className="mx-auto mt-2 max-w-2xl text-[13px] leading-6 text-slate-500">{body}</p>
    </div>
  );
}
