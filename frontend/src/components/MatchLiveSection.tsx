"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock3, Layers3 } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { Countdown } from "@/components/Countdown";
import { FreshnessBadge } from "@/components/FreshnessBadge";
import { LiveUpdatesBadge } from "@/components/LiveUpdatesBadge";
import { MarketOddsBoard } from "@/components/MarketOddsBoard";
import { getBestOdds, getMatchDetail, type BestOdds, type MatchDetail } from "@/lib/api";
import {
  BOOKMAKER_ORDER,
  getBookmakerDisplay,
  getMarketLabel,
  resolveSelectionLabel,
} from "@/lib/constants";
import { formatFullDate, formatLastUpdated, getBookmakerFreshness } from "@/lib/utils";

type Props = {
  initialMatch: MatchDetail;
  initialBestOdds: BestOdds[];
  focusTarget?: {
    market?: string;
    selection?: string;
    bookmaker?: string;
  };
};

function latestCheckedAt(odds: MatchDetail["odds"]) {
  if (odds.length === 0) {
    return null;
  }

  return [...odds]
    .map((entry) => entry.checked_at ?? entry.scraped_at)
    .sort((left, right) => right.localeCompare(left))[0];
}

function latestCheckedAtForBookmaker(odds: MatchDetail["odds"], bookmaker: string) {
  const timestamps = odds
    .filter((entry) => entry.bookmaker === bookmaker)
    .map((entry) => entry.checked_at ?? entry.scraped_at)
    .sort((left, right) => right.localeCompare(left));
  return timestamps[0] ?? null;
}

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
  const lastChecked = latestCheckedAt(match.odds);
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
    <div className="space-y-6">
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.18),_transparent_30%),linear-gradient(180deg,_#ffffff,_#f8fbff)] px-6 py-8 shadow-[0_24px_70px_-44px_rgba(15,23,42,0.45)] sm:px-8">
        <Link href="/" className="text-sm font-medium text-blue-600 hover:text-blue-700">
          Back to homepage
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
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-500">
          <span>{formatFullDate(match.start_time)}</span>
          <Countdown startTime={match.start_time} status={match.status} />
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <LiveUpdatesBadge
            matchId={match.id}
            onUpdate={() => {
              queryClient.invalidateQueries({ queryKey: matchDetailQueryKey });
              queryClient.invalidateQueries({ queryKey: bestOddsQueryKey });
            }}
          />
          {lastChecked ? (
            <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-sm text-slate-600 shadow-sm">
              <Clock3 className="h-4 w-4 text-blue-600" />
              Checked {formatLastUpdated(lastChecked)}
            </div>
          ) : null}
          <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-sm text-slate-600 shadow-sm">
            <Layers3 className="h-4 w-4 text-emerald-600" />
            {bookmakerCount} bookmaker{bookmakerCount === 1 ? "" : "s"} tracked
          </div>
        </div>

        {activeBookmakers.length > 0 ? (
          <div className="mt-5 flex flex-wrap gap-2">
            {activeBookmakers.map((bookmaker) => {
              const bookmakerData = getBookmakerDisplay(bookmaker);
              return (
                <span
                  key={bookmaker}
                  className="inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold"
                  style={{ backgroundColor: bookmakerData.bgColor, color: bookmakerData.color }}
                >
                  <span>{bookmakerData.displayName}</span>
                  {(() => {
                    const checkedAt = latestCheckedAtForBookmaker(match.odds, bookmaker);
                    const freshness = getBookmakerFreshness(bookmaker, checkedAt);
                    return (
                      <FreshnessBadge
                        freshness={freshness.freshness}
                        ageSeconds={freshness.ageSeconds}
                        className="bg-white/80 text-slate-700"
                      />
                    );
                  })()}
                </span>
              );
            })}
          </div>
        ) : null}
      </section>

      {focusTarget?.market && focusTarget?.selection && focusTarget?.bookmaker ? (
        <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
          Focused outcome: {getBookmakerDisplay(focusTarget.bookmaker).displayName} &bull;{" "}
          {getMarketLabel(focusTarget.market)} &bull;{" "}
          {resolveSelectionLabel(focusTarget.selection, match.home_team, match.away_team)}
        </div>
      ) : null}

      <MarketOddsBoard
        markets={markets}
        odds={match.odds}
        bestOdds={bestOdds}
        focusedBookmaker={focusTarget?.bookmaker}
        focusedMarket={focusedMarket}
        focusedSelection={focusTarget?.selection}
        homeTeam={match.home_team}
        awayTeam={match.away_team}
      />
    </div>
  );
}
