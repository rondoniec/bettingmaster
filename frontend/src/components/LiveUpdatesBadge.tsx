"use client";

import { Activity } from "lucide-react";
import { startTransition, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { cn, formatLastUpdated } from "@/lib/utils";

type Props = {
  matchId?: string;
  leagueId?: string;
  sport?: string;
  date?: string;
  className?: string;
  onUpdate?: () => void;
};

type LiveStatus = "connecting" | "connected" | "reconnecting";

function buildWebSocketUrl({
  matchId,
  leagueId,
  sport,
  date,
}: Omit<Props, "className">) {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  const url = baseUrl
    ? new URL(baseUrl)
    : new URL(window.location.origin);

  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/odds-feed";
  url.search = "";

  if (matchId) {
    url.searchParams.set("match_id", matchId);
  }
  if (leagueId) {
    url.searchParams.set("league_id", leagueId);
  }
  if (sport) {
    url.searchParams.set("sport", sport);
  }
  if (date) {
    url.searchParams.set("date", date);
  }

  return url.toString();
}

export function LiveUpdatesBadge({
  matchId,
  leagueId,
  sport,
  date,
  className,
  onUpdate,
}: Props) {
  const router = useRouter();
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const [lastEventAt, setLastEventAt] = useState<string | null>(null);
  const initializedRef = useRef(false);
  const onUpdateRef = useRef<Props["onUpdate"]>(onUpdate);
  const reconnectTimerRef = useRef<number | null>(null);
  const attemptsRef = useRef(0);

  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;

    const connect = () => {
      if (cancelled) {
        return;
      }

      setStatus(attemptsRef.current === 0 ? "connecting" : "reconnecting");
      socket = new WebSocket(buildWebSocketUrl({ matchId, leagueId, sport, date }));

      socket.onopen = () => {
        if (cancelled) {
          socket?.close();
          return;
        }
        setStatus("connected");
        attemptsRef.current = 0;
      };

      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data) as { type?: string };
        setLastEventAt(new Date().toISOString());
        if (payload.type === "snapshot") {
          initializedRef.current = true;
          return;
        }
        if (payload.type === "odds_update" && initializedRef.current) {
          startTransition(() => {
            if (onUpdateRef.current) {
              onUpdateRef.current();
              return;
            }
            router.refresh();
          });
        }
      };

      socket.onerror = () => {
        socket?.close();
      };

      socket.onclose = () => {
        if (cancelled) {
          return;
        }
        attemptsRef.current += 1;
        setStatus("reconnecting");
        reconnectTimerRef.current = window.setTimeout(
          connect,
          Math.min(5000, attemptsRef.current * 1000)
        );
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      socket?.close();
    };
  }, [date, leagueId, matchId, router, sport]);

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm shadow-sm",
        status === "connected"
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-amber-200 bg-amber-50 text-amber-700",
        className
      )}
    >
      <Activity className="h-4 w-4" />
      <span>
        {status === "connected"
          ? "Live updates on"
          : status === "reconnecting"
          ? "Reconnecting live feed"
          : "Connecting live feed"}
      </span>
      {lastEventAt ? <span className="hidden text-xs sm:inline">Seen {formatLastUpdated(lastEventAt)}</span> : null}
    </div>
  );
}
