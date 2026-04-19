"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Loader2, TrendingUp } from "lucide-react";
import { format, parseISO } from "date-fns";

import { getOddsHistory, type OddsHistorySeries } from "@/lib/api";
import { getBookmakerDisplay, resolveSelectionLabel } from "@/lib/constants";

type Props = {
  matchId: string;
  market: string;
  homeTeam?: string;
  awayTeam?: string;
};

type ChartRow = {
  timestamp: string;
  label: string;
  [key: string]: number | string | null;
};

type ChartLine = {
  key: string;
  label: string;
  color: string;
  dashArray?: string;
};

const DASH_BY_SELECTION: Record<string, string | undefined> = {
  home: undefined,
  draw: "6 4",
  away: "2 4",
  over: undefined,
  under: "6 4",
  yes: undefined,
  no: "6 4",
};

function buildChartModel(series: OddsHistorySeries[], homeTeam?: string, awayTeam?: string) {
  const rowsByTimestamp = new Map<string, ChartRow>();
  const lines: ChartLine[] = [];

  for (const selectionSeries of series) {
    for (const point of selectionSeries.history) {
      const key = `${point.bookmaker}__${selectionSeries.selection}`;
      if (!lines.find((line) => line.key === key)) {
        const bookmaker = getBookmakerDisplay(point.bookmaker);
        lines.push({
          key,
          label: `${bookmaker.displayName} ${resolveSelectionLabel(selectionSeries.selection, homeTeam, awayTeam)}`,
          color: bookmaker.color,
          dashArray: DASH_BY_SELECTION[selectionSeries.selection],
        });
      }

      const existing = rowsByTimestamp.get(point.scraped_at) ?? {
        timestamp: point.scraped_at,
        label: format(parseISO(point.scraped_at), "HH:mm"),
      };
      existing[key] = point.odds;
      rowsByTimestamp.set(point.scraped_at, existing);
    }
  }

  const rows = Array.from(rowsByTimestamp.values()).sort((left, right) =>
    String(left.timestamp).localeCompare(String(right.timestamp))
  );

  return { rows, lines };
}

export function OddsHistoryChart({ matchId, market, homeTeam, awayTeam }: Props) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["odds-history", matchId, market],
    queryFn: () => getOddsHistory(matchId, market),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="flex min-h-56 items-center justify-center rounded-3xl border border-slate-200 bg-white">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading odds history...
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-3xl border border-dashed border-amber-300 bg-amber-50 px-5 py-10 text-center">
        <p className="text-sm font-semibold text-amber-800">History unavailable</p>
        <p className="mt-2 text-sm text-amber-700">
          {error instanceof Error ? error.message : "Could not load odds history."}
        </p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
        <p className="text-sm font-semibold text-slate-700">No odds history yet</p>
        <p className="mt-2 text-sm text-slate-500">
          This market will chart movement as soon as more snapshots are scraped.
        </p>
      </div>
    );
  }

  const { rows, lines } = buildChartModel(data, homeTeam, awayTeam);

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-[0_18px_45px_-32px_rgba(15,23,42,0.45)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">Odds movement</p>
          <p className="mt-1 text-sm text-slate-500">
            Each line tracks one bookmaker and outcome inside this market.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
          <TrendingUp className="h-3.5 w-3.5" />
          {rows.length} snapshot{rows.length === 1 ? "" : "s"}
        </div>
      </div>

      <div className="mt-5 h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "#64748b", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fill: "#64748b", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              domain={["dataMin - 0.05", "dataMax + 0.05"]}
              width={44}
            />
            <Tooltip
              contentStyle={{
                borderRadius: "16px",
                borderColor: "#cbd5e1",
                boxShadow: "0 18px 45px -32px rgba(15, 23, 42, 0.45)",
              }}
            />
            <Legend />
            {lines.map((line) => (
              <Line
                key={line.key}
                type="monotone"
                dataKey={line.key}
                name={line.label}
                stroke={line.color}
                strokeWidth={2}
                dot={{ r: 2 }}
                activeDot={{ r: 4 }}
                connectNulls
                strokeDasharray={line.dashArray}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
