import { type ClassValue, clsx } from "clsx";
import { format, formatDistanceToNow, isToday, isTomorrow, parseISO } from "date-fns";
import { twMerge } from "tailwind-merge";

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
    return `${formatDistanceToNow(parseISO(isoString), { addSuffix: true })}`;
  } catch {
    return isoString;
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
      return "Pre-match";
    case "live":
      return "Live";
    case "finished":
      return "Finished";
    case "upcoming":
      return "Upcoming";
    default:
      return status ?? "Unknown";
  }
}
