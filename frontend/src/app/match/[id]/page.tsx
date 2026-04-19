import { notFound } from "next/navigation";

import { MatchLiveSection } from "@/components/MatchLiveSection";
import { getBestOdds, getMatchDetail } from "@/lib/api";

export const dynamic = "force-dynamic";

type MatchPageProps = {
  params: Promise<{
    id: string;
  }>;
  searchParams?: Promise<{
    market?: string;
    selection?: string;
    bookmaker?: string;
  }>;
};

async function loadMatchPageData(matchId: string) {
  try {
    const [match, bestOdds] = await Promise.all([getMatchDetail(matchId), getBestOdds(matchId)]);
    return { match, bestOdds };
  } catch {
    return null;
  }
}

export default async function MatchPage({ params, searchParams }: MatchPageProps) {
  const { id } = await params;
  const resolvedSearch = await searchParams;
  const data = await loadMatchPageData(id);
  if (!data) {
    notFound();
  }

  return (
    <MatchLiveSection
      initialMatch={data.match}
      initialBestOdds={data.bestOdds}
      focusTarget={{
        market: resolvedSearch?.market,
        selection: resolvedSearch?.selection,
        bookmaker: resolvedSearch?.bookmaker,
      }}
    />
  );
}
