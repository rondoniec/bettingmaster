"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock3, Layers3 } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { LiveUpdatesBadge } from "@/components/LiveUpdatesBadge";
import { OddsHistoryChart } from "@/components/OddsHistoryChart";
import { OddsTable } from "@/components/OddsTable";
import { OutcomesPanel } from "@/components/OutcomesPanel";
import { getBestOdds, getMatchDetail, type BestOdds, type MatchDetail } from "@/lib/api";
import {
  BOOKMAKER_ORDER,
  getBookmakerDisplay,
  getMarketLabel,
  resolveSelectionLabel,
} from "@/lib/constants";
import { formatFullDate, formatLastUpdated } from "@/lib/utils";

type Props = {
  initialMatch: MatchDetail;
  initialBestOdds: BestOdds[];
  focusTarget?: {
    market?: string;
    selection?: string;
    bookmaker?: string;
  };
};

export function MatchLiveSection({ initialMatch, initialBestOdds, focusTarget }: Props) {
  const queryClient = useQueryClient();
  const matchDetailQueryKey = ["match-detail", initialMatch.id];
  const bestOddsQueryKey = ["best-odds", initialMatch.id];

  const { data: match = initialMatch } = useQuery({
    queryKey: matchDetailQueryKey,
    queryFn: () => getMatchDetail(initialMatch.id),
    initialData: initialMatch,
  });

  const { data: bestOdds = initialBestOdds } = useQuery({
    queryKey: bestOddsQueryKey,
    queryFn: () => getBestOdds(initialMatch.id),
    initialData: initialBestOdds,
  });

  const marketSet = new Set(match.odds.map((entry) => entry.market));
  for (const market of bestOdds) {
    marketSet.add(market.market);
  }

  const focusedMarket = focusTarget?.market?.trim() || null;
  const markets = Array.from(marketSet).sort((left, right) => {
    if (focusedMarket && left === focusedMarket && right !== focusedMarket) {
      return -1;
    }
    if (focusedMarket && right === focusedMarket && left !== focusedMarket) {
      return 1;
    }
    return left.localeCompare(right);
  });
  const marginByMarket = new Map(bestOdds.map((market) => [market.market, market.combined_margin]));
  const lastUpdated =
    match.odds.length > 0
      ? [...match.odds].sort((left, right) => right.scraped_at.localeCompare(left.scraped_at))[0]
          ?.scraped_at
      : null;
  const bookmakerCount = new Set(match.odds.map((entry) => entry.bookmaker)).size;
  const activeBookmakers = BOOKMAKER_ORDER.filter((bookmaker) =>
    match.odds.some((entry) => entry.bookmaker === bookmaker)
  );

  useEffect(() => {
    if (!focusedMarket) {
      return;
    }
    const section = document.getElementById(`market-${focusedMarket}`);
    section?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [focusedMarket]);

  const isLive = new Date(match.start_time) <= new Date() || match.status === "live";

  return (
    <div className="space-y-8">
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.18),_transparent_30%),linear-gradient(180deg,_#ffffff,_#f8fbff)] px-6 py-8 shadow-[0_24px_70px_-44px_rgba(15,23,42,0.45)] sm:px-8">
        <Link href="/" className="text-sm font-medium text-blue-600 hover:text-blue-700">
          Back to board
        </Link>
        <div className="mt-4 flex items-center gap-2">
          <Link
            href={`/league/${match.league_id}`}
            className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 transition hover:text-blue-600"
          >
            {match.league_id}
          </Link>
          {isLive ? (
            <span className="animate-pulse rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-red-600">
              Live
            </span>
          ) : null}
        </div>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
          {match.home_team} vs {match.away_team}
        </h1>
        <p className="mt-3 text-sm text-slate-500">{formatFullDate(match.start_time)}</p>
        <div className="mt-5 flex flex-wrap gap-3">
          <LiveUpdatesBadge
            matchId={match.id}
            onUpdate={() => {
              queryClient.invalidateQueries({ queryKey: matchDetailQueryKey });
              queryClient.invalidateQueries({ queryKey: bestOddsQueryKey });
              queryClient.invalidateQueries({ queryKey: ["odds-history", match.id] });
            }}
          />
          {lastUpdated ? (
            <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-sm text-slate-600 shadow-sm">
              <Clock3 className="h-4 w-4 text-blue-600" />
              Updated {formatLastUpdated(lastUpdated)}
            </div>
          ) : null}
          <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-sm text-slate-600 shadow-sm">
            <Layers3 className="h-4 w-4 text-emerald-600" />
            {bookmakerCount} bookmaker{bookmakerCount === 1 ? "" : "s"} tracked
          </div>
        </div>

        {activeBookmakers.length > 0 ? (
          <div className="mt-5">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
              Bookmakers on this match
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {activeBookmakers.map((bookmaker) => {
                const bookmakerData = getBookmakerDisplay(bookmaker);
                return (
                  <span
                    key={bookmaker}
                    className="rounded-full px-3 py-1.5 text-sm font-semibold"
                    style={{
                      backgroundColor: bookmakerData.bgColor,
                      color: bookmakerData.color,
                    }}
                  >
                    {bookmakerData.displayName}
                  </span>
                );
              })}
            </div>
          </div>
        ) : null}
      </section>

      <section className="space-y-4">
        <OutcomesPanel
          odds={match.odds}
          homeTeam={match.home_team}
          awayTeam={match.away_team}
        />
      </section>

      <section className="space-y-6">
        {focusTarget?.market && focusTarget?.selection && focusTarget?.bookmaker ? (
          <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            Focused outcome: {getBookmakerDisplay(focusTarget.bookmaker).displayName} •{" "}
            {getMarketLabel(focusTarget.market)} • {resolveSelectionLabel(focusTarget.selection, match.home_team, match.away_team)}
          </div>
        ) : null}
        {markets.map((market) => (
          <div
            key={market}
            id={`market-${market}`}
            className="space-y-3 scroll-mt-24"
          >
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-xl font-semibold text-slate-950">{getMarketLabel(market)}</h2>
              {marginByMarket.has(market) ? (
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                  Combined margin {marginByMarket.get(market)?.toFixed(2)}%
                </span>
              ) : null}
            </div>
            <OddsTable
              market={market}
              odds={match.odds}
              combinedMargin={marginByMarket.get(market)}
              focusedBookmaker={market === focusedMarket ? focusTarget?.bookmaker : undefined}
              focusedSelection={market === focusedMarket ? focusTarget?.selection : undefined}
              homeTeam={match.home_team}
              awayTeam={match.away_team}
            />
            <OddsHistoryChart matchId={match.id} market={market} homeTeam={match.home_team} awayTeam={match.away_team} />
          </div>
        ))}
      </section>
    </div>
  );
}
