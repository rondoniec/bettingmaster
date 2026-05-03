import { type ClassValue, clsx } from "clsx";
import { format, formatDistanceToNow, isToday, isTomorrow, parseISO } from "date-fns";
import { sk } from "date-fns/locale";
import { twMerge } from "tailwind-merge";

import { BOOKMAKER_REFRESH_INTERVALS } from "@/lib/constants";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatOdds(odds: number): string {
  return odds.toFixed(2);
}

export function formatMargin(margin: number): string {
  return `${margin.toFixed(2)}%`;
}

export function formatProfitPercent(profit: number): string {
  return `+${profit.toFixed(2)}%`;
}

export function formatMatchTime(isoString: string): string {
  try {
    const date = parseISO(isoString);
    if (isToday(date)) {
      return `Today ${format(date, "HH:mm")}`;
    }
    if (isTomorrow(date)) {
      return `Tomorrow ${format(date, "HH:mm")}`;
    }
    return format(date, "dd.MM. HH:mm");
  } catch {
    return isoString;
  }
}

export function formatFullDate(isoString: string): string {
  try {
    return format(parseISO(isoString), "EEEE, d MMMM yyyy 'at' HH:mm");
  } catch {
    return isoString;
  }
}

export function formatLastUpdated(isoString: string): string {
  try {
    return formatDistanceToNow(parseISO(isoString), { addSuffix: true, locale: sk });
  } catch {
    return isoString;
  }
}

export function formatSecondsCompact(totalSeconds: number): string {
  if (!Number.isFinite(totalSeconds) || totalSeconds < 0) {
    return "-";
  }

  if (totalSeconds < 60) {
    return `${Math.round(totalSeconds)}s`;
  }

  const minutes = Math.round(totalSeconds / 60);
  if (minutes < 60) {
    return `${minutes}m`;
  }

  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours}h`;
  }

  const days = Math.round(hours / 24);
  return `${days}d`;
}

export type FreshnessState = "fresh" | "aging" | "stale" | "idle";

export function getFreshnessState(
  ageSeconds: number | null | undefined,
  intervalSeconds: number
): FreshnessState {
  if (ageSeconds === null || ageSeconds === undefined) {
    return "idle";
  }

  const freshThreshold = Math.max(intervalSeconds * 2, 120);
  const agingThreshold = Math.max(intervalSeconds * 6, 600);
  if (ageSeconds <= freshThreshold) {
    return "fresh";
  }
  if (ageSeconds <= agingThreshold) {
    return "aging";
  }
  return "stale";
}

export function getBookmakerFreshness(bookmaker: string, isoString?: string | null) {
  const intervalSeconds = BOOKMAKER_REFRESH_INTERVALS[bookmaker] ?? 120;
  if (!isoString) {
    return {
      freshness: "idle" as FreshnessState,
      ageSeconds: null,
      intervalSeconds,
    };
  }

  try {
    const checkedAt = parseISO(isoString).getTime();
    if (Number.isNaN(checkedAt)) {
      return {
        freshness: "idle" as FreshnessState,
        ageSeconds: null,
        intervalSeconds,
      };
    }

    const ageSeconds = Math.max(0, Math.round((Date.now() - checkedAt) / 1000));
    return {
      freshness: getFreshnessState(ageSeconds, intervalSeconds),
      ageSeconds,
      intervalSeconds,
    };
  } catch {
    return {
      freshness: "idle" as FreshnessState,
      ageSeconds: null,
      intervalSeconds,
    };
  }
}

export function getStatusVariant(
  status: string
): "default" | "secondary" | "destructive" | "outline" {
  switch (status?.toLowerCase()) {
    case "prematch":
    case "upcoming":
      return "outline";
    case "live":
    case "inprogress":
      return "destructive";
    case "finished":
    case "ended":
      return "secondary";
    default:
      return "default";
  }
}

export function getStatusLabel(status: string): string {
  switch (status?.toLowerCase()) {
    case "prematch":
      return "Pred zápasom";
    case "live":
      return "Naživo";
    case "finished":
    case "concluded":
    case "ended":
      return "Skončené";
    case "upcoming":
      return "Nadchádzajúce";
    case "cancelled":
    case "canceled":
      return "Zrušené";
    default:
      return status ?? "Neznámy";
  }
}
