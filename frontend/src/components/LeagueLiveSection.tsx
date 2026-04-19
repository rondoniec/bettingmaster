"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, ChartNoAxesCombined, Layers3 } from "lucide-react";
import Link from "next/link";

import { BestOddsMatchCard } from "@/components/BestOddsMatchCard";
import { LiveUpdatesBadge } from "@/components/LiveUpdatesBadge";
import { MatchCard } from "@/components/MatchCard";
import {
  getMatchesByLeague,
  getMatchesWithBestOdds,
  type BestOdds,
  type League,
  type Match,
  type MatchBestOdds,
} from "@/lib/api";
import { BOOKMAKER_ORDER, getBookmakerDisplay } from "@/lib/constants";
import { formatFullDate } from "@/lib/utils";

type Props = {
  league: League;
  date: string;
  initialMatches: Match[];
  initialPricedMatches: MatchBestOdds[];
};

const DATE_FILTERS = [
  { value: "today", label: "Today" },
  { value: "tomorrow", label: "Tomorrow" },
];

function buildLeagueHref(leagueId: string, date: string) {
  return `/league/${leagueId}?date=${encodeURIComponent(date)}`;
}

export function LeagueLiveSection({
  league,
  date,
  initialMatches,
  initialPricedMatches,
}: Props) {
  const queryClient = useQueryClient();
  const matchesQueryKey = ["league-matches", league.id, date];
  const pricedMatchesQueryKey = ["league-best-odds", league.id, date, "1x2", 1];

  const { data: matches = [] } = useQuery({
    queryKey: matchesQueryKey,
    queryFn: () => getMatchesByLeague(league.id, date),
    initialData: initialMatches,
  });

  const { data: pricedMatches = [] } = useQuery({
    queryKey: pricedMatchesQueryKey,
    queryFn: () =>
      getMatchesWithBestOdds({
        league_id: league.id,
        date,
        market: "1x2",
        min_bookmakers: 1,
      }),
    initialData: initialPricedMatches,
  });

  const bestOddsByMatch = new Map(
    pricedMatches.map((match) => [
      match.id,
      {
        match_id: match.id,
        market: match.market,
        selections: match.selections,
        combined_margin: match.combined_margin,
      } satisfies BestOdds,
    ])
  );
  const crossBookmakerMatches = pricedMatches.filter((match) => match.bookmakers.length >= 2);
  const nextMatch = matches[0];
  const activeBookmakers = BOOKMAKER_ORDER.filter((bookmaker) =>
    pricedMatches.some((match) => match.bookmakers.includes(bookmaker))
  );

  return (
    <>
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(37,99,235,0.18),_transparent_34%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.16),_transparent_28%),linear-gradient(135deg,_#f8fbff,_#ffffff_46%,_#f5fbff)] px-6 py-8 shadow-[0_28px_80px_-40px_rgba(15,23,42,0.45)] sm:px-8 sm:py-10">
        <Link href="/" className="text-sm font-medium text-blue-600 hover:text-blue-700">
          Back to board
        </Link>

        <div className="mt-4 flex flex-wrap items-start justify-between gap-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
              {league.country} • {league.sport_id}
            </p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
              {league.name}
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
              League-wide view for scheduled fixtures, cross-bookmaker comparisons, and quick
              access to each match board.
            </p>
          </div>

          <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-4 backdrop-blur">
            <p className="text-sm font-semibold text-slate-900">Date filter</p>
            <LiveUpdatesBadge
              leagueId={league.id}
              date={date}
              className="mt-3"
              onUpdate={() => {
                queryClient.invalidateQueries({ queryKey: matchesQueryKey });
                queryClient.invalidateQueries({ queryKey: pricedMatchesQueryKey });
              }}
            />
            <div className="mt-3 flex flex-wrap gap-2">
              {DATE_FILTERS.map((option) => (
                <Link
                  key={option.value}
                  href={buildLeagueHref(league.id, option.value)}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                    date === option.value
                      ? "bg-slate-900 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {option.label}
                </Link>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <MetricCard
            label="Scheduled fixtures"
            value={String(matches.length)}
            icon={<CalendarDays className="h-4 w-4" />}
          />
          <MetricCard
            label="Priced matches"
            value={String(pricedMatches.length)}
            icon={<Layers3 className="h-4 w-4" />}
          />
          <MetricCard
            label="Cross-bookmaker"
            value={String(crossBookmakerMatches.length)}
            icon={<ChartNoAxesCombined className="h-4 w-4" />}
          />
        </div>

        {activeBookmakers.length > 0 ? (
          <div className="mt-6">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
              Active bookmakers in this league view
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

        {nextMatch ? (
          <div className="mt-6 rounded-[1.5rem] border border-slate-200 bg-white/75 p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
              Next kickoff
            </p>
            <p className="mt-2 text-lg font-semibold text-slate-950">
              {nextMatch.home_team} vs {nextMatch.away_team}
            </p>
            <p className="mt-1 text-sm text-slate-500">{formatFullDate(nextMatch.start_time)}</p>
          </div>
        ) : null}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
            Best odds in this league
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Cross-bookmaker matches with direct 1X2 comparison.
          </p>
        </div>

        {crossBookmakerMatches.length > 0 ? (
          <div className="grid gap-5">
            {crossBookmakerMatches.map((match) => (
              <BestOddsMatchCard key={match.id} match={match} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No merged comparisons yet"
            body="This league has fixtures, but not enough overlapping bookmaker coverage for a merged board on the selected day."
          />
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">All fixtures</h2>
          <p className="mt-1 text-sm text-slate-500">
            Every scheduled match for the selected date, with best available 1X2 prices when present.
          </p>
        </div>

        {matches.length > 0 ? (
          <div className="grid gap-3">
            {matches.map((match) => (
              <MatchCard key={match.id} match={match} bestOdds={bestOddsByMatch.get(match.id)} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No fixtures for this date"
            body="Try switching between today and tomorrow, or come back after the next scraper cycle."
          />
        )}
      </section>
    </>
  );
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/80 bg-white/80 px-4 py-3 backdrop-blur">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        {icon}
        <span>{label}</span>
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
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
