import { Clock } from "lucide-react";
import Link from "next/link";

import { Countdown } from "@/components/Countdown";
import type { BestOdds, Match } from "@/lib/api";
import { formatMatchTime, formatOdds } from "@/lib/utils";

/** Produce a short chip label from a full team name (e.g. "Slovan Bratislava" → "Slovan"). */
function teamAbbrev(name: string): string {
  const firstWord = name.split(/\s+/)[0] ?? name;
  return firstWord.length <= 7 ? firstWord : firstWord.slice(0, 6);
}

type Props = {
  match: Match;
  bestOdds?: BestOdds | null;
};

export function MatchCard({ match, bestOdds }: Props) {
  const best1x2 = bestOdds?.market === "1x2" ? bestOdds : null;
  const homeOdds = best1x2?.selections.find((selection) => selection.selection === "home");
  const drawOdds = best1x2?.selections.find((selection) => selection.selection === "draw");
  const awayOdds = best1x2?.selections.find((selection) => selection.selection === "away");
  const isLive = match.status === "live";

  return (
    <Link href={`/match/${match.id}`} className="group block">
      <div className="flex items-center gap-3 rounded-lg border border-slate-100 bg-white px-4 py-3 transition group-hover:bg-blue-50/30 hover:border-blue-200 hover:shadow-sm">
        <div className="flex w-20 shrink-0 flex-col items-center gap-1 text-center">
          <div className="flex items-center gap-1">
            <Clock className="h-3 w-3 text-slate-400" />
            <span className="text-xs font-medium text-slate-500">
              {formatMatchTime(match.start_time)}
            </span>
          </div>
          <Countdown startTime={match.start_time} status={match.status} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-semibold text-slate-900">{match.home_team}</p>
            {isLive ? (
              <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-red-600">
                Live
              </span>
            ) : null}
          </div>
          <p className="truncate text-sm text-slate-600">{match.away_team}</p>
        </div>

        {best1x2 ? (
          <div className="flex shrink-0 gap-1.5">
            <OddsChip label={teamAbbrev(match.home_team)} odds={homeOdds?.odds} bookmaker={homeOdds?.bookmaker} />
            <OddsChip label="Draw" odds={drawOdds?.odds} bookmaker={drawOdds?.bookmaker} />
            <OddsChip label={teamAbbrev(match.away_team)} odds={awayOdds?.odds} bookmaker={awayOdds?.bookmaker} />
          </div>
        ) : (
          <div className="shrink-0 text-xs text-slate-400">Odds unavailable</div>
        )}
      </div>
    </Link>
  );
}

function OddsChip({
  label,
  odds,
  bookmaker,
}: {
  label: string;
  odds?: number;
  bookmaker?: string;
}) {
  if (!odds) {
    return (
      <div className="flex h-9 w-14 flex-col items-center justify-center rounded border border-slate-100 bg-slate-50 text-center">
        <span className="text-[10px] text-slate-400">{label}</span>
        <span className="text-xs text-slate-300">-</span>
      </div>
    );
  }

  return (
    <div
      className="flex h-9 w-14 flex-col items-center justify-center rounded border border-emerald-200 bg-emerald-50 text-center"
      title={bookmaker ? `Best price: ${bookmaker}` : undefined}
    >
      <span className="text-[10px] font-medium text-emerald-700">{label}</span>
      <span className="text-sm font-bold text-emerald-800">{formatOdds(odds)}</span>
    </div>
  );
}
