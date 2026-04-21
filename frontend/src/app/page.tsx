import { Search } from "lucide-react";
import Link from "next/link";

import { HomeLiveSection } from "@/components/HomeLiveSection";
import {
  getMatchesWithBestOdds,
  getSports,
  getSurebets,
  searchMatches,
  type Match,
  type Sport,
  type Surebet,
} from "@/lib/api";
import { formatMatchTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

type HomePageProps = {
  searchParams?: Promise<{
    date?: string;
    sport?: string;
    market?: string;
    q?: string;
    status?: string;
    sort?: string;
  }>;
};

async function loadHomeData({
  date,
  sport,
  market,
  q,
}: {
  date: string;
  sport?: string;
  market: string;
  q?: string;
}): Promise<{
  sports: Sport[];
  surebets: Surebet[];
  matches: Awaited<ReturnType<typeof getMatchesWithBestOdds>>;
  searchResults: Match[];
  error: string | null;
}> {
  try {
    const [sports, surebets, matches, searchResults] = await Promise.all([
      getSports(),
      getSurebets(),
      getMatchesWithBestOdds({ date, sport, market }),
      q ? searchMatches(q) : Promise.resolve([]),
    ]);

    return { sports, surebets, matches, searchResults, error: null };
  } catch (error) {
    return {
      sports: [],
      surebets: [],
      matches: [],
      searchResults: [],
      error: error instanceof Error ? error.message : "Could not load data.",
    };
  }
}

export default async function HomePage({ searchParams }: HomePageProps) {
  const resolvedParams = await searchParams;
  const date = resolvedParams?.date ?? "next24";
  const sport = resolvedParams?.sport;
  const market = resolvedParams?.market ?? "1x2";
  const q = resolvedParams?.q?.trim();
  const status = resolvedParams?.status;
  const sort = resolvedParams?.sort;

  const { sports, surebets, matches, searchResults, error } = await loadHomeData({
    date,
    sport,
    market,
    q,
  });

  return (
    <div className="space-y-8">
      {q ? (
        <section className="space-y-4">
          <div className="rounded-[1.75rem] border border-slate-200 bg-white px-6 py-6 shadow-[0_18px_45px_-32px_rgba(15,23,42,0.45)]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-slate-400" />
                <h2 className="text-lg font-semibold text-slate-950">
                  Search results for &quot;{q}&quot;
                </h2>
              </div>
              <Link
                href="/"
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100"
              >
                Clear search
              </Link>
            </div>
            <p className="mt-3 text-sm text-slate-500">
              {searchResults.length > 0
                ? `Found ${searchResults.length} matching ${searchResults.length === 1 ? "match" : "matches"}.`
                : "No matching upcoming or live matches found."}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-slate-400" />
            <h3 className="text-lg font-semibold text-slate-950">Matches</h3>
          </div>
          {searchResults.length > 0 ? (
            <div className="grid gap-3">
              {searchResults.map((match) => (
                <Link
                  key={match.id}
                  href={`/match/${match.id}`}
                  className="rounded-2xl border border-slate-200 bg-white px-5 py-4 transition hover:border-slate-300 hover:shadow-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm text-slate-500">{match.league_id}</p>
                      <p className="text-lg font-semibold text-slate-950">
                        {match.home_team} vs {match.away_team}
                      </p>
                    </div>
                    <div className="text-sm text-slate-500">
                      {formatMatchTime(match.start_time)}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No matches found"
              body="Try another team name or remove the search term to get back to the merged comparison board."
            />
          )}
        </section>
      ) : null}

      {!error ? (
        <HomeLiveSection
          date={date}
          sport={sport}
          market={market}
          status={status}
          sort={sort}
          sports={sports}
          initialMatches={matches}
          initialSurebets={surebets}
        />
      ) : (
        <EmptyState title="Frontend is ready, but the API did not answer" body={error} />
      )}
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
