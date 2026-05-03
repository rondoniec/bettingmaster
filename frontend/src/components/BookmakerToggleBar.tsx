"use client";

import { Check } from "lucide-react";

import { useBookmakerFilter } from "@/hooks/useBookmakerFilter";
import { BOOKMAKER_ORDER, getBookmakerDisplay } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface Props {
  className?: string;
  bookmakers?: string[];
}

export function BookmakerToggleBar({ className, bookmakers }: Props) {
  const { hydrated, isEnabled, toggle, enableAll, disabled } = useBookmakerFilter();
  const list = bookmakers && bookmakers.length > 0 ? bookmakers : BOOKMAKER_ORDER;
  const allOn = disabled.size === 0;

  if (!hydrated) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm",
        className,
      )}
    >
      <span className="mr-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
        Stávkové kancelárie
      </span>
      {list.map((bm) => {
        const display = getBookmakerDisplay(bm);
        const enabled = isEnabled(bm);
        return (
          <button
            key={bm}
            type="button"
            onClick={() => toggle(bm)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition",
              enabled
                ? "ring-1 ring-inset"
                : "bg-slate-100 text-slate-400 line-through ring-1 ring-inset ring-slate-200",
            )}
            style={
              enabled
                ? {
                    backgroundColor: display.bgColor,
                    color: display.color,
                    boxShadow: `inset 0 0 0 1px ${display.color}33`,
                  }
                : undefined
            }
            aria-pressed={enabled}
          >
            {enabled ? <Check className="h-3 w-3" /> : null}
            <span>{display.displayName}</span>
          </button>
        );
      })}
      {!allOn ? (
        <button
          type="button"
          onClick={enableAll}
          className="ml-auto rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white hover:bg-slate-700"
        >
          Zapnúť všetky
        </button>
      ) : null}
    </div>
  );
}
