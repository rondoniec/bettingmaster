"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Loader2, TrendingUp } from "lucide-react";
import Link from "next/link";

import { getSurebets } from "@/lib/api";
import { formatProfitPercent } from "@/lib/utils";

export function SurebetBanner() {
  const { data: surebets, isLoading } = useQuery({
    queryKey: ["surebets"],
    queryFn: getSurebets,
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
        <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
        <span className="ml-2 text-sm text-emerald-700">Loading surebets...</span>
      </div>
    );
  }

  if (!surebets || surebets.length === 0) {
    return null;
  }

  const bestProfit = Math.max(...surebets.map((surebet) => surebet.profit_percent));

  return (
    <Link href="/surebets" className="block">
      <div className="group flex items-center justify-between rounded-xl border border-emerald-300 bg-gradient-to-r from-emerald-50 to-green-50 px-4 py-3 shadow-sm transition hover:border-emerald-400 hover:shadow-md">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white shadow">
            <TrendingUp className="h-5 w-5" />
          </div>
          <div>
            <p className="font-semibold text-emerald-800">
              {surebets.length} live {surebets.length === 1 ? "surebet" : "surebets"}
            </p>
            <p className="text-sm text-emerald-600">
              Best profit: <span className="font-bold">{formatProfitPercent(bestProfit)}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white shadow transition group-hover:bg-emerald-700">
          View
          <ArrowRight className="h-4 w-4" />
        </div>
      </div>
    </Link>
  );
}
