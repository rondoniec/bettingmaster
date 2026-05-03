import { ChevronRight, ExternalLink } from "lucide-react";
import Link from "next/link";

import { Countdown } from "@/components/Countdown";
import { BookmakerChip, Kicker, LiveBadge, MarginChip } from "@/components/Primitives";
import type { MatchBestOdds } from "@/lib/api";
import { resolveSelectionLabel } from "@/lib/constants";
import { cn, formatMatchTime, formatOdds } from "@/lib/utils";

type Props = {
  match: MatchBestOdds;
};

export function BestOddsMatchCard({ match }: Props) {
  const isLive = match.status === "live";
  const isSurebet = match.combined_margin < 0;

  // Determine the single highest odds across the three selections — that's
  // the "TOP PICK" (best bet on this card). Only that one cell goes emerald.
  let topSelection: string | null = null;
  let topValue = 0;
  for (const sel of match.selections) {
    if (sel.odds > topValue) {
      topValue = sel.odds;
      topSelection = sel.selection;
    }
  }

  return (
    <article
      className={cn(
        "border bg-white",
        isSurebet ? "border-slate-200 border-l-[3px] border-l-emerald-700" : "border-slate-200",
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href={`/league/${match.league_id}`}
              className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500 hover:text-slate-900"
            >
              {match.league_id.replace(/-/g, " ").toUpperCase()}
            </Link>
            <span className="font-mono text-[11px] tabular-nums text-slate-500">
              {formatMatchTime(match.start_time)}
            </span>
            {isLive ? <LiveBadge /> : <Countdown startTime={match.start_time} status={match.status} />}
          </div>
          <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-900">
            {match.home_team}
            <span className="mx-2 text-slate-400">vs</span>
            {match.away_team}
          </h2>
          <p className="mt-1 font-mono text-[11px] tabular-nums text-slate-500">
            {match.bookmakers.length} stávkových kancelárií porovnaných
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <MarginChip margin={match.combined_margin} />
          <Link
            href={`/match/${match.id}`}
            className="inline-flex items-center gap-1 bg-slate-900 px-3.5 py-1.5 text-[12px] font-semibold text-white transition hover:bg-slate-700"
          >
            Otvoriť
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </header>

      <div className="m-4 grid grid-cols-3 gap-px border border-slate-200 bg-slate-200 p-px">
        {match.selections.map((selection) => {
          const isTop = selection.selection === topSelection;
          return (
            <div key={selection.selection} className="bg-white p-4">
              <div className="flex items-start justify-between gap-2">
                <Kicker>
                  {resolveSelectionLabel(selection.selection, match.home_team, match.away_team)}
                </Kicker>
                {isTop ? (
                  <span className="bg-emerald-700 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-white">
                    Top kurz
                  </span>
                ) : null}
              </div>
              <p
                className={cn(
                  "mt-2 font-mono text-[28px] font-semibold tracking-[-0.02em] tabular-nums",
                  isTop ? "text-emerald-700" : "text-slate-900",
                )}
              >
                {formatOdds(selection.odds)}
              </p>
              <div className="mt-3 flex items-center justify-between gap-2">
                <BookmakerChip bookmaker={selection.bookmaker} />
                {selection.url ? (
                  <a
                    href={selection.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-900"
                  >
                    Otvoriť
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </article>
  );
}
