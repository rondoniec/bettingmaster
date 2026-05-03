"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect } from "react";

import { BookmakerToggleBar } from "@/components/BookmakerToggleBar";
import { Countdown } from "@/components/Countdown";
import { FreshnessBadge } from "@/components/FreshnessBadge";
import { LiveUpdatesBadge } from "@/components/LiveUpdatesBadge";
import { MarketOddsBoard } from "@/components/MarketOddsBoard";
import { BookmakerChip, Kicker, LiveBadge } from "@/components/Primitives";
import { useBookmakerFilter } from "@/hooks/useBookmakerFilter";
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
  const { isEnabled, hydrated: filterHydrated } = useBookmakerFilter();

  const { data: rawMatch = initialMatch } = useQuery({
    queryKey: matchDetailQueryKey,
    queryFn: () => getMatchDetail(initialMatch.id),
    initialData: initialMatch,
  });

  const { data: rawBestOdds = initialBestOdds } = useQuery({
    queryKey: bestOddsQueryKey,
    queryFn: () => getBestOdds(initialMatch.id),
    initialData: initialBestOdds,
  });

  const match = filterHydrated
    ? { ...rawMatch, odds: rawMatch.odds.filter((entry) => isEnabled(entry.bookmaker)) }
    : rawMatch;

  // Drop entire markets where best is now from a disabled bookmaker; recompute best
  // from remaining entries inside MarketOddsBoard. We pass the market list through
  // bestOdds so the margin chip stays meaningful — but recompute its selections
  // server-style here to preserve the filter.
  const bestOdds = filterHydrated
    ? rawBestOdds
        .map((bo) => ({
          ...bo,
          selections: bo.selections.filter((s) => isEnabled(s.bookmaker)),
        }))
        .filter((bo) => bo.selections.length > 0)
    : rawBestOdds;

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
      <Link
        href="/"
        className="inline-flex items-center font-mono text-[12px] text-slate-600 hover:text-slate-900"
      >
        ← Späť na hlavnú stránku
      </Link>

      <section className="border border-slate-200 bg-white px-6 py-5">
        <div className="flex flex-wrap items-center gap-3">
          <Link
            href={`/league/${match.league_id}`}
            className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500 hover:text-slate-900"
          >
            {match.league_id.replace(/-/g, " ").toUpperCase()}
          </Link>
          {isLive ? (
            <LiveBadge />
          ) : (
            <Countdown startTime={match.start_time} status={match.status} />
          )}
          <span className="font-mono text-[11px] tabular-nums text-slate-500">
            {formatFullDate(match.start_time)}
          </span>
        </div>

        <h1 className="mt-3 text-[28px] font-semibold tracking-[-0.02em] text-slate-900">
          {match.home_team}
          <span className="mx-3 text-slate-300">vs</span>
          {match.away_team}
        </h1>

        <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-3">
          <Kicker>Stávkové kancelárie</Kicker>
          <div className="flex flex-wrap items-center gap-1.5">
            {activeBookmakers.map((bookmaker) => {
              const checkedAt = latestCheckedAtForBookmaker(match.odds, bookmaker);
              const freshness = getBookmakerFreshness(bookmaker, checkedAt);
              return (
                <span key={bookmaker} className="inline-flex items-center gap-1">
                  <BookmakerChip bookmaker={bookmaker} />
                  <FreshnessBadge
                    freshness={freshness.freshness}
                    ageSeconds={freshness.ageSeconds}
                  />
                </span>
              );
            })}
          </div>
          <div className="ml-auto flex items-center gap-3 font-mono text-[11px] tabular-nums text-slate-500">
            {lastChecked ? <span>aktualizované {formatLastUpdated(lastChecked)}</span> : null}
            <LiveUpdatesBadge
              matchId={match.id}
              onUpdate={() => {
                queryClient.invalidateQueries({ queryKey: matchDetailQueryKey });
                queryClient.invalidateQueries({ queryKey: bestOddsQueryKey });
              }}
            />
          </div>
        </div>
      </section>

      {focusTarget?.market && focusTarget?.selection && focusTarget?.bookmaker ? (
        <div className="border border-emerald-200 border-l-[3px] border-l-emerald-700 bg-emerald-50 px-4 py-3 font-mono text-[12px] text-slate-900">
          Označený výsledok: {getBookmakerDisplay(focusTarget.bookmaker).displayName} ·{" "}
          {getMarketLabel(focusTarget.market)} ·{" "}
          {resolveSelectionLabel(focusTarget.selection, match.home_team, match.away_team)}
        </div>
      ) : null}

      <BookmakerToggleBar />

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
