"use client";

import { ExternalLink } from "lucide-react";

import type { BestOdds, OddsEntry } from "@/lib/api";
import {
  BOOKMAKER_ORDER,
  getBookmakerDisplay,
  getMarketLabel,
  resolveSelectionLabel,
  SELECTION_ORDER,
} from "@/lib/constants";
import { cn, formatLastUpdated, formatMargin, formatOdds } from "@/lib/utils";

type Props = {
  markets: string[];
  odds: OddsEntry[];
  bestOdds: BestOdds[];
  focusedBookmaker?: string;
  focusedMarket?: string | null;
  focusedSelection?: string;
  homeTeam: string;
  awayTeam: string;
};

function bookmakerRank(bookmaker: string) {
  const index = BOOKMAKER_ORDER.indexOf(bookmaker);
  return index === -1 ? BOOKMAKER_ORDER.length : index;
}

function orderSelections(market: string, entries: OddsEntry[]) {
  const preferred = SELECTION_ORDER[market] ?? [];
  const present = Array.from(new Set(entries.map((entry) => entry.selection)));
  return [
    ...preferred.filter((selection) => present.includes(selection)),
    ...present.filter((selection) => !preferred.includes(selection)).sort(),
  ];
}

export function MarketOddsBoard({
  markets,
  odds,
  bestOdds,
  focusedBookmaker,
  focusedMarket,
  focusedSelection,
  homeTeam,
  awayTeam,
}: Props) {
  const marginByMarket = new Map(bestOdds.map((market) => [market.market, market.combined_margin]));
  const displayMarkets = markets
    .map((market) => {
      const marketOdds = odds.filter((entry) => entry.market === market);
      const selections = orderSelections(market, marketOdds).filter(
        (selection) => marketOdds.filter((entry) => entry.selection === selection).length >= 2
      );
      return { market, marketOdds, selections };
    })
    .filter((item) => item.selections.length > 0);

  if (displayMarkets.length === 0) {
    return (
      <div className="rounded-[1.75rem] border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
        <h2 className="text-xl font-semibold text-slate-950">No comparable odds on this match yet</h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-slate-500">
          We only show outcomes when at least two bookmakers have returned a price for the same market.
        </p>
      </div>
    );
  }

  return (
    <section className="space-y-5">
      {displayMarkets.map(({ market, marketOdds, selections }) => {
        const gridClass =
          selections.length >= 3
            ? "lg:grid-cols-3"
            : selections.length === 2
              ? "sm:grid-cols-2"
              : "sm:grid-cols-1";

        return (
          <article
            key={market}
            id={`market-${market}`}
            className="scroll-mt-24 overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white shadow-[0_18px_45px_-34px_rgba(15,23,42,0.45)]"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-[linear-gradient(135deg,_#f8fbff,_#ffffff_52%,_#f6fff8)] px-5 py-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                  Market
                </p>
                <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">
                  {getMarketLabel(market)}
                </h2>
              </div>
              {marginByMarket.has(market) ? (
                <span
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-semibold",
                    (marginByMarket.get(market) ?? 0) < 0
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-slate-100 text-slate-600"
                  )}
                >
                  Margin {formatMargin(marginByMarket.get(market) ?? 0)}
                </span>
              ) : null}
            </div>

            <div className={cn("grid gap-4 p-4 sm:p-5", gridClass)}>
              {selections.map((selection) => {
                const entries = marketOdds
                  .filter((entry) => entry.selection === selection)
                  .sort((left, right) => {
                    if (right.odds !== left.odds) {
                      return right.odds - left.odds;
                    }
                    return bookmakerRank(left.bookmaker) - bookmakerRank(right.bookmaker);
                  });
                const best = entries[0];

                return (
                  <div
                    key={`${market}-${selection}`}
                    className={cn(
                      "rounded-2xl border bg-slate-50/80 p-3 transition sm:p-4",
                      focusedMarket === market && focusedSelection === selection
                        ? "border-blue-300 ring-2 ring-blue-100"
                        : "border-slate-200"
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                          {resolveSelectionLabel(selection, homeTeam, awayTeam)}
                        </p>
                        <p className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
                          {best ? formatOdds(best.odds) : "-"}
                        </p>
                      </div>
                      {best ? (
                        <BookmakerPill bookmaker={best.bookmaker} />
                      ) : null}
                    </div>

                    <div className="mt-4 space-y-2">
                      {entries.map((entry) => {
                        const bookmaker = getBookmakerDisplay(entry.bookmaker);
                        const isFocused =
                          focusedBookmaker === entry.bookmaker &&
                          focusedMarket === market &&
                          focusedSelection === selection;
                        return (
                          <a
                            key={`${entry.bookmaker}-${entry.market}-${entry.selection}`}
                            href={entry.url ?? "#"}
                            target={entry.url ? "_blank" : undefined}
                            rel={entry.url ? "noopener noreferrer" : undefined}
                            className={cn(
                              "flex items-center justify-between gap-3 rounded-xl border bg-white px-3 py-2 text-sm transition",
                              entry.url ? "hover:border-slate-300 hover:shadow-sm" : "pointer-events-none",
                              isFocused ? "border-blue-300 ring-2 ring-blue-100" : "border-slate-100"
                            )}
                          >
                            <span className="flex min-w-0 items-center gap-2">
                              <span
                                className="h-2.5 w-2.5 shrink-0 rounded-full"
                                style={{ backgroundColor: bookmaker.color }}
                              />
                              <span className="truncate font-semibold" style={{ color: bookmaker.color }}>
                                {bookmaker.displayName}
                              </span>
                            </span>
                            <span className="flex shrink-0 items-center gap-2">
                              <span className="font-bold tabular-nums text-slate-950">
                                {formatOdds(entry.odds)}
                              </span>
                              {entry.url ? <ExternalLink className="h-3.5 w-3.5 text-slate-400" /> : null}
                            </span>
                            <span className="sr-only">
                              Checked {formatLastUpdated(entry.checked_at ?? entry.scraped_at)}
                            </span>
                          </a>
                        );
                      })}
                    </div>

                    {best ? (
                      <p className="mt-3 text-xs text-slate-400">
                        Checked {formatLastUpdated(best.checked_at ?? best.scraped_at)}
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </article>
        );
      })}
    </section>
  );
}

function BookmakerPill({ bookmaker }: { bookmaker: string }) {
  const bookmakerData = getBookmakerDisplay(bookmaker);
  return (
    <span
      className="rounded-full px-2.5 py-1 text-xs font-semibold"
      style={{
        backgroundColor: bookmakerData.bgColor,
        color: bookmakerData.color,
      }}
    >
      {bookmakerData.displayName}
    </span>
  );
}
