import { ExternalLink, ShieldCheck } from "lucide-react";
import Link from "next/link";

import type { MatchBestOdds } from "@/lib/api";
import { getBookmakerDisplay, resolveSelectionLabel } from "@/lib/constants";
import { cn, formatLastUpdated, formatMargin, formatMatchTime, formatOdds } from "@/lib/utils";

type Props = {
  match: MatchBestOdds;
};

export function BestOddsMatchCard({ match }: Props) {
  const isLive = match.status === "live";

  return (
    <article className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_18px_45px_-32px_rgba(15,23,42,0.45)]">
      <div className="border-b border-slate-100 bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.16),_transparent_38%),radial-gradient(circle_at_top_right,_rgba(16,185,129,0.14),_transparent_32%),linear-gradient(180deg,_#ffffff,_#f8fbff)] px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Link
                href={`/league/${match.league_id}`}
                className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 transition hover:text-blue-600"
              >
                {match.league_id}
              </Link>
              {isLive ? (
                <span className="animate-pulse rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-red-600">
                  Live
                </span>
              ) : null}
            </div>
            <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">
              {match.home_team}
              <span className="mx-2 text-slate-300">vs</span>
              {match.away_team}
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              {formatMatchTime(match.start_time)} • {match.bookmakers.length} bookmakers compared
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div
              className={cn(
                "rounded-full px-3 py-1 text-sm font-semibold",
                match.combined_margin < 0
                  ? "bg-emerald-100 text-emerald-700"
                  : match.combined_margin < 5
                  ? "bg-amber-100 text-amber-700"
                  : "bg-slate-100 text-slate-600"
              )}
            >
              Margin {formatMargin(match.combined_margin)}
            </div>
            <Link
              href={`/match/${match.id}`}
              className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
            >
              Open match
            </Link>
          </div>
        </div>
      </div>

      <div className="grid gap-3 p-5 sm:grid-cols-3 sm:p-6">
        {match.selections.map((selection) => {
          const bookmaker = getBookmakerDisplay(selection.bookmaker);
          return (
            <div
              key={selection.selection}
              className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                    {resolveSelectionLabel(selection.selection, match.home_team, match.away_team)}
                  </p>
                  <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
                    {formatOdds(selection.odds)}
                  </p>
                </div>
                <div
                  className="rounded-full px-2.5 py-1 text-xs font-semibold"
                  style={{
                    backgroundColor: bookmaker.bgColor,
                    color: bookmaker.color,
                  }}
                >
                  {bookmaker.displayName}
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-emerald-500" />
                  <span>Best for this outcome</span>
                </div>
                {selection.url ? (
                  <a
                    href={selection.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-medium text-slate-700 transition hover:text-slate-950"
                  >
                    Visit
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                ) : null}
              </div>
              <p className="mt-3 text-xs text-slate-400">
                Data from {formatLastUpdated(selection.scraped_at)}
              </p>
            </div>
          );
        })}
      </div>
    </article>
  );
}
