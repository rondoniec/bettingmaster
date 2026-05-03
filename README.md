# Handoff: BettingMaster Visual Refresh

## Overview

A visual + interaction refresh of the BettingMaster odds-comparison app (`bettingmaster/frontend`, Next.js 14 + Tailwind + shadcn). The current production UI uses a soft, "marketing-page" aesthetic — large border-radii, radial gradients, capsule pill filters, brand-color-saturated bookmaker chips, multiple competing accent colors. This refresh replaces it with a flat, monochrome, **data-terminal aesthetic** suited to a price-comparison product where the data — not the chrome — should carry the visual weight.

The scope covers:

1. The **homepage** (`/`) — header, hero/filter board, surebet banner, and the list of best-odds match cards.
2. The **match detail page** (`/match/[id]`) — the same match card, an outcomes-by-bookmaker panel (rewrite of `OutcomesPanel.tsx`), and an all-bookmakers odds table.
3. **Foundation tokens** — fonts, colors, radius, spacing — applied site-wide, so the rest of the app inherits the new look automatically.

## About the Design Files

The files in `mocks/` and `reference/` are **design references created in HTML** — React + inline styles, loaded via Babel-standalone in a single `index.html`. They are **prototypes showing intended look, behavior, and information architecture, not production code to copy directly.**

Your task is to **recreate these designs in the existing `bettingmaster/frontend` codebase** using its established patterns:

- Convert inline `style={...}` blocks to Tailwind classes (or shadcn variants where one already exists).
- Use the existing components (`@/components/ui/*`) where the mock has an obvious analogue (button, input, table).
- Keep the existing data layer (`lib/api.ts`, React Query hooks) untouched — only the presentational components change.
- Use `next/font/google` for fonts — the mock loads them via `<link>` for prototyping convenience only.

## Fidelity

**High-fidelity.** Hex values, type sizes, spacing, and border weights in the mocks are deliberate and should be matched closely. Do not "interpret" — if the mock says `#047857`, use `#047857` (or the Tailwind class that resolves to it: `text-emerald-700`).

The mocks were iterated on with the designer multiple times specifically to remove vibe-coded patterns (saturated colors, gradients, capsule pills, decorative icons). Reintroducing those in the port would undo the work.

---

## Foundation Tokens (do these first)

These changes are site-wide. Land them as a single PR before component work, so the existing pages immediately reflect the new system without breaking.

### Fonts

Replace the system stack in `src/app/layout.tsx` with `next/font/google`:

```ts
import { Geist, JetBrains_Mono } from "next/font/google";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans", weight: ["400","500","600","700"] });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", weight: ["400","500","600"] });

// In <html className={`${geist.variable} ${jetbrains.variable}`}>
```

In `tailwind.config.ts` add:

```ts
fontFamily: {
  sans: ["var(--font-sans)", "system-ui", "sans-serif"],
  mono: ["var(--font-mono)", "ui-monospace", "monospace"],
},
```

**Usage rule:** numbers (odds, percentages, timestamps, counts) and uppercase metadata kickers use `font-mono` with `tabular-nums`. Everything else uses `font-sans`.

### Colors (`src/app/globals.css`)

Replace the existing `:root` block. The semantic tokens are the same shadcn structure but the values flatten to slate + a single emerald accent.

```css
:root {
  --background:        0 0% 100%;
  --foreground:        222 47% 11%;   /* slate-900 #0f172a  */
  --muted:             210 40% 98%;   /* slate-50  #f8fafc  */
  --muted-foreground:  215 16% 47%;   /* slate-500 #64748b  */
  --border:            214 32% 91%;   /* slate-200 #e2e8f0  */
  --input:             214 32% 91%;
  --ring:              222 47% 11%;
  --primary:           222 47% 11%;   /* slate-900 — primary action */
  --primary-foreground:0 0% 100%;
  --accent-best:       158 64% 24%;   /* emerald-700 #047857 — "best price" only */
  --accent-best-bg:    152 76% 95%;   /* emerald-50  #ecfdf5 */
  --accent-best-border:152 76% 80%;   /* emerald-200 #a7f3d0 */
  --danger:            0 73% 50%;     /* red-600  #dc2626 — LIVE indicator */
  --radius: 4px;
}
```

Remove any existing emerald/amber/rose/blue tokens that were used for "marketing" purposes.

### Radius

The current production CSS uses `--radius: 1.75rem` (28px) which produces the bubbly feel everywhere. Drop to **4px** for cards, tables, and most surfaces. Reserve `rounded-full` for the `LIVE` dot and avatar-like elements only.

