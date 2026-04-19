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
  status?: string;
  sort?: string;
  initialMatches: Match[];
  initialPricedMatches: MatchBestOdds[];
};

const DATE_FILTERS = [
  { value: "today", label: "Today" },
  { value: "tomorrow", label: "Tomorrow" },
];

const STATUS_FILTERS = [
  { value: "live", label: "Live" },
  { value: "upcoming", label: "Upcoming" },
] as const;

const SORT_OPTIONS = [
  { value: "kickoff", label: "Kickoff" },
  { value: "edge", label: "Best edge" },
  { value: "coverage", label: "Coverage" },
] as const;

function buildLeagueHref(
  leagueId: string,
  current: { date: string; status?: string; sort?: string },
  updates: Record<string, string | undefined>
) {
  const params = new URLSearchParams();
  params.set("date", current.date);
  if (current.status) {
    params.set("status", current.status);
  }
  if (current.sort) {
    params.set("sort", current.sort);
  }

  for (const [key, value] of Object.entries(updates)) {
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
  }

  return `/league/${leagueId}?${params.toString()}`;
}

function isLiveMatch(match: Pick<Match, "status">) {
  return match.status === "live";
}

function sortPricedMatches(matches: MatchBestOdds[], sort: string) {
  const sorted = [...matches];
  sorted.sort((left, right) => {
    if (sort === "edge" && left.combined_margin !== right.combined_margin) {
      return left.combined_margin - right.combined_margin;
    }

    if (sort === "coverage" && left.bookmakers.length !== right.bookmakers.length) {
      return right.bookmakers.length - left.bookmakers.length;
    }

    return new Date(left.start_time).getTime() - new Date(right.start_time).getTime();
  });
  return sorted;
}

function sortFixtures(matches: Match[], pricedMatches: MatchBestOdds[], sort: string) {
  const coverageByMatch = new Map(pricedMatches.map((match) => [match.id, match.bookmakers.length]));
  const marginByMatch = new Map(pricedMatches.map((match) => [match.id, match.combined_margin]));
  const sorted = [...matches];

  sorted.sort((left, right) => {
    if (sort === "edge") {
      const leftMargin = marginByMatch.get(left.id) ?? Number.POSITIVE_INFINITY;
      const rightMargin = marginByMatch.get(right.id) ?? Number.POSITIVE_INFINITY;
      if (leftMargin !== rightMargin) {
        return leftMargin - rightMargin;
      }
    }

    if (sort === "coverage") {
      const leftCoverage = coverageByMatch.get(left.id) ?? 0;
      const rightCoverage = coverageByMatch.get(right.id) ?? 0;
      if (leftCoverage !== rightCoverage) {
        return rightCoverage - leftCoverage;
      }
    }

    return new Date(left.start_time).getTime() - new Date(right.start_time).getTime();
  });

  return sorted;
}

export function LeagueLiveSection({
  league,
  date,
  status,
  sort,
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

  const liveCount = matches.filter((match) => isLiveMatch(match)).length;
  const upcomingCount = matches.length - liveCount;
  const statusFilter =
    status === "live" || status === "upcoming"
      ? status
      : liveCount > 0
        ? "live"
        : "upcoming";
  const sortMode = SORT_OPTIONS.some((option) => option.value === sort) ? sort ?? "kickoff" : "kickoff";

  const filteredMatches = matches.filter((match) =>
    statusFilter === "live" ? isLiveMatch(match) : !isLiveMatch(match)
  );
  const filteredPricedMatches = pricedMatches.filter((match) =>
    statusFilter === "live" ? isLiveMatch(match) : !isLiveMatch(match)
  );
  const sortedMatches = sortFixtures(filteredMatches, filteredPricedMatches, sortMode);
  const sortedPricedMatches = sortPricedMatches(filteredPricedMatches, sortMode);

  const bestOddsByMatch = new Map(
    filteredPricedMatches.map((match) => [
      match.id,
      {
        match_id: match.id,
        market: match.market,
        selections: match.selections,
        combined_margin: match.combined_margin,
      } satisfies BestOdds,
    ])
  );
  const crossBookmakerMatches = sortedPricedMatches.filter((match) => match.bookmakers.length >= 2);
  const nextMatch = sortedMatches[0];
  const activeBookmakers = BOOKMAKER_ORDER.filter((bookmaker) =>
    filteredPricedMatches.some((match) => match.bookmakers.includes(bookmaker))
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
            <p className="text-sm font-semibold text-slate-900">Filters</p>
            <LiveUpdatesBadge
              leagueId={league.id}
              date={date}
              className="mt-3"
              onUpdate={() => {
                queryClient.invalidateQueries({ queryKey: matchesQueryKey });
                queryClient.invalidateQueries({ queryKey: pricedMatchesQueryKey });
              }}
            />

            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                Sort board
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {SORT_OPTIONS.map((option) => (
                  <Link
                    key={option.value}
                    href={buildLeagueHref(
                      league.id,
                      { date, status: statusFilter, sort: sortMode },
                      { sort: option.value }
                    )}
                    className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                      sortMode === option.value
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {option.label}
                  </Link>
                ))}
              </div>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {DATE_FILTERS.map((option) => (
                <Link
                  key={option.value}
                  href={buildLeagueHref(
                    league.id,
                    { date, status: statusFilter, sort: sortMode },
                    { date: option.value }
                  )}
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

            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                Match state
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {STATUS_FILTERS.map((option) => {
                  const count = option.value === "live" ? liveCount : upcomingCount;
                  return (
                    <Link
                      key={option.value}
                      href={buildLeagueHref(
                        league.id,
                        { date, status: statusFilter, sort: sortMode },
                        { status: option.value }
                      )}
                      className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                        statusFilter === option.value
                          ? "bg-rose-600 text-white"
                          : "bg-rose-50 text-rose-700 hover:bg-rose-100"
                      }`}
                    >
                      {option.label} ({count})
                    </Link>
                  );
                })}
              </div>
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
            value={String(pricedMatches.filter((match) => match.bookmakers.length >= 2).length)}
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
              Next in this tab
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
            {statusFilter} 1X2 comparisons, sorted by{" "}
            {SORT_OPTIONS.find((option) => option.value === sortMode)?.label.toLowerCase()}.
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
            title={`No ${statusFilter} merged comparisons yet`}
            body="This league has no overlapping bookmaker coverage for the current tab and filters."
          />
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">All fixtures</h2>
          <p className="mt-1 text-sm text-slate-500">
            Every {statusFilter} fixture for the selected date, with best available 1X2 prices when
            present.
          </p>
        </div>

        {sortedMatches.length > 0 ? (
          <div className="grid gap-3">
            {sortedMatches.map((match) => (
              <MatchCard key={match.id} match={match} bestOdds={bestOddsByMatch.get(match.id)} />
            ))}
          </div>
        ) : (
          <EmptyState
            title={`No ${statusFilter} fixtures for this date`}
            body="Try switching tabs or dates, or come back after the next scraper cycle."
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
