"use client";

import { useBookmakerFilter } from "@/hooks/useBookmakerFilter";
import { BOOKMAKERS, BOOKMAKER_ORDER } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Kicker } from "@/components/Primitives";

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
        "flex flex-wrap items-center gap-3 border border-slate-200 bg-white px-4 py-3",
        className,
      )}
    >
      <Kicker>Stávkové kancelárie</Kicker>
      <div className="flex flex-wrap items-center gap-2">
        {list.map((bm) => {
          const meta = BOOKMAKERS[bm];
          if (!meta) return null;
          const enabled = isEnabled(bm);
          const dot = meta.bgColor.toLowerCase() === "#ffffff" ? meta.color : meta.bgColor;
          return (
            <button
              key={bm}
              type="button"
              onClick={() => toggle(bm)}
              aria-pressed={enabled}
              className={cn(
                "inline-flex items-center gap-1.5 border px-2 py-1 text-[11px] font-medium transition",
                enabled
                  ? "border-slate-300 bg-slate-50 text-slate-800 hover:border-slate-400"
                  : "border-slate-200 bg-white text-slate-400 line-through hover:border-slate-300",
              )}
            >
              <span
                className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: enabled ? dot : "#cbd5e1" }}
              />
              {meta.displayName}
            </button>
          );
        })}
      </div>
      {!allOn ? (
        <button
          type="button"
          onClick={enableAll}
          className="ml-auto bg-slate-900 px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-white transition hover:bg-slate-700"
        >
          Zapnúť všetky
        </button>
      ) : null}
    </div>
  );
}
