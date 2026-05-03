"use client";

import { useCallback, useSyncExternalStore } from "react";

import { BOOKMAKER_ORDER } from "@/lib/constants";

const STORAGE_KEY = "bm.disabledBookmakers";
const CHANGE_EVENT = "bm.disabledBookmakers.change";

function readStored(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.map(String);
    }
  } catch {
    /* ignore */
  }
  return [];
}

function writeStored(disabled: string[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(disabled));
    window.dispatchEvent(new Event(CHANGE_EVENT));
  } catch {
    /* ignore */
  }
}

let cachedSnapshot: string[] | null = null;

function snapshot(): string[] {
  const next = readStored();
  if (
    cachedSnapshot &&
    cachedSnapshot.length === next.length &&
    cachedSnapshot.every((v, i) => v === next[i])
  ) {
    return cachedSnapshot;
  }
  cachedSnapshot = next;
  return next;
}

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = () => onChange();
  window.addEventListener(CHANGE_EVENT, handler);
  window.addEventListener("storage", handler);
  return () => {
    window.removeEventListener(CHANGE_EVENT, handler);
    window.removeEventListener("storage", handler);
  };
}

const EMPTY: string[] = [];

export function useBookmakerFilter() {
  const disabledList = useSyncExternalStore(subscribe, snapshot, () => EMPTY);
  const disabled = new Set(disabledList);
  const hydrated = typeof window !== "undefined";

  const toggle = useCallback((bookmaker: string) => {
    const current = readStored();
    const next = current.includes(bookmaker)
      ? current.filter((b) => b !== bookmaker)
      : [...current, bookmaker];
    writeStored(next);
  }, []);

  const enableAll = useCallback(() => {
    writeStored([]);
  }, []);

  const isEnabled = (bookmaker: string) => !disabled.has(bookmaker);
  const enabledList = BOOKMAKER_ORDER.filter((b) => !disabled.has(b));

  return {
    hydrated,
    disabled,
    isEnabled,
    toggle,
    enableAll,
    enabledList,
  };
}
