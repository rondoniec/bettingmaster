"use client";

import { useEffect, useState } from "react";

export type CountdownUrgency = "live" | "imminent" | "soon" | "later" | "done";

export interface CountdownResult {
  label: string;
  urgency: CountdownUrgency;
}

function pickInterval(diffMs: number): number {
  const absMs = Math.abs(diffMs);
  if (absMs < 2 * 60 * 1000) return 1000;
  if (absMs < 60 * 60 * 1000) return 15_000;
  return 60_000;
}

function buildResult(startTime: string, status: string, now: number): CountdownResult {
  const normalized = status?.toLowerCase() ?? "";

  if (normalized === "live" || normalized === "inprogress") {
    return { label: "LIVE", urgency: "live" };
  }
  if (normalized === "concluded" || normalized === "finished" || normalized === "ended") {
    return { label: "FT", urgency: "done" };
  }
  if (normalized === "cancelled" || normalized === "canceled") {
    return { label: "Cancelled", urgency: "done" };
  }

  const startMs = Date.parse(startTime);
  if (Number.isNaN(startMs)) {
    return { label: "", urgency: "later" };
  }

  const diffMs = startMs - now;
  if (diffMs <= 0 && diffMs > -10 * 60 * 1000) {
    return { label: "Starting now", urgency: "imminent" };
  }
  if (diffMs <= -10 * 60 * 1000) {
    return { label: "FT", urgency: "done" };
  }

  const totalSeconds = Math.floor(diffMs / 1000);

  let urgency: CountdownUrgency = "later";
  if (diffMs < 10 * 60 * 1000) urgency = "imminent";
  else if (diffMs < 2 * 60 * 60 * 1000) urgency = "soon";

  if (totalSeconds < 60) {
    return { label: `in ${totalSeconds}s`, urgency };
  }
  const minutes = Math.floor(totalSeconds / 60);
  if (minutes < 60) {
    return { label: `in ${minutes}m`, urgency };
  }
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  if (hours < 24) {
    const minSuffix = remMinutes > 0 ? ` ${remMinutes}m` : "";
    return { label: `in ${hours}h${minSuffix}`, urgency };
  }
  const days = Math.floor(hours / 24);
  const remHours = hours % 24;
  const hrSuffix = remHours > 0 ? ` ${remHours}h` : "";
  return { label: `in ${days}d${hrSuffix}`, urgency };
}

export function useCountdown(startTime: string, status: string): CountdownResult {
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    const startMs = Date.parse(startTime);
    if (Number.isNaN(startMs)) return;

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout>;

    const schedule = () => {
      if (cancelled) return;
      const tickNow = Date.now();
      setNow(tickNow);
      const interval = pickInterval(startMs - tickNow);
      timeoutId = setTimeout(schedule, interval);
    };

    schedule();
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [startTime]);

  return buildResult(startTime, status, now);
}
