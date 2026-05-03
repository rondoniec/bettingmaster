import Link from "next/link";

import { Countdown } from "@/components/Countdown";
import { BookmakerChip, Kicker, LiveBadge } from "@/components/Primitives";
import type { BestOdds, Match } from "@/lib/api";
import { formatMatchTime, formatOdds } from "@/lib/utils";

type Props = {
  match: Match;
  bestOdds?: BestOdds | null;
};

export function MatchCard({ match, bestOdds }: Props) {
  const best1x2 = bestOdds?.market === "1x2" ? bestOdds : null;
  const homeOdds = best1x2?.selections.find((s) => s.selection === "home");
  const drawOdds = best1x2?.selections.find((s) => s.selection === "draw");
  const awayOdds = best1x2?.selections.find((s) => s.selection === "away");
  const isLive = match.status === "live";

  return (
    <Link href={`/match/${match.id}`} className="group block">
      <div className="flex items-center gap-4 border border-slate-200 bg-white px-4 py-3 transition group-hover:border-slate-400">
        <div className="flex w-24 shrink-0 flex-col items-start gap-1 text-left">
          <span className="font-mono text-[11px] tabular-nums text-slate-500">
            {formatMatchTime(match.start_time)}
          </span>
          <Countdown startTime={match.start_time} status={match.status} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-semibold text-slate-900">{match.home_team}</p>
            {isLive ? <LiveBadge /> : null}
          </div>
          <p className="truncate text-sm text-slate-600">{match.away_team}</p>
        </div>

        {best1x2 ? (
          <div className="flex shrink-0 gap-px border border-slate-200 bg-slate-200 p-px">
            <OddsCell label="1" entry={homeOdds} />
            <OddsCell label="X" entry={drawOdds} />
            <OddsCell label="2" entry={awayOdds} />
          </div>
        ) : (
          <div className="shrink-0 font-mono text-[11px] uppercase tracking-wider text-slate-400">
            Bez kurzov
          </div>
        )}
      </div>
    </Link>
  );
}

function OddsCell({
  label,
  entry,
}: {
  label: string;
  entry?: { odds?: number; bookmaker?: string };
}) {
  if (!entry?.odds) {
    return (
      <div className="flex h-12 w-16 flex-col items-center justify-center bg-white text-center">
        <Kicker>{label}</Kicker>
        <span className="font-mono text-xs text-slate-300">—</span>
      </div>
    );
  }
  return (
    <div
      className="flex h-12 w-16 flex-col items-center justify-center bg-white text-center"
      title={entry.bookmaker ? `Najlepší kurz: ${entry.bookmaker}` : undefined}
    >
      <Kicker>{label}</Kicker>
      <span className="font-mono text-sm font-semibold tabular-nums text-slate-900">
        {formatOdds(entry.odds)}
      </span>
    </div>
  );
}
