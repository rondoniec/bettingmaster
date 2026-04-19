"use client";

import Link from "next/link";
import type { OddsEntry } from "@/lib/api";
import { BOOKMAKER_ORDER, getBookmakerDisplay, resolveSelectionLabel } from "@/lib/constants";
import { cn } from "@/lib/utils";

type Props = {
  odds: OddsEntry[];
  homeTeam: string;
  awayTeam: string;
};

type OutcomeRow = {
  bookmaker: string;
  home: number | null;
  draw: number | null;
  away: number | null;
  url?: string;
};

/** Convert decimal odds to implied probability percentage */
function toProb(decimal: number): number {
  return Math.round((1 / decimal) * 1000) / 10; // round to 1 dp
}

/** Normalise three raw probabilities to sum to 100 (removing bookmaker margin) */
function normalise(home: number, draw: number | null, away: number): [number, number | null, number] {
  const total = home + (draw ?? 0) + away;
  if (total === 0) return [33.3, draw !== null ? 33.4 : null, 33.3];
  return [
    Math.round((home / total) * 1000) / 10,
    draw !== null ? Math.round((draw / total) * 1000) / 10 : null,
    Math.round((away / total) * 1000) / 10,
  ];
}

export function OutcomesPanel({ odds, homeTeam, awayTeam }: Props) {
  // pull 1x2 odds for each bookmaker
  const rowsByBookmaker: Record<string, Partial<Record<string, OddsEntry>>> = {};
  for (const entry of odds) {
    if (entry.market !== "1x2") continue;
    if (!rowsByBookmaker[entry.bookmaker]) rowsByBookmaker[entry.bookmaker] = {};
    rowsByBookmaker[entry.bookmaker][entry.selection] = entry;
  }

  const activeBookmakers = BOOKMAKER_ORDER.filter((bm) => rowsByBookmaker[bm]);

  if (activeBookmakers.length === 0) return null;

  const rows: OutcomeRow[] = activeBookmakers.map((bm) => {
    const entries = rowsByBookmaker[bm] ?? {};
    return {
      bookmaker: bm,
      home: entries["home"]?.odds ?? null,
      draw: entries["draw"]?.odds ?? null,
      away: entries["away"]?.odds ?? null,
      url: entries["home"]?.url ?? entries["away"]?.url,
    };
  });

  // Consensus: average implied probabilities across all bookmakers
  const hasConsensus = rows.length > 1;
  const avg = (vals: (number | null)[]) => {
    const nums = vals.filter((v): v is number => v !== null);
    return nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null;
  };
  const consensusHomeRaw = avg(rows.map((r) => (r.home ? toProb(r.home) : null)));
  const consensusDrawRaw = avg(rows.map((r) => (r.draw ? toProb(r.draw) : null)));
  const consensusAwayRaw = avg(rows.map((r) => (r.away ? toProb(r.away) : null)));

  const selections = [
    { key: "home", label: resolveSelectionLabel("home", homeTeam, awayTeam) },
    ...(rows.some((r) => r.draw !== null) ? [{ key: "draw", label: "Draw" }] : []),
    { key: "away", label: resolveSelectionLabel("away", homeTeam, awayTeam) },
  ] as { key: "home" | "draw" | "away"; label: string }[];

  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold text-slate-950">Outcomes</h2>

      {/* Column headers */}
      <div
        className={cn(
          "grid items-center text-xs font-semibold uppercase tracking-wide text-slate-400",
          selections.length === 3 ? "grid-cols-[160px_1fr_1fr_1fr]" : "grid-cols-[160px_1fr_1fr]"
        )}
      >
        <span />
        {selections.map((s) => (
          <span key={s.key} className="text-center truncate px-1">
            {s.label}
          </span>
        ))}
      </div>

      {/* Bookmaker rows */}
      <div className="space-y-2">
        {rows.map((row) => {
          const bm = getBookmakerDisplay(row.bookmaker);
          const values = selections.map((s) => row[s.key] ?? null);
          const probs = values.map((v) => (v ? toProb(v) : null));
          // normalise within this row
          const homeP = probs[0] ?? 0;
          const drawP = selections.length === 3 ? (probs[1] ?? 0) : null;
          const awayP = selections.length === 3 ? (probs[2] ?? 0) : (probs[1] ?? 0);
          const [nHome, nDraw, nAway] = normalise(homeP, drawP, awayP);
          const normProbs = selections.length === 3 ? [nHome, nDraw, nAway] : [nHome, nAway];

          return (
            <div
              key={row.bookmaker}
              className={cn(
                "grid items-center gap-2 rounded-2xl border border-slate-100 bg-white px-4 py-3 transition hover:border-slate-200 hover:shadow-sm",
                selections.length === 3 ? "grid-cols-[160px_1fr_1fr_1fr]" : "grid-cols-[160px_1fr_1fr]"
              )}
            >
              {/* Bookmaker name */}
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: bm.color }}
                />
                {row.url ? (
                  <Link
                    href={row.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-semibold truncate hover:underline"
                    style={{ color: bm.color }}
                  >
                    {bm.displayName}
                  </Link>
                ) : (
                  <span className="text-sm font-semibold truncate" style={{ color: bm.color }}>
                    {bm.displayName}
                  </span>
                )}
              </div>

              {/* Outcome bars */}
              {selections.map((s, idx) => {
                const odds = row[s.key];
                const prob = normProbs[idx] ?? 0;
                const isHome = s.key === "home";
                const barColor = isHome
                  ? bm.color
                  : s.key === "draw"
                  ? "#94a3b8"
                  : "#f1a623";

                return (
                  <div key={s.key} className="flex flex-col items-center gap-1">
                    {/* Bar track */}
                    <div className="relative h-7 w-full rounded-lg bg-slate-100 overflow-hidden">
                      <div
                        className="absolute inset-y-0 left-0 rounded-lg transition-all duration-500"
                        style={{
                          width: `${prob}%`,
                          backgroundColor: barColor,
                          opacity: 0.2,
                        }}
                      />
                      <div
                        className="absolute inset-0 flex items-center justify-center text-xs font-bold"
                        style={{ color: prob > 0 ? "#1e293b" : "#94a3b8" }}
                      >
                        {odds ? `${prob}%` : "—"}
                      </div>
                    </div>
                    {/* Decimal odds */}
                    {odds ? (
                      <span className="text-[11px] tabular-nums text-slate-500">
                        {odds.toFixed(2)}
                      </span>
                    ) : null}
                  </div>
                );
              })}
            </div>
          );
        })}

        {/* Consensus row */}
        {hasConsensus && consensusHomeRaw !== null && consensusAwayRaw !== null ? (() => {
          const [nHome, nDraw, nAway] = normalise(
            consensusHomeRaw,
            consensusDrawRaw,
            consensusAwayRaw
          );
          const normConsensus = selections.length === 3 ? [nHome, nDraw, nAway] : [nHome, nAway];
          return (
            <div
              className={cn(
                "grid items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3",
                selections.length === 3 ? "grid-cols-[160px_1fr_1fr_1fr]" : "grid-cols-[160px_1fr_1fr]"
              )}
            >
              <div className="flex items-center gap-2">
                <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-500" />
                <span className="text-sm font-bold text-emerald-700">Consensus</span>
              </div>
              {selections.map((s, idx) => {
                const prob = normConsensus[idx] ?? 0;
                return (
                  <div key={s.key} className="flex flex-col items-center gap-1">
                    <div className="relative h-7 w-full rounded-lg bg-emerald-100 overflow-hidden">
                      <div
                        className="absolute inset-y-0 left-0 rounded-lg bg-emerald-400 transition-all duration-500"
                        style={{ width: `${prob}%`, opacity: 0.4 }}
                      />
                      <div className="absolute inset-0 flex items-center justify-center text-xs font-bold text-emerald-900">
                        {prob}%
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })() : null}
      </div>
    </section>
  );
}