### Spacing & Layout

- Max content width: `1280px` (`max-w-screen-xl`), unchanged from current.
- Page gutter: `24px` desktop, `16px` mobile.
- Vertical rhythm between major sections: `24px`.
- Card inner padding: `16px`.

---

## Screens

### 1. Homepage (`src/app/page.tsx`)

Layout (top to bottom):

```
┌─────────────────────────────────────────────────────┐
│  Header                                             │
├─────────────────────────────────────────────────────┤
│  HeroBoard         (title + filter tabs + stats)    │
│  SurebetBanner     (only if surebets > 0)           │
│  Best odds board   (h2 + match cards list)          │
│  Footer                                             │
└─────────────────────────────────────────────────────┘
```

#### Header (`src/components/Header.tsx`)

**Reference:** `mocks/Header.jsx`

- Sticky, white background, `1px solid #e2e8f0` bottom border. **No backdrop-blur, no gradient, no shadow.**
- Layout: 14px vertical padding, 24px horizontal. `flex items-center gap-6`.
- **Wordmark** (left): a 14×14px solid slate-900 square + the text "BettingMaster", `text-base font-semibold tracking-tight text-slate-900`. **No `TrendingUp` icon, no blue.**
- **Search** (center, max-width 420px): single input, `border border-slate-200`, **square corners (`rounded-sm`)**, white background, search icon at `left-2.5`, **no inline submit button**, **no focus ring** — just `focus:border-slate-900`.
- **Nav** (right, `ml-auto`): underline tabs, not pills. Active = `text-slate-900 font-semibold border-b-2 border-slate-900`. Idle = `text-slate-500`. Tabs: "Best odds", "Surebets", "Leagues", "Live".
- **Feed status** (far right, after `border-l border-slate-200 pl-4`): a 6px green dot (`bg-emerald-500`, with the `bmPulse` animation) + `FEED OK` in `font-mono text-[11px] text-slate-500 uppercase tracking-wider`.

```css
@keyframes bmPulse { 0%,100%{opacity:1} 50%{opacity:.45} }
```

#### HeroBoard (new component)

**Reference:** `mocks/HeroBoard.jsx`

A flat white card (`border border-slate-200 bg-white p-6`). **No gradient, no shadow, no rounded-3xl.**

Top row (`flex justify-between items-start gap-6 flex-wrap`):

- **Left column** (max-width 720px):
  - Kicker: `Market view · TODAY` — `font-mono text-[10px] uppercase tracking-[0.14em] text-slate-500`
  - h1: "Best price across N bookmakers, in real time." — `text-[30px] font-semibold tracking-[-0.02em] text-slate-900 leading-[1.15]`
  - Sub: 13px slate-600, max-width 560px.
