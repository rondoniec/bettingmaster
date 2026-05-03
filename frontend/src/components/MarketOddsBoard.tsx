"use client";

import { ExternalLink } from "lucide-react";

import { BookmakerName, Kicker } from "@/components/Primitives";
import { FreshnessBadge } from "@/components/FreshnessBadge";
import type { BestOdds, OddsEntry } from "@/lib/api";
import {
  BOOKMAKER_ORDER,
  getMarketLabel,
  resolveSelectionLabel,
  SELECTION_ORDER,
} from "@/lib/constants";
import { cn, formatLastUpdated, formatMargin, formatOdds, getBookmakerFreshness } from "@/lib/utils";

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

const SELECTION_CODE: Record<string, string> = {
  home: "1",
  draw: "X",
  away: "2",
  yes: "Áno",
  no: "Nie",
  over: "Nad",
  under: "Pod",
};

function bookmakerRank(bm: string) {
  const i = BOOKMAKER_ORDER.indexOf(bm);
  return i === -1 ? BOOKMAKER_ORDER.length : i;
}

function orderSelections(market: string, entries: OddsEntry[]) {
  const preferred = SELECTION_ORDER[market] ?? [];
  const present = Array.from(new Set(entries.map((e) => e.selection)));
  return [
    ...preferred.filter((s) => present.includes(s)),
    ...present.filter((s) => !preferred.includes(s)).sort(),
  ];
}

function impliedPercent(odds: number) {
  if (!odds || odds <= 0) return 0;
  return Math.round((1 / odds) * 1000) / 10;
}

