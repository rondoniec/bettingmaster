function getApiBase() {
  if (typeof window === "undefined") {
    return process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://backend:8000";
  }

  return process.env.NEXT_PUBLIC_API_URL ?? window.location.origin;
}

export type Sport = {
  id: string;
  name: string;
};

export type League = {
  id: string;
  sport_id: string;
  name: string;
  country: string;
};

export type Match = {
  id: string;
  league_id: string;
  home_team: string;
  away_team: string;
  start_time: string;
  status: string;
};

export type OddsEntry = {
  bookmaker: string;
  market: string;
  selection: string;
  odds: number;
  url?: string;
  scraped_at: string;
  checked_at?: string | null;
};

export type MatchDetail = Match & {
  odds: OddsEntry[];
};

export type BestOddsSelection = {
  selection: string;
  odds: number;
  bookmaker: string;
  url?: string;
  scraped_at: string;
  checked_at?: string | null;
};

export type BestOdds = {
  match_id: string;
  market: string;
  selections: BestOddsSelection[];
  combined_margin: number;
};

export type OddsHistoryPoint = {
  bookmaker: string;
  odds: number;
  scraped_at: string;
};

export type OddsHistorySeries = {
  market: string;
  selection: string;
  history: OddsHistoryPoint[];
};

export type MatchBestOdds = Match & {
  market: string;
  selections: BestOddsSelection[];
  combined_margin: number;
  bookmakers: string[];
};

export type Surebet = {
  match_id: string;
  home_team: string;
  away_team: string;
  league_id: string;
  start_time: string;
  market: string;
  selections: BestOddsSelection[];
  margin: number;
  profit_percent: number;
};

export type NewPolymarketSubMarket = {
  name: string;
  slug: string;
  url: string;
  market_count: number;
};

export type NewPolymarketMarket = {
  title: string;
  slug: string;
  url: string;
  start_time?: string | null;
  created_at?: string | null;
  market_count: number;
  league_hint?: string | null;
  markets?: NewPolymarketSubMarket[];
};

export type ScraperHealth = {
  last_scraped_at?: string | null;
  interval_seconds: number;
  age_seconds?: number | null;
  freshness: "fresh" | "aging" | "stale" | "idle" | string;
};

export type HealthStatus = {
  status: string;
  db: string;
  scrapers: Record<string, ScraperHealth>;
};

export type MatchesQueryParams = {
  date?: string;
  sport?: string;
  status?: string;
};

export type BestOddsMatchesQueryParams = MatchesQueryParams & {
  league_id?: string;
  market?: string;
  min_bookmakers?: number;
  bookmakers?: string[];
};

async function apiFetch<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${getApiBase()}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }

  const response = await fetch(url.toString(), {
    headers: { "Content-Type": "application/json" },
    next: { revalidate: 30 },
  });

  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText} (${path})`);
  }

  return response.json() as Promise<T>;
}

export async function getSports(): Promise<Sport[]> {
  return apiFetch<Sport[]>("/api/sports");
}

export async function getLeaguesBySport(sportId: string): Promise<League[]> {
  return apiFetch<League[]>(`/api/sports/${encodeURIComponent(sportId)}/leagues`);
}

export async function getLeague(leagueId: string): Promise<League> {
  return apiFetch<League>(`/api/leagues/${encodeURIComponent(leagueId)}`);
}

export async function getMatchesByLeague(leagueId: string, date?: string): Promise<Match[]> {
  const params: Record<string, string> = {};
  if (date) {
    params.date = date;
  }
  return apiFetch<Match[]>(`/api/leagues/${encodeURIComponent(leagueId)}/matches`, params);
}

export async function getMatches(params?: MatchesQueryParams): Promise<Match[]> {
  const query: Record<string, string> = {};
  if (params?.date) {
    query.date = params.date;
  }
  if (params?.sport) {
    query.sport = params.sport;
  }
  if (params?.status) {
    query.status = params.status;
  }
  return apiFetch<Match[]>("/api/matches", query);
}

export async function getMatchDetail(matchId: string): Promise<MatchDetail> {
  return apiFetch<MatchDetail>(`/api/matches/${encodeURIComponent(matchId)}`);
}

export async function getBestOdds(matchId: string): Promise<BestOdds[]> {
  return apiFetch<BestOdds[]>(`/api/matches/${encodeURIComponent(matchId)}/best-odds`);
}

export async function getMatchesWithBestOdds(
  params?: BestOddsMatchesQueryParams
): Promise<MatchBestOdds[]> {
  const query: Record<string, string> = {};
  if (params?.date) {
    query.date = params.date;
  }
  if (params?.sport) {
    query.sport = params.sport;
  }
  if (params?.league_id) {
    query.league_id = params.league_id;
  }
  if (params?.status) {
    query.status = params.status;
  }
  if (params?.market) {
    query.market = params.market;
  }
  if (params?.min_bookmakers !== undefined) {
    query.min_bookmakers = String(params.min_bookmakers);
  }
  if (params?.bookmakers && params.bookmakers.length > 0) {
    query.bookmakers = params.bookmakers.join(",");
  }
  return apiFetch<MatchBestOdds[]>("/api/matches/best-odds", query);
}

export async function getOddsHistory(
  matchId: string,
  market: string
): Promise<OddsHistorySeries[]> {
  return apiFetch<OddsHistorySeries[]>(`/api/matches/${encodeURIComponent(matchId)}/history`, {
    market,
  });
}

export async function getSurebets(): Promise<Surebet[]> {
  return apiFetch<Surebet[]>("/api/surebets");
}

export async function getNonSportsPolymarketMarkets(): Promise<NewPolymarketMarket[]> {
  return apiFetch<NewPolymarketMarket[]>("/api/polymarket/non-sports");
}

export async function getNewPolymarketMarkets(): Promise<NewPolymarketMarket[]> {
  return apiFetch<NewPolymarketMarket[]>("/api/polymarket/new-football-markets");
}

export async function searchMatches(q: string): Promise<Match[]> {
  return apiFetch<Match[]>("/api/search", { q });
}

export async function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/api/health");
}
