"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { BestOddsMatchCard } from "@/components/BestOddsMatchCard";
import { BookmakerToggleBar } from "@/components/BookmakerToggleBar";
import { Countdown } from "@/components/Countdown";
import { BookmakerChip, Kicker, MarginChip, Tab } from "@/components/Primitives";
import { LiveUpdatesBadge } from "@/components/LiveUpdatesBadge";
import { ScrapeHealthPanel } from "@/components/ScrapeHealthPanel";
import { useBookmakerFilter } from "@/hooks/useBookmakerFilter";
import {
  getMatchesWithBestOdds,
  getSurebets,
  type HealthStatus,
  type MatchBestOdds,
  type Sport,
  type Surebet,
} from "@/lib/api";
import { BOOKMAKER_ORDER } from "@/lib/constants";
import { formatMargin } from "@/lib/utils";

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
  const { enabledList, hydrated: filterHydrated } = useBookmakerFilter();
  // Stable cache key based on enabled bookmakers so toggles invalidate.
  const bookmakerKey = enabledList.join(",");
  const matchesQueryKey = ["matches-best-odds", date, sport ?? "", market, bookmakerKey];
  const surebetsQueryKey = ["surebets"];

  const { data: matches = [] } = useQuery({
    queryKey: matchesQueryKey,
    queryFn: () =>
      getMatchesWithBestOdds({
        date,
        sport,
        market,
        bookmakers: filterHydrated && enabledList.length > 0 ? enabledList : undefined,
      }),
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
    <div className="space-y-6">
      {/* HeroBoard — flat data-terminal title + stats strip */}
      <section className="border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="max-w-[720px]">
            <Kicker>Market view · DNES</Kicker>
            <h1 className="mt-2 text-[30px] font-semibold leading-[1.15] tracking-[-0.02em] text-slate-900">
              Najlepšie kurzy na Premier League a La Liga, v reálnom čase.
            </h1>
            <p className="mt-3 max-w-[560px] text-[13px] leading-6 text-slate-600">
              Sledujeme len blízke zápasy najvyšších anglickej a španielskej ligy. Pri každom kurze
              vidíš čas posledného overenia.
            </p>
          </div>

          <div className="flex divide-x divide-slate-200">
            <Stat label="Zápasy" value={String(matches.length)} />
            <Stat
              label="Sigurebety"
              value={String(surebets.length)}
              tone={surebets.length > 0 ? "emerald" : "slate"}
            />
            <Stat
              label="Najlepšia marža"
              value={bestMarginMatch ? formatMargin(bestMarginMatch.combined_margin) : "—"}
              tone={bestMarginMatch && bestMarginMatch.combined_margin < 0 ? "emerald" : "slate"}
            />
          </div>
        </div>

        {/* Filter bar */}
        <div className="mt-6 grid gap-x-8 gap-y-3 border-t border-slate-200 pt-4 sm:flex sm:flex-wrap">
          <FilterGroup label="Stav">
            {STATUS_FILTERS.map((option) => {
              const count = option.value === "live" ? liveCount : upcomingCount;
              return (
                <FilterTab
                  key={option.value}
                  active={statusFilter === option.value}
                  href={buildHref(
                    { date, sport, market, status: statusFilter, sort: sortMode },
                    { status: option.value },
                  )}
                >
                  {option.label} <span className="text-slate-400">({count})</span>
                </FilterTab>
              );
            })}
          </FilterGroup>

          <FilterGroup label="Dátum">
            {DATE_FILTERS.map((option) => (
              <FilterTab
                key={option.value}
                active={date === option.value}
                href={buildHref(
                  { date, sport, market, status: statusFilter, sort: sortMode },
                  { date: option.value },
                )}
              >
                {option.label}
              </FilterTab>
            ))}
          </FilterGroup>

          <FilterGroup label="Zoradiť">
            {SORT_OPTIONS.map((option) => (
              <FilterTab
                key={option.value}
                active={sortMode === option.value}
                href={buildHref(
                  { date, sport, market, status: statusFilter, sort: sortMode },
                  { sort: option.value },
                )}
              >
                {option.label}
              </FilterTab>
            ))}
          </FilterGroup>

          <FilterGroup label="Šport">
            <FilterTab
              active={!sport}
              href={buildHref(
                { date, sport, market, status: statusFilter, sort: sortMode },
                { sport: undefined },
              )}
            >
              Všetky
            </FilterTab>
            {sports.map((item) => (
              <FilterTab
                key={item.id}
                active={sport === item.id}
                href={buildHref(
                  { date, sport, market, status: statusFilter, sort: sortMode },
                  { sport: item.id },
                )}
              >
                {item.name}
              </FilterTab>
            ))}
          </FilterGroup>
        </div>

        {/* Bookmaker row — lists active books in scope */}
        {activeBookmakers.length > 0 ? (
          <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-dashed border-slate-200 pt-3">
            <Kicker>Stávkové kancelárie v ponuke</Kicker>
            <div className="flex flex-wrap gap-1.5">
              {activeBookmakers.map((bookmaker) => (
                <BookmakerChip key={bookmaker} bookmaker={bookmaker} />
              ))}
            </div>
            <div className="ml-auto">
              <LiveUpdatesBadge
                sport={sport}
                date={date}
                onUpdate={() => {
                  queryClient.invalidateQueries({ queryKey: matchesQueryKey });
                  queryClient.invalidateQueries({ queryKey: surebetsQueryKey });
                }}
              />
            </div>
          </div>
        ) : null}
      </section>

      {/* Surebet banner */}
      {surebets.length > 0 && bestMarginMatch ? (
        <section className="flex items-center justify-between border border-emerald-200 border-l-[3px] border-l-emerald-700 bg-emerald-50 px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            <Kicker tone="emerald">Príležitosť</Kicker>
            <span className="text-[13px] text-slate-900">
              {surebets.length} {surebets.length === 1 ? "živá sigurebet" : "živých sigurebetov"} na boarde
            </span>
            {bestMarginMatch.combined_margin < 0 ? (
              <MarginChip margin={bestMarginMatch.combined_margin} />
            ) : null}
          </div>
          <Link
            href="/surebets"
            className="inline-flex items-center gap-1 font-mono text-[12px] font-semibold uppercase tracking-wider text-emerald-700 hover:text-emerald-800"
          >
            Zobraziť všetky
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </section>
      ) : null}

      <ScrapeHealthPanel initialHealth={initialHealth} />

      <BookmakerToggleBar />

      <section className="space-y-3">
        <header className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-200 pb-2">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-slate-900">
              Najlepšie kurzy
            </h2>
            <p className="mt-1 font-mono text-[11px] tabular-nums text-slate-500">
              {visibleMatches.length} {statusFilter === "live" ? "živých" : "nadchádzajúcich"} zápasov · {market.toUpperCase()}
            </p>
          </div>
        </header>

        {visibleMatches.length > 0 ? (
          <div className="flex flex-col gap-4">
            {visibleMatches.map((match) => (
              <BestOddsMatchCard key={match.id} match={match} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="Žiadne porovnania"
            body="Aktuálne filtre nepriniesli žiadne výsledky."
          />
        )}
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "slate",
}: {
  label: string;
  value: string;
  tone?: "slate" | "emerald";
}) {
  return (
    <div className="px-6 py-1 first:pl-0 last:pr-0">
      <Kicker>{label}</Kicker>
      <p
        className={`mt-1 font-mono text-[24px] font-semibold tabular-nums ${
          tone === "emerald" ? "text-emerald-700" : "text-slate-900"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function FilterGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <Kicker>{label}</Kicker>
      <div className="flex flex-wrap items-center gap-4">{children}</div>
    </div>
  );
}

function FilterTab({
  active,
  href,
  children,
}: {
  active: boolean;
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className="inline-block">
      <Tab active={active}>{children}</Tab>
    </Link>
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
