"use client";

import { ExternalLink } from "lucide-react";

import type { OddsEntry } from "@/lib/api";
import {
  BOOKMAKER_ORDER,
  getBookmakerDisplay,
  resolveSelectionLabel,
  SELECTION_ORDER,
} from "@/lib/constants";
import { cn, formatLastUpdated, formatMargin, formatOdds } from "@/lib/utils";

type Props = {
  market: string;
  odds: OddsEntry[];
  combinedMargin?: number;
  focusedBookmaker?: string;
  focusedSelection?: string;
  homeTeam?: string;
  awayTeam?: string;
};

export function OddsTable({ market, odds, combinedMargin, focusedBookmaker, focusedSelection, homeTeam, awayTeam }: Props) {
  const oddsMap: Record<string, Record<string, OddsEntry>> = {};
  for (const entry of odds) {
    if (entry.market !== market) {
      continue;
    }
    if (!oddsMap[entry.bookmaker]) {
      oddsMap[entry.bookmaker] = {};
    }
    oddsMap[entry.bookmaker][entry.selection] = entry;
  }

  const selectionOrder =
    SELECTION_ORDER[market] ??
    Array.from(
      new Set(odds.filter((entry) => entry.market === market).map((entry) => entry.selection))
    );

  const activeBookmakers = BOOKMAKER_ORDER.filter((bookmaker) => oddsMap[bookmaker]);

  const bestOddsPerSelection: Record<string, number> = {};
  for (const selection of selectionOrder) {
    let best = 0;
    for (const bookmaker of activeBookmakers) {
      const value = oddsMap[bookmaker]?.[selection]?.odds ?? 0;
      if (value > best) {
        best = value;
      }
    }
    bestOddsPerSelection[selection] = best;
  }

  if (activeBookmakers.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 py-12 text-center text-sm text-slate-400">
        No odds available for this market
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {combinedMargin !== undefined ? (
        <div className="flex items-center justify-end gap-2">
          <span className="text-xs text-slate-500">Margin:</span>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-semibold",
              combinedMargin < 0
                ? "bg-emerald-100 text-emerald-700"
                : combinedMargin < 5
                ? "bg-amber-100 text-amber-700"
                : "bg-red-100 text-red-700"
            )}
          >
            {formatMargin(combinedMargin)}
          </span>
        </div>
      ) : null}

      <div className="odds-scroll overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full min-w-[480px] text-sm">
          <thead>
            <tr className="border-b bg-slate-50">
              <th className="sticky left-0 z-10 min-w-[120px] bg-slate-50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                Bookmaker
              </th>
              {selectionOrder.map((selection) => (
                <th
                  key={selection}
                  className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500"
                >
                  {resolveSelectionLabel(selection, homeTeam, awayTeam)}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100 bg-white">
            {activeBookmakers.map((bookmaker) => {
              const bookmakerData = getBookmakerDisplay(bookmaker);
              const isFocusedBookmaker = bookmaker === focusedBookmaker;
              return (
                <tr
                  key={bookmaker}
                  className={cn(
                    "transition hover:bg-slate-50/60",
                    isFocusedBookmaker ? "bg-blue-50/60" : undefined
                  )}
                >
                  <td
                    className={cn(
                      "sticky left-0 z-10 px-4 py-3 font-semibold",
                      isFocusedBookmaker ? "bg-blue-50" : "bg-white"
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: bookmakerData.color }}
                      />
                      <span style={{ color: bookmakerData.color }}>
                        {bookmakerData.displayName}
                      </span>
                    </div>
                  </td>

                  {selectionOrder.map((selection) => {
                    const entry = oddsMap[bookmaker]?.[selection];
                    const isBest =
                      entry &&
                      entry.odds === bestOddsPerSelection[selection] &&
                      entry.odds > 0;
                    const isFocused = bookmaker === focusedBookmaker && selection === focusedSelection;

                    return (
                      <td key={selection} className="px-4 py-3 text-center">
                        {entry ? (
                          <>
                            <div
                              className={cn(
                                "inline-flex items-center gap-1 rounded-lg px-2 py-1 font-bold tabular-nums",
                                isFocused
                                  ? "ring-2 ring-blue-500 ring-offset-1"
                                  : undefined,
                                isBest ? "best-odds bg-emerald-100 text-emerald-800" : "text-slate-700"
                              )}
                            >
                              {formatOdds(entry.odds)}
                              {isBest && entry.url ? (
                                <a
                                  href={entry.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={(event) => event.stopPropagation()}
                                  className="ml-1 text-emerald-600 hover:text-emerald-800"
                                  title={`Open at ${bookmakerData.displayName}`}
                                >
                                  <ExternalLink className="h-3 w-3" />
                                </a>
                              ) : null}
                            </div>
                            <div className="mt-1 text-[10px] text-slate-400">
                              price {formatLastUpdated(entry.scraped_at)}
                              {entry.checked_at ? ` • checked ${formatLastUpdated(entry.checked_at)}` : ""}
                            </div>
                          </>
                        ) : (
                          <span className="text-slate-300">-</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>

          <tfoot>
            <tr className="border-t-2 border-emerald-200 bg-emerald-50">
              <td className="sticky left-0 z-10 bg-emerald-50 px-4 py-3 text-xs font-bold uppercase tracking-wide text-emerald-700">
                Best
              </td>
              {selectionOrder.map((selection) => {
                const bestOdds = bestOddsPerSelection[selection];
                const bestEntry = activeBookmakers
                  .map((bookmaker) => oddsMap[bookmaker]?.[selection])
                  .filter(Boolean)
                  .find((entry) => entry!.odds === bestOdds);
                const bestBookmaker = activeBookmakers.find(
                  (bookmaker) => oddsMap[bookmaker]?.[selection]?.odds === bestOdds
                );
                const bookmakerData = bestBookmaker
                  ? getBookmakerDisplay(bestBookmaker)
                  : null;

                return (
                  <td key={selection} className="px-4 py-3 text-center">
                    {bestOdds > 0 ? (
                      <div className="flex flex-col items-center gap-0.5">
                        <div className="flex items-center gap-1">
                          <span className="text-base font-bold tabular-nums text-emerald-800">
                            {formatOdds(bestOdds)}
                          </span>
                          {bestEntry?.url ? (
                            <a
                              href={bestEntry.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-emerald-600 hover:text-emerald-800"
                              title="Open bookmaker"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          ) : null}
                        </div>
                        {bookmakerData ? (
                          <span
                            className="text-[10px] font-semibold"
                            style={{ color: bookmakerData.color }}
                          >
                            {bookmakerData.displayName}
                          </span>
                        ) : null}
                      </div>
                    ) : (
                      <span className="text-slate-300">-</span>
                    )}
                  </td>
                );
              })}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