- **Right column — stats strip:** three columns separated by `border-l border-slate-200`, each `px-6 py-1`.
  - Each column: kicker (`text-[9px] uppercase tracking-[0.14em] text-slate-500`) + value (24px font-mono, slate-900).
  - The **Surebets** value goes emerald-700 only when `count > 0`.
  - The **Best margin** value goes emerald-700 only when `< 0` (i.e. it's a surebet).
  - **No dark navy background.**

Filter bar (`mt-6 pt-4 border-t border-slate-200 flex flex-wrap gap-6`):

- Four `<FilterGroup>`: State, Date, Sort, Sport.
- Each group is `flex items-center gap-3`: small mono kicker label + a row of underline tabs (`<Tab>` from `mocks/Primitives.jsx`).
- **Tabs, not capsule pills.** Active = `font-semibold text-slate-900 border-b-2 border-slate-900 pb-2`. Idle = `text-slate-500 border-b-2 border-transparent`.

Bookmaker row (`mt-4 pt-3 border-t border-dashed border-slate-200`):

- Kicker "Bookmakers in this view".
- A row of `<BookmakerChip>` (see Components below).

#### SurebetBanner (`src/components/SurebetBanner.tsx`)

**Reference:** `mocks/OddsTable.jsx` (the `SurebetBanner` is at the top of that file).

- `border border-emerald-200 border-l-[3px] border-l-emerald-700 bg-emerald-50 px-4 py-3`
- Layout: `flex items-center justify-between`.
- Left: `OPPORTUNITY` kicker (emerald-700), then the message "N live surebets on the board" (slate-900, 13px), then "best profit +2.14%" in font-mono emerald-700.
- Right: "View all →" link, emerald-700, 12px.
- **No background gradient, no green circular icon, no big shadow.** Hide entirely if `count === 0`.

#### BestOddsMatchCard (`src/components/BestOddsMatchCard.tsx`)

**Reference:** `mocks/BestOddsMatchCard.jsx`

A flat card with two regions: header strip + 3-cell outcomes grid.

- Outer: `border border-slate-200 bg-white`. **If `combined_margin < 0`** (surebet on this match), swap the left border to `border-l-[3px] border-l-emerald-700`.
- Header (`px-5 py-4 border-b border-slate-100 flex justify-between flex-wrap gap-4`):
  - Left: kicker "LA LIGA" + (if live) `<LiveBadge>` (red dot + `LIVE` in font-mono red-600 uppercase) + kickoff time in mono slate-500.
  - Middle: h2 "Real Madrid <vs in slate-400> Barcelona" — 18px, semibold, tracking-tight.
  - Sub: "5 bookmakers compared" in font-mono slate-500.
  - Right: a margin chip (`MARGIN +1.42%`, `font-mono text-[11px]`, neutral slate or emerald background depending on sign — see `marginTone()` in `mocks/Primitives.jsx`) and the dark `Open ›` action button (`bg-slate-900 text-white px-3.5 py-1.5`, square corners).
- Outcomes grid (`m-4 p-px grid grid-cols-3 gap-px bg-slate-200 border border-slate-200`):
  - Each cell: `bg-white p-4`.
  - Top row: outcome label kicker. **Only the cell with the highest odds across the three** gets a green `TOP PICK` tag (`bg-emerald-700 text-white text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5`).
  - Middle: the odds value, 28px font-mono semibold tracking-[-0.02em]. **Slate-900 normally, emerald-700 only on the TOP PICK cell.** **Do not color all three green** — the bug we fixed was that "best across books for this outcome" was being conflated with "best bet on this card".
  - Bottom: `<BookmakerChip>` on the left (neutral, see below), `VISIT ↗` mono link on the right.

#### Match list section

```tsx
<section>
  <header className="flex justify-between items-end pb-2 border-b border-slate-200">
    <div>
      <h2 className="text-lg font-semibold text-slate-900 tracking-tight">Best odds board</h2>
      <p className="mt-1 font-mono text-xs text-slate-500">{n} {state} matches · {date}</p>
    </div>
  </header>
  <div className="flex flex-col gap-4">{matches.map(...)}</div>
</section>
```

Empty state: `border border-dashed border-slate-300 bg-white p-12 text-center` with a 16px slate-900 heading and a 13px slate-500 sub.

### 2. Match Detail (`src/app/match/[id]/page.tsx`)

Stack:

1. Back link: `← Back to board`, font-mono 12px slate-600.
2. `<BestOddsMatchCard>` — same component as on the homepage.
3. **`<OutcomeBars>`** — the rewrite of `OutcomesPanel.tsx`. See below.
4. h2 "All bookmakers" + `<OddsTable>`.

#### OutcomeBars — rewrite of `OutcomesPanel.tsx`

**Reference:** `mocks/OutcomeBars.jsx`. This is the most complex and **most-iterated component** — read the mock carefully.

A flat white card showing the same 1X2 market across all bookmakers, side by side.

Layout: `border border-slate-200 bg-white p-5`.

Top row:

- Left: h2 "Odds for each result" (15px, semibold) + a 12px slate-500 paragraph explaining: *"Higher odds = bigger payout for you. The **BEST** tag marks the bookmaker paying the most per outcome. The bar shows how likely each result is, based on the price."* Bold "BEST" in emerald-700.
- Right: `font-mono text-[11px] text-slate-500 text-right` — "N bookmakers / updated HH:MM".

Column headers (`grid-cols-[140px_repeat(3,1fr)_80px] gap-3 mt-4 pb-2 border-b border-slate-200`):

- "Bookmaker" kicker.
- Three outcome columns. Each shows an outcome code kicker (`1`, `X`, `2`) above the team name (12px semibold slate-900).
- "Margin" kicker, right-aligned.

Per-bookmaker row (`grid-cols-[140px_repeat(3,1fr)_80px] gap-3 py-3.5 border-b border-slate-100`):

- **First column:** `<BookmakerName>` — 8×8px brand-colored swatch + the bookmaker name in 13px slate-900. **Not the saturated full-color chip.**
- **Three outcome cells.** Each is `relative` and contains:
  - A row with the price (18px font-mono semibold tabular-nums) + `implied N%` (10px font-mono slate-400).
  - A 5px-tall bar below: `bg-slate-100`, with a fill `width: <implied%>` colored `bg-slate-300` normally or `bg-emerald-700` if this bookmaker has the **best** (highest) price in this column.
  - **A small `BEST` tag in the top-right** of the cell — only when this bookmaker holds the highest price in this column. (Multiple BEST tags per row are fine — they mean "this book is best for *this outcome*".)
  - Price text turns `text-emerald-700` when it's the best.
- **Last column:** the per-bookmaker margin (`+N.NN%`), font-mono, slate-500, right-aligned.

Critical logic — **fix the production bug here:**

```ts
// Best PRICE = highest odds in column (best for the bettor).
// NOT the highest implied probability (which would be the LOWEST odds).
const best = {};
['home','draw','away'].forEach(sel => {
  let max = 0;
  rows.forEach(r => { const v = r.odds[sel] ?? 0; if (v > max) max = v; });
  best[sel] = max;
});
```

Market-average row (`mt-3 bg-slate-50 border border-slate-200 p-3.5`):

- Same grid, but: gray dot + "Market average" label, average odds (slate-600), bar in slate-300/slate-400, and the calculated market margin on the right.

Legend (`mt-3.5 pt-3 border-t border-dashed border-slate-200 flex flex-wrap gap-4 text-[11px] text-slate-500`):

- `[emerald bar] **Best** — highest odds in this column`
- `[slate-300 bar] Other bookmakers`
- `[slate-400 bar] Market average`

#### OddsTable (`src/components/OddsTable.tsx`)

**Reference:** `mocks/OddsTable.jsx`

Flat HTML table, `border border-slate-200 bg-white`. Replace the existing component wholesale.

- `<thead>`: slate-50 background, `border-b border-slate-200`. Cells use `font-mono text-[10px] uppercase tracking-wider text-slate-500`.
- `<tbody>` rows: `border-b border-slate-100`, hover `bg-slate-50`.
  - First cell: `<BookmakerName>` (dot + slate-900 name).
  - Outcome cells: right-aligned, font-mono tabular-nums.
  - The cell holding the column's max odds gets `font-semibold text-emerald-700` and a small inline `BEST` tag (same style as in `OutcomeBars`).
- `<tfoot>`: `border-t border-emerald-700 bg-emerald-50` "Best per outcome" summary row, with the max value (15px font-mono semibold emerald-700) and the bookmaker name (10px mono slate-500) below.

---

## Components

### `<BookmakerChip>` (reference: `mocks/Primitives.jsx`)

The single most important reusable token in this refresh. **Used wherever a bookmaker is attributed** (best-odds cells, hero "Bookmakers in this view" row).

- `inline-flex items-center gap-1.5 bg-slate-50 border border-slate-200 text-slate-700 px-2 py-0.5 text-[10px] font-medium rounded-sm font-sans`
- Inside, a 6px circular dot uses the bookmaker's brand background color (e.g. Fortuna `#ffdb01`, Niké `#0d0d0d`, DOXXbet `#272727`, Tipsport `#167be8`, Tipos `#e30613`, Polymarket `#0d1117`). The dot is the only branded surface.
- Followed by the bookmaker display name in slate-700.
- **Why:** earlier iterations used full bookmaker brand-color fills (yellow Fortuna chip, blue Tipsport chip, etc.) and the bookmakers ended up dominating the visual hierarchy. The dot-only version keeps brand identity recognizable but lets the data win.

### `<BookmakerName>` — table-row variant

- 8×8px brand-color square (border-radius 2px) + 13px slate-900 name. No background or border.

### `<Tab>` (filter underline tab)

- `bg-transparent border-0 px-0 py-2 text-[13px] font-medium`
- Active: `text-slate-900 font-semibold border-b-2 border-slate-900`.
- Idle: `text-slate-500 border-b-2 border-transparent`.
- Optional `tone="emerald"` variant: active color/border becomes emerald-700.

### `<Kicker>`

- `font-mono text-[10px] uppercase tracking-[0.14em] text-slate-500 font-semibold`.

### Bookmaker brand map

In `src/lib/constants.ts`, replace the existing `BOOKMAKERS` map with:

```ts
export const BOOKMAKERS = {
  fortuna:    { displayName: "Fortuna",    color: "#17171b", bgColor: "#ffdb01" },
  nike:       { displayName: "Niké",       color: "#ff8000", bgColor: "#0d0d0d" },
  doxxbet:    { displayName: "DOXXbet",    color: "#f31537", bgColor: "#272727" },
  tipsport:   { displayName: "Tipsport",   color: "#ff8e13", bgColor: "#167be8" },
  tipos:      { displayName: "Tipos",      color: "#ffffff", bgColor: "#e30613" },
  polymarket: { displayName: "Polymarket", color: "#2d9cdb", bgColor: "#0d1117" },
};
```

These hex values were sampled from screenshots of each bookmaker's actual product. Don't substitute approximations.

---

## Interactions & Behavior

- **Filter tabs** call existing setState handlers; no other changes.
- **`Open ›` button on match card** navigates to `/match/{id}`.
- **`bmPulse` animation** runs on the LIVE dot and the FEED OK dot (2s ease-in-out infinite, opacity 1 → .45 → 1).
- **Hover state** on rows: `hover:bg-slate-50`. On primary buttons: `hover:bg-slate-700`. Nothing else.
- **Live updates:** unchanged — keep React Query polling. Just style the existing badge with the new feed-status pattern.

---

## Design Tokens Cheat Sheet

| Token | Value |
|---|---|
| Background | `#ffffff` (page) / `#f8fafc` (subtle muted) |
| Foreground | `#0f172a` slate-900 |
| Muted text | `#64748b` slate-500 |
| Border | `#e2e8f0` slate-200 |
| Hairline | `#f1f5f9` slate-100 |
| Best (emerald) | `#047857` text · `#ecfdf5` bg · `#a7f3d0` border |
| Live (red) | `#dc2626` text/dot only — never as background |
| Primary button bg | `#0f172a` |
| Radius | `4px` |
| Card padding | `16px` |
| Section gap | `24px` |
| Sans | Geist · 400/500/600/700 |
| Mono | JetBrains Mono · 400/500/600 — for all numbers + uppercase metadata |

## Assets

No raster assets. The wordmark is a 14×14 solid slate-900 square + the word "BettingMaster". Icons (search, external link, chevron, arrow) are inline SVG copied from lucide-react and already available in the codebase.

## Files in this bundle

```
mocks/                       — runnable HTML/JSX prototype (open mocks/index.html)
  index.html                 — entry, app shell, mock data
  Primitives.jsx             — Tab, Kicker, BookmakerChip/Name, BOOKMAKERS map
  Header.jsx
  HeroBoard.jsx
  BestOddsMatchCard.jsx
  OddsTable.jsx              — (also contains SurebetBanner)
  OutcomeBars.jsx            — rewrite of OutcomesPanel
reference/
  colors_and_type.css        — full token CSS, lifted 1:1 from production with new accents
  components-prob-bars.html  — standalone preview card for OutcomeBars (most iterated)
  components-buttons.html    — buttons / filter-tabs / status chips spec
  components-inputs.html     — search input + feed-status chip states
  components-odds-cell.html  — the three states of an outcome cell
  colors-bookmakers.html     — sampled bookmaker brand colors
  colors-semantic.html       — semantic-accent dot map (5 accents)
  brand-backgrounds.html     — surface recipes (flat data-terminal style)
  _shared.css                — preview-only base
```

## Implementation order (suggested PRs)

1. **Tokens + fonts.** layout.tsx, globals.css, tailwind.config.ts. The site visually shifts immediately even before component work.
2. **Header.** Smallest, highest visibility, lands the new look in the chrome.
3. **BestOddsMatchCard + SurebetBanner.** Homepage now matches the mock.
4. **HeroBoard.** New component on the home page.
5. **OutcomeBars (replaces OutcomesPanel) + OddsTable.** Match-detail page now matches.
6. Sweep — apply `<BookmakerChip>` / `<BookmakerName>` everywhere they appear in the rest of the app.

## Don'ts (things prior iterations rejected)

- ❌ No radial-gradient backgrounds.
- ❌ No `rounded-2xl` / `rounded-3xl` / `rounded-full` capsule filter pills.
- ❌ No "marketing" gradients on banners or buttons.
- ❌ No saturated bookmaker brand-color chip backgrounds (use the dot pattern).
- ❌ No coloring all three outcome cells green — only the single highest-odds cell on a card gets `TOP PICK`.
- ❌ No "best = highest implied probability" logic — best = highest odds.
- ❌ No backdrop-blur, no large box-shadows. A `1px` border is enough.
- ❌ No emoji, no decorative icons in titles. Lucide icons only where they carry meaning (search, external link, chevron, live dot).
