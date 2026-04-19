import { notFound } from "next/navigation";

import { LeagueLiveSection } from "@/components/LeagueLiveSection";
import { getLeague, getMatchesByLeague, getMatchesWithBestOdds } from "@/lib/api";

export const dynamic = "force-dynamic";

type LeaguePageProps = {
  params: Promise<{
    id: string;
  }>;
  searchParams?: Promise<{
    date?: string;
    status?: string;
    sort?: string;
  }>;
};

async function loadLeaguePageData(leagueId: string, date: string) {
  try {
    const [league, matches, pricedMatches] = await Promise.all([
      getLeague(leagueId),
      getMatchesByLeague(leagueId, date),
      getMatchesWithBestOdds({
        league_id: leagueId,
        date,
        market: "1x2",
        min_bookmakers: 1,
      }),
    ]);
    return { league, matches, pricedMatches };
  } catch {
    return null;
  }
}

export default async function LeaguePage({ params, searchParams }: LeaguePageProps) {
  const { id } = await params;
  const resolvedSearch = await searchParams;
  const date = resolvedSearch?.date ?? "today";
  const status = resolvedSearch?.status;
  const sort = resolvedSearch?.sort;
  const data = await loadLeaguePageData(id, date);

  if (!data) {
    notFound();
  }

  return (
    <LeagueLiveSection
      league={data.league}
      date={date}
      status={status}
      sort={sort}
      initialMatches={data.matches}
      initialPricedMatches={data.pricedMatches}
    />
  );
}
