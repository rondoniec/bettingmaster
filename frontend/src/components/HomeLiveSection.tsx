"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Sparkles, Trophy } from "lucide-react";
import Link from "next/link";

import { BestOddsMatchCard } from "@/components/BestOddsMatchCard";
import { LiveUpdatesBadge } from "@/components/LiveUpdatesBadge";
import { ScrapeHealthPanel } from "@/components/ScrapeHealthPanel";
import {
  getMatchesWithBestOdds,
  getSurebets,
  type HealthStatus,
  type MatchBestOdds,
  type Sport,
  type Surebet,
} from "@/lib/api";
import { BOOKMAKER_ORDER, getBookmakerDisplay } from "@/lib/constants";
import { formatFullDate, formatMargin } from "@/lib/utils";

type Props = {
  date: string;
  sport?: string;
  market: string;
  status?: string;
  sort?: string;
  initialHealth: HealthStatus;
  sports: Sport[];
  initialMatches: MatchBestOdds[];
  initialSurebets: Surebet[];
};

const DATE_FILTERS = [
  { value: "next24", label: "Next 24h" },
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

function isLiveMatch(match: Pick<MatchBestOdds, "status">) {
  return match.status === "live";
}

function filterMatchesByStatus(matches: MatchBestOdds[], statusFilter: string) {
  if (statusFilter === "live") {
    return matches.filter((match) => isLiveMatch(match));
  }

  return matches.filter((match) => !isLiveMatch(match));
}

function sortMatches(matches: MatchBestOdds[], sort: string) {
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

function buildHref(
  current: {
    date: string;
    sport?: string;
    market: string;
    status?: string;
    sort?: string;
  },
  updates: Record<string, string | undefined>
) {
  const params = new URLSearchParams();
  params.set("date", current.date);
  params.set("market", current.market);
  if (current.sport) {
    params.set("sport", current.sport);
  }
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

  const query = params.toString();
  return query ? `/?${query}` : "/";
}

export function HomeLiveSection({
  date,
  sport,
  market,
  status,
  sort,
  initialHealth,
  sports,
  initialMatches,
  initialSurebets,
}: Props) {
  const queryClient = useQueryClient();
  const matchesQueryKey = ["matches-best-odds", date, sport ?? "", market];
  const surebetsQueryKey = ["surebets"];

  const { data: matches = [] } = useQuery({
    queryKey: matchesQueryKey,
    queryFn: () => getMatchesWithBestOdds({ date, sport, market }),
    initialData: initialMatches,
  });

  const { data: surebets = [] } = useQuery({
    queryKey: surebetsQueryKey,
    queryFn: getSurebets,
    initialData: initialSurebets,
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
  const visibleMatches = sortMatches(filterMatchesByStatus(matches, statusFilter), sortMode);

  const bestMarginMatch = matches.length
    ? matches.reduce((best, current) =>
        current.combined_margin < best.combined_margin ? current : best
      )
    : null;
  const activeBookmakers = BOOKMAKER_ORDER.filter(
    (bookmaker) =>
      matches.some((match) => match.bookmakers.includes(bookmaker)) ||
      surebets.some((surebet) =>
        surebet.selections.some((selection) => selection.bookmaker === bookmaker)
      )
  );

  return (
    <>
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.22),_transparent_34%),radial-gradient(circle_at_top_right,_rgba(16,185,129,0.18),_transparent_28%),linear-gradient(135deg,_#f8fbff,_#ffffff_48%,_#f6fff8)] px-6 py-8 shadow-[0_28px_80px_-40px_rgba(15,23,42,0.45)] sm:px-8 sm:py-10">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(300px,1fr)]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 backdrop-blur">
              <Sparkles className="h-3.5 w-3.5" />
              Market view
            </div>
            <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
              Premier League and La Liga odds, next 24 hours only.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
              We only track near-term Premier League and La Liga matches now, with each price marked
              by the time it was last checked.
            </p>

            <div className="mt-6 flex flex-wrap gap-3">
              <MetricCard
                label="Merged matches"
                value={String(matches.length)}
                icon={<CalendarDays className="h-4 w-4" />}
              />
              <MetricCard
                label="Live surebets"
                value={String(surebets.length)}
                icon={<Trophy className="h-4 w-4" />}
              />
              <MetricCard
                label="Best margin"
                value={bestMarginMatch ? formatMargin(bestMarginMatch.combined_margin) : "-"}
                icon={<Sparkles className="h-4 w-4" />}
              />
            </div>

            {activeBookmakers.length > 0 ? (
              <div className="mt-6">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                  Active bookmakers in this view
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
          </div>

          <div className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 backdrop-blur">
            <p className="text-sm font-semibold text-slate-900">Filters</p>
            <LiveUpdatesBadge
              sport={sport}
              date={date}
              className="mt-4"
              onUpdate={() => {
                queryClient.invalidateQueries({ queryKey: matchesQueryKey });
                queryClient.invalidateQueries({ queryKey: surebetsQueryKey });
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
                    href={buildHref(
                      { date, sport, market, status: statusFilter, sort: sortMode },
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

            <div className="mt-4 flex flex-wrap gap-2">
              {DATE_FILTERS.map((option) => (
                <Link
                  key={option.value}
                  href={buildHref(
                    { date, sport, market, status: statusFilter, sort: sortMode },
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
                      href={buildHref(
                        { date, sport, market, status: statusFilter, sort: sortMode },
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

            <div className="mt-4 flex flex-wrap gap-2">
              <Link
                href={buildHref(
                  { date, sport, market, status: statusFilter, sort: sortMode },
                  { sport: undefined }
                )}
                className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                  !sport
                    ? "bg-blue-600 text-white"
                    : "bg-blue-50 text-blue-700 hover:bg-blue-100"
                }`}
              >
                All sports
              </Link>
              {sports.map((item) => (
                <Link
                  key={item.id}
                  href={buildHref(
                    { date, sport, market, status: statusFilter, sort: sortMode },
                    { sport: item.id }
                  )}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                    sport === item.id
                      ? "bg-blue-600 text-white"
                      : "bg-blue-50 text-blue-700 hover:bg-blue-100"
                  }`}
                >
                  {item.name}
                </Link>
              ))}
            </div>

            <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                Highlight
              </p>
              {bestMarginMatch ? (
                <>
                  <p className="mt-2 text-lg font-semibold text-slate-950">
                    {bestMarginMatch.home_team} vs {bestMarginMatch.away_team}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    {formatFullDate(bestMarginMatch.start_time)}
                  </p>
                  <p className="mt-3 text-sm text-slate-600">
                    Strongest current comparison with a combined margin of{" "}
                    <span className="font-semibold text-emerald-700">
                      {formatMargin(bestMarginMatch.combined_margin)}
                    </span>
                    .
                  </p>
                </>
              ) : (
                <p className="mt-2 text-sm text-slate-500">
                  As soon as merged comparisons are available, the strongest card shows up here.
                </p>
              )}
            </div>
          </div>
        </div>
      </section>

      <ScrapeHealthPanel initialHealth={initialHealth} />

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
              Best odds board
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Showing {statusFilter} Premier League and La Liga {market.toUpperCase()} comparisons for {date}, sorted
              by {SORT_OPTIONS.find((option) => option.value === sortMode)?.label.toLowerCase()}.
            </p>
          </div>
          <Link
            href="/surebets"
            className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-100"
          >
            Open surebets
          </Link>
        </div>

        {visibleMatches.length > 0 ? (
          <div className="grid gap-5">
            {visibleMatches.map((match) => (
              <BestOddsMatchCard key={match.id} match={match} />
            ))}
          </div>
        ) : (
          <EmptyState
            title={`No ${statusFilter} comparisons yet`}
            body="The current filters did not produce any cross-bookmaker matches for this view."
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
