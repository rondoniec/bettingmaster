import { Kicker } from "@/components/Primitives";
import { PolymarketEventCard } from "@/components/PolymarketEventCard";
import {
  getNonSportsPolymarketMarkets,
  type NewPolymarketMarket,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function OthersPage() {
  let markets: NewPolymarketMarket[] = [];
  let error: string | null = null;

  try {
    markets = await getNonSportsPolymarketMarkets();
  } catch (caughtError) {
    error =
      caughtError instanceof Error ? caughtError.message : "Could not load markets.";
  }

  return (
    <div className="space-y-6">
      <section className="border border-slate-200 bg-white p-6">
        <Kicker>Politika · Voľby · Geopolitika</Kicker>
        <h1 className="mt-2 text-[26px] font-semibold tracking-[-0.02em] text-slate-900">
          Iné trhy na Polymarkete
        </h1>
        <p className="mt-2 max-w-2xl text-[13px] leading-6 text-slate-600">
          Politické a geopolitické udalosti, voľby, USA, Stredný východ. Plánujeme
          dopĺňať porovnanie s kurzami od slovenských stávkoviek (napr. maďarské
          parlamentné voľby na Niké) — prepojenie ešte nie je hotové, zatiaľ
          objavuj na Polymarkete.
        </p>
      </section>

      {error ? <EmptyState title="Polymarket nedostupný" body={error} /> : null}

      {!error && markets.length === 0 ? (
        <EmptyState
          title="Čaká sa na scraper Niké/Fortuna pre nešportové trhy"
          body="Polymarket má aktívne trhy na voľby, geopolitiku a podobne, ale zobrazujeme ich len keď sú dostupné aj na slovenských stávkovkách. Ten scraper ešte nie je hotový."
        />
      ) : null}

      {!error && markets.length > 0 ? (
        <div className="flex flex-col gap-3">
          {markets.map((market) => (
            <PolymarketEventCard key={market.slug} market={market} />
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