function calcMarginFor(rowOdds: Record<string, number | undefined>) {
  const vals = Object.values(rowOdds).filter((v): v is number => Boolean(v) && (v as number) > 0);
  if (vals.length < 2) return null;
  return (vals.reduce((acc, v) => acc + 1 / v, 0) - 1) * 100;
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
  const marginByMarket = new Map(bestOdds.map((m) => [m.market, m.combined_margin]));

  const displayMarkets = markets
    .map((market) => {
      const marketOdds = odds.filter((e) => e.market === market);
      const selections = orderSelections(market, marketOdds).filter(
        (sel) => marketOdds.filter((e) => e.selection === sel).length >= 2,
      );
      return { market, marketOdds, selections };
    })
    .filter((m) => m.selections.length > 0);

  if (displayMarkets.length === 0) {
    return (
      <div className="border border-dashed border-slate-300 bg-white p-12 text-center">
        <h2 className="text-base font-semibold text-slate-900">Žiadne porovnateľné kurzy</h2>
        <p className="mx-auto mt-2 max-w-2xl text-[13px] leading-6 text-slate-500">
          Výsledky zobrazujeme len keď aspoň dve stávkovky majú kurz na rovnaký výsledok.
        </p>
      </div>
    );
  }

  return (
    <section className="space-y-4">
      {displayMarkets.map(({ market, marketOdds, selections }) => {
        // bookmaker -> selection -> entry
        const bmRows = new Map<string, Map<string, OddsEntry>>();
        for (const e of marketOdds) {
          if (!bmRows.has(e.bookmaker)) bmRows.set(e.bookmaker, new Map());
          bmRows.get(e.bookmaker)!.set(e.selection, e);
        }
        const bookmakers = Array.from(bmRows.keys()).sort(
          (a, b) => bookmakerRank(a) - bookmakerRank(b),
        );

        // Best odds per selection in this market
        const best: Record<string, number> = {};
        for (const sel of selections) {
          let max = 0;
          for (const bm of bookmakers) {
            const v = bmRows.get(bm)?.get(sel)?.odds ?? 0;
            if (v > max) max = v;
          }
          best[sel] = max;
        }

        // Per-bookmaker margin
        const rowMargins = new Map<string, number | null>();
        for (const bm of bookmakers) {
          const obj: Record<string, number | undefined> = {};
          for (const sel of selections) obj[sel] = bmRows.get(bm)?.get(sel)?.odds;
          rowMargins.set(bm, calcMarginFor(obj));
        }

        // Market average per selection
        const avgOdds: Record<string, number> = {};
        for (const sel of selections) {
          const vals = bookmakers
            .map((bm) => bmRows.get(bm)?.get(sel)?.odds)
            .filter((v): v is number => !!v && v > 0);
          avgOdds[sel] =
            vals.length > 0 ? vals.reduce((acc, v) => acc + v, 0) / vals.length : 0;
        }
        const avgMargin = calcMarginFor(avgOdds);

        // Latest checked
        const latestChecked = marketOdds
          .map((e) => e.checked_at ?? e.scraped_at)
          .filter(Boolean)
          .sort()
          .at(-1);

        const isFocusedMarket = focusedMarket === market;

        const gridTemplate =
          selections.length === 3
            ? "grid-cols-[140px_repeat(3,minmax(0,1fr))_80px]"
            : selections.length === 2
              ? "grid-cols-[140px_repeat(2,minmax(0,1fr))_80px]"
              : "grid-cols-[140px_repeat(1,minmax(0,1fr))_80px]";

        return (
          <article
            key={market}
            className={cn(
              "border bg-white p-5",
              isFocusedMarket ? "border-emerald-300" : "border-slate-200",
            )}
          >
            {/* Header */}
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="max-w-[540px]">
                <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-slate-900">
                  {getMarketLabel(market)}
                </h2>
                <p className="mt-1 text-[12px] leading-5 text-slate-500">
                  Vyšší kurz = vyššia výhra. Tag <b className="text-emerald-700">NAJ</b> označuje
                  stávkovku s najvyšším kurzom pre danú možnosť. Pruh ukazuje implikovanú
                  pravdepodobnosť.
                </p>
              </div>
              <div className="text-right font-mono text-[11px] text-slate-500">
                {bookmakers.length} stávkoviek
                {marginByMarket.has(market)
                  ? ` · spoločná marža ${formatMargin(marginByMarket.get(market) ?? 0)}`
                  : ""}
                {latestChecked ? (
                  <div className="text-slate-400">
                    aktualizované {formatLastUpdated(latestChecked)}
                  </div>
                ) : null}
              </div>
            </div>

            {/* Column headers */}
            <div
              className={cn(
                "mt-4 grid items-end gap-3 border-b border-slate-200 pb-2",
                gridTemplate,
              )}
            >
              <Kicker>Stávkovka</Kicker>
              {selections.map((sel) => (
                <div key={sel}>
                  <Kicker>{SELECTION_CODE[sel] ?? sel}</Kicker>
                  <div className="mt-0.5 truncate text-[12px] font-semibold text-slate-900">
                    {resolveSelectionLabel(sel, homeTeam, awayTeam)}
                  </div>
                </div>
              ))}
              <div className="text-right">
                <Kicker>Marža</Kicker>
              </div>
            </div>

            {/* Per-bookmaker rows */}
            {bookmakers.map((bm) => {
              const margin = rowMargins.get(bm);
              return (
                <div
                  key={bm}
                  className={cn(
                    "grid items-center gap-3 border-b border-slate-100 py-3.5 last:border-b-0",
                    gridTemplate,
                  )}
                >
                  <BookmakerName bookmaker={bm} />
                  {selections.map((sel) => {
                    const entry = bmRows.get(bm)?.get(sel);
                    const odds = entry?.odds ?? 0;
                    const isBest = !!odds && odds === best[sel];
                    const prob = impliedPercent(odds);
                    const isFocused =
                      focusedMarket === market &&
                      focusedSelection === sel &&
                      focusedBookmaker === bm;
                    const freshness = getBookmakerFreshness(
                      bm,
                      entry?.checked_at ?? entry?.scraped_at,
                    );
                    return (
                      <div
                        key={sel}
                        className={cn(
                          "relative",
                          isFocused ? "rounded-sm bg-slate-50 px-1.5 py-1" : null,
                        )}
                      >
                        <div className="flex items-baseline gap-2">
                          <span
                            className={cn(
                              "font-mono text-[18px] font-semibold tabular-nums leading-none tracking-[-0.01em]",
                              isBest ? "text-emerald-700" : "text-slate-900",
                            )}
                          >
                            {odds ? formatOdds(odds) : "—"}
                          </span>
                          {odds ? (
                            <span className="font-mono text-[10px] text-slate-400">
                              {prob}%
                            </span>
                          ) : null}
                        </div>
                        <div className="relative mt-1.5 h-[5px] bg-slate-100">
                          <div
                            className={cn(
                              "absolute inset-y-0 left-0",
                              isBest ? "bg-emerald-700" : "bg-slate-300",
                            )}
                            style={{ width: `${Math.min(100, prob)}%` }}
                          />
                        </div>
                        {isBest && entry ? (
                          <a
                            href={entry.url ?? "#"}
                            target={entry.url ? "_blank" : undefined}
                            rel={entry.url ? "noopener noreferrer" : undefined}
                            className="absolute -top-1 right-0 inline-flex items-center gap-0.5 bg-emerald-700 px-1 py-0.5 font-mono text-[8px] font-bold uppercase tracking-[0.08em] text-white hover:bg-emerald-800"
                          >
                            NAJ
                            {entry.url ? <ExternalLink className="h-2.5 w-2.5" /> : null}
                          </a>
                        ) : null}
                        {entry && !isBest ? (
                          <div className="mt-1">
                            <FreshnessBadge
                              freshness={freshness.freshness}
                              ageSeconds={freshness.ageSeconds}
                            />
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                  <div className="text-right font-mono text-[12px] tabular-nums text-slate-500">
                    {margin != null ? `${margin >= 0 ? "+" : ""}${margin.toFixed(2)}%` : "—"}
                  </div>
                </div>
              );
            })}

            {/* Market average */}
            <div className="mt-3 border border-slate-200 bg-slate-50 px-3 py-3.5">
              <div className={cn("grid items-center gap-3", gridTemplate)}>
                <span className="inline-flex items-center gap-2 text-[13px] font-medium text-slate-600">
                  <span className="inline-block h-2 w-2 rounded-[2px] bg-slate-400" />
                  Priemer trhu
                </span>
                {selections.map((sel) => {
                  const a = avgOdds[sel];
                  const p = impliedPercent(a);
                  return (
                    <div key={sel}>
                      <div className="flex items-baseline gap-2">
                        <span className="font-mono text-[16px] font-medium tabular-nums text-slate-600">
                          {a ? a.toFixed(2) : "—"}
                        </span>
                        <span className="font-mono text-[10px] text-slate-400">{p}%</span>
                      </div>
                      <div className="relative mt-1.5 h-[5px] bg-slate-200">
                        <div
                          className="absolute inset-y-0 left-0 bg-slate-400"
                          style={{ width: `${Math.min(100, p)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
                <div className="text-right font-mono text-[12px] tabular-nums text-slate-500">
                  {avgMargin !== null ? `${avgMargin >= 0 ? "+" : ""}${avgMargin.toFixed(2)}%` : "—"}
                </div>
              </div>
            </div>

            {/* Legend */}
            <div className="mt-3 flex flex-wrap items-center gap-4 border-t border-dashed border-slate-200 pt-3 text-[11px] text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-[5px] w-3.5 bg-emerald-700" />
                <b className="font-semibold text-slate-900">Najlepší</b> — najvyšší kurz v stĺpci
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-[5px] w-3.5 bg-slate-300" />
                Ostatné stávkovky
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-[5px] w-3.5 bg-slate-400" />
                Priemer trhu
              </span>
            </div>
          </article>
        );
      })}
    </section>
  );
}
