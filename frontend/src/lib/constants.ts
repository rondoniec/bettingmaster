export const BOOKMAKERS: Record<
  string,
  { displayName: string; color: string; bgColor: string }
> = {
  fortuna: {
    displayName: "Fortuna",
    color: "#e4003b",
    bgColor: "#fde8ed",
  },
  nike: {
    displayName: "Nike",
    color: "#f5a623",
    bgColor: "#fef3e2",
  },
  doxxbet: {
    displayName: "DOXXbet",
    color: "#00a859",
    bgColor: "#e6f7ef",
  },
  tipsport: {
    displayName: "Tipsport",
    color: "#0066cc",
    bgColor: "#e6f0fa",
  },
  tipos: {
    displayName: "Tipos",
    color: "#8b5cf6",
    bgColor: "#f0ebfe",
  },
  polymarket: {
    displayName: "Polymarket",
    color: "#0038ff",
    bgColor: "#e6ecff",
  },
};

export const BOOKMAKER_ORDER = ["fortuna", "nike", "doxxbet", "tipsport", "tipos", "polymarket"];

export const MARKET_LABELS: Record<string, string> = {
  // Moneyline / full-time result
  "1x2": "Match result",
  // Handicap / spreads
  handicap_1_5: "Handicap ±1.5",
  handicap_2_5: "Handicap ±2.5",
  // Totals
  over_under_1_5: "Over/Under 1.5",
  over_under_2_5: "Over/Under 2.5",
  over_under_3_5: "Over/Under 3.5",
  over_under_4_5: "Over/Under 4.5",
  // Both teams to score
  btts: "Both teams to score",
  // Halftime result
  "1x2_ht": "Half-time result",
  // Legacy (kept so old DB rows still display)
  double_chance: "Double chance",
  draw_no_bet: "Draw no bet",
  to_qualify: "To qualify",
  handicap: "Handicap",
  over_under_2: "Over/Under 2.0",
  over_under_3: "Over/Under 3.0",
};

export const MARKET_TABS = [
  { key: "1x2", label: "Moneyline" },
  { key: "handicap_1_5", label: "Spreads" },
  { key: "over_under_2_5", label: "Totals" },
  { key: "btts", label: "BTTS" },
  { key: "1x2_ht", label: "Halftime" },
];

export const SELECTION_LABELS: Record<string, string> = {
  home: "1",
  draw: "X",
  away: "2",
  home_draw: "1X",
  home_away: "12",
  draw_away: "X2",
  yes: "Yes",
  no: "No",
  over: "Over",
  under: "Under",
};

export const SELECTION_ORDER: Record<string, string[]> = {
  "1x2": ["home", "draw", "away"],
  "1x2_ht": ["home", "draw", "away"],
  handicap_1_5: ["home", "away"],
  handicap_2_5: ["home", "away"],
  over_under_1_5: ["over", "under"],
  over_under_2_5: ["over", "under"],
  over_under_3_5: ["over", "under"],
  over_under_4_5: ["over", "under"],
  btts: ["yes", "no"],
  // Legacy
  double_chance: ["home_draw", "home_away", "draw_away"],
  draw_no_bet: ["home", "away"],
  to_qualify: ["home", "away"],
  handicap: ["home", "away"],
  over_under_2: ["over", "under"],
  over_under_3: ["over", "under"],
};

export function getBookmakerDisplay(id: string) {
  return (
    BOOKMAKERS[id] ?? {
      displayName: id.charAt(0).toUpperCase() + id.slice(1),
      color: "#6b7280",
      bgColor: "#f3f4f6",
    }
  );
}

export function getMarketLabel(market: string): string {
  if (MARKET_LABELS[market]) return MARKET_LABELS[market];
  // Dynamic patterns
  const ouMatch = market.match(/^over_under_(\d+)_(\d+)$/);
  if (ouMatch) return `Over/Under ${ouMatch[1]}.${ouMatch[2]}`;
  const hcMatch = market.match(/^handicap_(\d+)_(\d+)$/);
  if (hcMatch) return `Handicap ±${hcMatch[1]}.${hcMatch[2]}`;
  return market;
}

export function getSelectionLabel(selection: string): string {
  return SELECTION_LABELS[selection] ?? selection;
}

/**
 * Returns a human-readable label for a selection, substituting actual team
 * names for "home" / "away" so readers can't mix up which side is which.
 *
 * Examples:
 *   resolveSelectionLabel("home", "Levante", "Getafe")  → "Levante"
 *   resolveSelectionLabel("away", "Levante", "Getafe")  → "Getafe"
 *   resolveSelectionLabel("draw", ...)                   → "Draw"
 *   resolveSelectionLabel("home_draw", "Levante", ...)  → "Levante or Draw"
 *   resolveSelectionLabel("draw_away", ..., "Getafe")   → "Draw or Getafe"
 *   resolveSelectionLabel("home_away", "Levante","Getafe") → "Levante or Getafe"
 */
export function resolveSelectionLabel(
  selection: string,
  homeTeam?: string,
  awayTeam?: string,
): string {
  switch (selection) {
    case "home":
      return homeTeam ?? "1";
    case "away":
      return awayTeam ?? "2";
    case "draw":
      return "Draw";
    case "home_draw":
      return homeTeam ? `${homeTeam} or Draw` : "1X";
    case "draw_away":
      return awayTeam ? `Draw or ${awayTeam}` : "X2";
    case "home_away":
      return homeTeam && awayTeam ? `${homeTeam} or ${awayTeam}` : "12";
    default:
      return SELECTION_LABELS[selection] ?? selection;
  }
}
