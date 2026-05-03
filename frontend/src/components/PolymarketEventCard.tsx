"use client";

import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { BookmakerChip, Kicker } from "@/components/Primitives";
import type { NewPolymarketMarket } from "@/lib/api";
import { resolveSelectionLabel } from "@/lib/constants";
import { cn, formatFullDate, formatLastUpdated, formatOdds } from "@/lib/utils";

export function PolymarketEventCard({ market }: { market: NewPolymarketMarket }) {
  const subMarkets = market.markets ?? [];
  const hasMultiple = subMarkets.length > 1;
  const [open, setOpen] = useState(false);

  return (
    <article className="border border-slate-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            {market.league_hint ? <Kicker>{market.league_hint}</Kicker> : null}
            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
              {subMarkets.length || 1} {(subMarkets.length || 1) === 1 ? "trh" : "trhov"}
            </span>
          </div>
          <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-900">
            {market.title}
          </h2>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] tabular-nums text-slate-500">
            {market.start_time ? <span>začína {formatFullDate(market.start_time)}</span> : null}
            {market.created_at ? <span>otvorené {formatLastUpdated(market.created_at)}</span> : null}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {hasMultiple ? (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="inline-flex items-center gap-1 border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-700 hover:border-slate-400"
              aria-expanded={open}
            >
              {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Trhy ({subMarkets.length})
            </button>
          ) : null}
          <a
            href={market.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 bg-slate-900 px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-white hover:bg-slate-700"
          >
            Otvoriť
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      {market.crossref ? (
        <CrossRefSection
          matchId={market.crossref.match_id}
          home={market.crossref.match_home}
          away={market.crossref.match_away}
          selections={market.crossref.selections}
          better={market.crossref.polymarket_better_count}
        />
      ) : null}

      {hasMultiple && open ? (
        <ul className="border-t border-slate-100 divide-y divide-slate-100">
          {subMarkets.map((sub) => (
            <li key={sub.slug} className="flex items-center justify-between gap-3 px-5 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium text-slate-900">{sub.name}</p>
                {sub.market_count > 1 ? (
                  <p className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
                    {sub.market_count} výsledkov
                  </p>
                ) : null}
              </div>
              <a
                href={sub.url}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  "inline-flex items-center gap-1 border border-slate-200 bg-white px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-700",
                  "hover:border-slate-400 hover:text-slate-900",
                )}
              >
                Otvoriť
                <ExternalLink className="h-3 w-3" />
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function CrossRefSection({
  matchId,
  home,
  away,
  selections,
  better,
}: {
  matchId: string;
  home: string;
  away: string;
  selections: NonNullable<NewPolymarketMarket["crossref"]>["selections"];
  better: number;
}) {
  return (
    <div className="border-t border-slate-100 bg-slate-50 px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Kicker tone={better > 0 ? "emerald" : "slate"}>
          {better > 0
            ? `Polymarket platí viac na ${better} výsledku${better > 1 ? "" : ""}`
            : "Porovnanie s kanceláriami"}
        </Kicker>
        <Link
          href={`/match/${matchId}`}
          className="font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-700 hover:text-slate-900"
        >
          Otvoriť zápas →
        </Link>
      </div>
      <div className="mt-2 grid gap-px bg-slate-200 p-px sm:grid-cols-3">
        {selections.map((sel) => {
          const isPolymarketBetter = (sel.edge_percent ?? 0) > 0;
          return (
            <div key={sel.selection} className="bg-white p-3">
              <Kicker>{resolveSelectionLabel(sel.selection, home, away)}</Kicker>
              <div className="mt-2 grid grid-cols-2 gap-2 text-[12px]">
                <div>
                  <div className="font-mono text-[9px] uppercase tracking-wider text-slate-400">
                    Polymarket
                  </div>
                  <div
                    className={cn(
                      "font-mono font-semibold tabular-nums",
                      isPolymarketBetter ? "text-emerald-700" : "text-slate-900",
                    )}
                  >
                    {sel.polymarket_odds != null ? formatOdds(sel.polymarket_odds) : "—"}
                  </div>
                </div>
                <div>
                  <div className="font-mono text-[9px] uppercase tracking-wider text-slate-400">
                    Najlepší kurz
                  </div>
                  <div className="font-mono font-semibold tabular-nums text-slate-900">
                    {sel.sportsbook_odds != null ? formatOdds(sel.sportsbook_odds) : "—"}
                  </div>
                  {sel.sportsbook_name ? (
                    <BookmakerChip bookmaker={sel.sportsbook_name} className="mt-1" />
                  ) : null}
                </div>
              </div>
              {sel.edge_percent != null ? (
                <div
                  className={cn(
                    "mt-2 inline-flex items-center border px-1.5 py-0.5 font-mono text-[10px] font-semibold tabular-nums",
                    isPolymarketBetter
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-slate-200 bg-white text-slate-500",
                  )}
                >
                  {sel.edge_percent > 0 ? "+" : ""}
                  {sel.edge_percent.toFixed(2)}%
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
