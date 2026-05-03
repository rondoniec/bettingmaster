import { Kicker } from "@/components/Primitives";
import { PolymarketEventCard } from "@/components/PolymarketEventCard";
import { getNewPolymarketMarkets, type NewPolymarketMarket } from "@/lib/api";

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
          Trhy otvorené v posledných 24h, ktoré sa dajú stávkovať aj v slovenských kanceláriách.
          Pri každom porovnávame Polymarket vs. najlepší kurz na trhu — ak Polymarket platí viac,
          oplatí sa staviť tam.
        </p>
      </section>

      {error ? <EmptyState title="Polymarket nedostupný" body={error} /> : null}

      {!error && markets.length === 0 ? (
        <EmptyState
          title="Žiadne nové trhy"
          body="V posledných 24h Polymarket neotvoril nový trh, ktorý by sme našli aj u našich kancelárií."
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
