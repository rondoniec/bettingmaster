"""Fortuna.sk (ifortuna.sk) scraper using their public offer API.

Confirmed working endpoints (no auth required):
  Base URL: https://api.ifortuna.sk/offer

  Structure API (/structure/api/v1_0):
    GET /sports                                    — all sports
    GET /sport/{sportId}/tournaments?categories=true — tournaments for a sport
    GET /tournament/{tournamentId}/matches          — fixtures for a tournament
    GET /fixture/{fixtureId}?markets=true           — single fixture detail

  Markets API (/markets/api/v1_0):
    GET /fixture/{fixtureId}/markets                — all markets/odds for a fixture
    GET /fixture/{fixtureId}/markets/overview       — overview markets

  Result API (/result/api/v1_0):
    GET /tournament/{tournamentId}/fixtures          — results

Sport IDs:
  ufo:sprt:00 = Futbal (Football)
  ufo:sprt:0w = Hokej (Hockey)
  ufo:sprt:0x = Tenis (Tennis)
  ufo:sprt:0i = Basketbal (Basketball)

Tournament IDs (Football):
  ufo:tour:00-062 = 1. Slovensko (Niké Liga)
  ufo:tour:00-06l = 2. Slovensko
  ufo:tour:00-0ai = Slovensko - pohár

Market identification:
  "Výsledok zápasu" (Match Result / 1X2): outcomes 1=home, 0=draw, 2=away
  "Výsledok zápasu - dvojtip" (Double Chance): outcomes 10=home_draw, 12=home_away, 02=draw_away
  "Oba tímy dajú gól" (BTTS): outcomes Áno=yes, Nie=no
  "Počet gólov" (Over/Under): outcomes Menej=under, Viac=over

Uses Scrapling's Fetcher with Chrome TLS impersonation.
"""

import logging
import re
from datetime import UTC, datetime
from typing import Optional

from scrapling.fetchers import Fetcher

from bettingmaster.odds_writer import add_odds_snapshot
from bettingmaster.scrapers.base import BaseScraper, RawMatch, RawOdds
from bettingmaster.scope import is_match_in_active_scope

logger = logging.getLogger(__name__)

API_BASE = "https://api.ifortuna.sk/offer"
STRUCTURE = "/structure/api/v1_0"
MARKETS = "/markets/api/v1_0"

# Map exact Fortuna market names to our canonical names
MARKET_NAME_MAP = {
    # Full match
    "Výsledok zápasu":              "1x2",
    "Výsledok zápasu - dvojtip":    "double_chance",
    "Výsledok zápasu bez remízy":   "draw_no_bet",
    "Oba tímy dajú gól":            "btts",
    "Zápas/oba tímy dajú gól":      "result_btts",
    "Postup":                        "to_qualify",
    # Half-time
    "Výsledok 1. polčasu":          "1x2_ht",
    "Výsledok 1. polčasu - dvojtip":"double_chance_ht",
    "1.polčas: oba tímy dajú gól":  "btts_ht",
    # 2nd half
    "2.polčas":                     "1x2_2h",
    "Výsledok 2. polčasu - dvojtip":"double_chance_2h",
}

# Over/under market names follow the pattern "Počet gólov X" (e.g. "Počet gólov 2.5")
OVER_UNDER_RE = re.compile(r"^Počet gólov (\d+(?:\.\d+)?)$")

# Outcome name → canonical selection
SELECTION_MAP_1X2 = {"1": "home", "0": "draw", "2": "away"}

SELECTION_MAP_DC = {
    "10": "home_draw",   # 1X
    "12": "home_away",   # 12
    "02": "draw_away",   # X2
}

SELECTION_MAP_BTTS = {"Áno": "yes", "Nie": "no"}

# result_btts combinations: "{result}/{btts}" e.g. "1/Áno" → "home_yes"
SELECTION_MAP_RESULT_BTTS = {
    "1/Áno": "home_yes",  "1/Nie": "home_no",
    "0/Áno": "draw_yes",  "0/Nie": "draw_no",
    "2/Ano": "away_yes",  "2/Nie": "away_no",  "2/Áno": "away_yes",
}

# Map Fortuna tournament IDs to our league IDs
TOURNAMENT_MAP = {
    "ufo:tour:00-062": "sk-fortuna-liga",
    "ufo:tour:00-03m": "en-premier-league",
    "ufo:tour:00-0c6": "de-bundesliga",
    "ufo:tour:00-0h7": "es-la-liga",
    "ufo:tour:00-06t": "it-serie-a",
}

# Reverse lookup
LEAGUE_TO_TOURNAMENT = {v: k for k, v in TOURNAMENT_MAP.items()}


def _utc_from_timestamp(raw: int | float) -> datetime:
    return datetime.fromtimestamp(raw, UTC).replace(tzinfo=None)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FortunaScraper(BaseScraper):
    BOOKMAKER = "fortuna"
    BASE_URL = "https://www.ifortuna.sk"
    REQUEST_DELAY = 1.0

    def _api_get(self, path: str) -> dict | list | None:
        """Make a GET request to Fortuna offer API."""
        url = f"{API_BASE}{path}"
        try:
            page = Fetcher.get(url, impersonate="chrome", stealthy_headers=True)
            if page.status == 200 and page.body:
                return page.json()
            else:
                logger.warning(f"[fortuna] {url} returned status {page.status}")
                return None
        except Exception:
            logger.exception(f"[fortuna] Failed to fetch {url}")
            return None

    def scrape_matches(self, league_external_id: str) -> list[RawMatch]:
        """Scrape matches for a tournament."""
        path = f"{STRUCTURE}/tournament/{league_external_id}/matches"
        data = self._api_get(path)
        if not data or not isinstance(data, dict):
            return []

        fixtures = data.get("fixtures", [])
        matches = []
        for f in fixtures:
            rm = self._parse_fixture(f, league_external_id)
            if rm:
                matches.append(rm)
        return matches

    def scrape_odds(self, match_external_id: str) -> list[RawOdds]:
        """Scrape odds for a specific fixture."""
        path = f"{MARKETS}/fixture/{match_external_id}/markets"
        data = self._api_get(path)
        if not data or not isinstance(data, list):
            return []
        return self._parse_markets(data, match_external_id)

    def run(self, league_ids: dict[str, str], normalizer=None):
        """Override base run for efficient per-tournament fetching with inline odds."""
        from bettingmaster.scrapers.base import generate_match_id
        from bettingmaster.models.match import Match

        for our_league_id, ext_id in league_ids.items():
            try:
                self._scrape_tournament(
                    our_league_id, ext_id, normalizer,
                    generate_match_id, Match,
                )
            except Exception:
                logger.exception(
                    f"[fortuna] Failed to scrape league {our_league_id}"
                )

    def _scrape_tournament(self, league_id, tournament_id, normalizer,
                           generate_match_id, Match):
        """Fetch all matches for a tournament and their odds."""
        # Step 1: Get fixtures
        path = f"{STRUCTURE}/tournament/{tournament_id}/matches"
        data = self._api_get(path)
        if not data or not isinstance(data, dict):
            logger.warning(f"[fortuna] No data for tournament {tournament_id}")
            return

        fixtures = data.get("fixtures", [])
        logger.info(f"[fortuna] Tournament {tournament_id}: {len(fixtures)} fixtures")

        for fixture in fixtures:
            try:
                self._process_fixture(
                    fixture, league_id, normalizer,
                    generate_match_id, Match,
                )
            except Exception:
                name = fixture.get("name", "?")
                logger.exception(f"[fortuna] Failed: {name}")

    def _process_fixture(self, fixture, league_id, normalizer,
                         generate_match_id, Match):
        """Process a single fixture: parse teams, fetch odds, save."""
        participants = fixture.get("participants", [])
        home_raw = ""
        away_raw = ""
        for p in participants:
            if p.get("type") == "HOME":
                home_raw = p.get("name", "")
            elif p.get("type") == "AWAY":
                away_raw = p.get("name", "")

        if not home_raw or not away_raw:
            # Try parsing from the combined name
            name = fixture.get("name", "")
            if " - " in name:
                parts = name.split(" - ", 1)
                home_raw = home_raw or parts[0].strip()
                away_raw = away_raw or parts[1].strip()

        if not home_raw or not away_raw:
            return

        # Normalize team names
        home = home_raw
        away = away_raw
        if normalizer:
            home = normalizer.normalize(home_raw, self.BOOKMAKER) or home_raw
            away = normalizer.normalize(away_raw, self.BOOKMAKER) or away_raw

        # Parse start time (Unix timestamp in milliseconds)
        start_ms = fixture.get("startDatetime", 0)
        if start_ms > 1e12:
            start_time = _utc_from_timestamp(start_ms / 1000)
        elif start_ms > 0:
            start_time = _utc_from_timestamp(start_ms)
        else:
            start_time = _utc_now()

        if not is_match_in_active_scope(league_id, start_time):
            return

        match_id = generate_match_id(
            league_id, home, away, start_time.strftime("%Y-%m-%d")
        )

        # Upsert match
        ext_id = fixture.get("id", "")
        kind = fixture.get("kind", "PREMATCH")
        status = "live" if kind == "LIVE" else "prematch"

        seo = fixture.get("seoName", "")
        cat_seo = fixture.get("categorySeoName", "")
        tour_seo = fixture.get("tournamentSeoName", "")
        sport_seo = fixture.get("sportSeoName", "")
        match_url = (
            f"{self.BASE_URL}/stavkovanie/{sport_seo}/{cat_seo}"
            f"/{tour_seo}/{seo}"
        )

        match = self._db.get(Match, match_id)
        if match is None:
            match = Match(
                id=match_id,
                league_id=league_id,
                home_team=home,
                away_team=away,
                start_time=start_time,
                status=status,
                external_ids={self.BOOKMAKER: ext_id},
            )
            self._db.add(match)
        else:
            ext = dict(match.external_ids or {})
            ext[self.BOOKMAKER] = ext_id
            match.external_ids = ext
            if kind == "LIVE":
                match.status = "live"

        self._db.flush()

        # Step 2: Fetch markets/odds for this fixture
        markets_path = f"{MARKETS}/fixture/{ext_id}/markets"
        markets_data = self._api_get(markets_path)

        now = _utc_now()
        odds_count = 0

        if markets_data and isinstance(markets_data, list):
            for market in markets_data:
                market_name = market.get("name", "")
                canonical_market = MARKET_NAME_MAP.get(market_name)
                if not canonical_market:
                    m = OVER_UNDER_RE.match(market_name)
                    canonical_market = f"over_under_{m.group(1)}" if m else None
                if not canonical_market:
                    continue  # Skip markets we don't track

                outcomes = market.get("outcomes", [])
                for outcome in outcomes:
                    odds_val = outcome.get("odds")
                    if odds_val is None:
                        continue

                    outcome_name = outcome.get("name", "")
                    sel_name = self._map_selection(
                        canonical_market, outcome_name
                    )
                    if not sel_name:
                        continue

                    add_odds_snapshot(
                        self._db,
                        match_id=match_id,
                        bookmaker=self.BOOKMAKER,
                        market=canonical_market,
                        selection=sel_name,
                        odds=float(odds_val),
                        url=match_url,
                        scraped_at=now,
                    )
                    odds_count += 1

        self._db.commit()
        logger.debug(
            f"[fortuna] Saved: {home} vs {away} ({odds_count} odds)"
        )

    def _map_selection(self, market: str, outcome_name: str) -> str | None:
        """Map a Fortuna outcome name to our canonical selection name."""
        if market in ("1x2", "1x2_ht", "1x2_2h", "draw_no_bet", "to_qualify"):
            return SELECTION_MAP_1X2.get(outcome_name)
        elif market in ("double_chance", "double_chance_ht", "double_chance_2h"):
            return SELECTION_MAP_DC.get(outcome_name)
        elif market in ("btts", "btts_ht"):
            return SELECTION_MAP_BTTS.get(outcome_name)
        elif market == "result_btts":
            return SELECTION_MAP_RESULT_BTTS.get(outcome_name)
        elif market.startswith("over_under_"):
            # outcome_name is e.g. "+ 2.5" or "- 2.5"
            if outcome_name.startswith("+"):
                return "over"
            elif outcome_name.startswith("-"):
                return "under"
        return None

    def _parse_fixture(self, fixture: dict, tournament_id: str) -> Optional[RawMatch]:
        """Parse a fixture dict into RawMatch."""
        ext_id = fixture.get("id", "")
        if not ext_id:
            return None

        participants = fixture.get("participants", [])
        home = ""
        away = ""
        for p in participants:
            if p.get("type") == "HOME":
                home = p.get("name", "")
            elif p.get("type") == "AWAY":
                away = p.get("name", "")

        if not home or not away:
            name = fixture.get("name", "")
            if " - " in name:
                parts = name.split(" - ", 1)
                home = home or parts[0].strip()
                away = away or parts[1].strip()

        if not home or not away:
            return None

        start_ms = fixture.get("startDatetime", 0)
        if start_ms > 1e12:
            start_time = _utc_from_timestamp(start_ms / 1000)
        elif start_ms > 0:
            start_time = _utc_from_timestamp(start_ms)
        else:
            start_time = _utc_now()

        kind = fixture.get("kind", "PREMATCH")
        status = "live" if kind == "LIVE" else "prematch"

        seo = fixture.get("seoName", "")
        cat_seo = fixture.get("categorySeoName", "")
        tour_seo = fixture.get("tournamentSeoName", "")
        sport_seo = fixture.get("sportSeoName", "")

        return RawMatch(
            external_id=ext_id,
            home_team=home,
            away_team=away,
            league_external_id=tournament_id,
            start_time=start_time,
            status=status,
            url=(
                f"{self.BASE_URL}/stavkovanie/{sport_seo}/{cat_seo}"
                f"/{tour_seo}/{seo}"
            ),
        )

    def _parse_markets(self, markets: list, fixture_id: str) -> list[RawOdds]:
        """Parse market data into RawOdds."""
        odds = []
        for market in markets:
            market_name = market.get("name", "")
            canonical_market = MARKET_NAME_MAP.get(market_name)
            if not canonical_market:
                m = OVER_UNDER_RE.match(market_name)
                canonical_market = f"over_under_{m.group(1)}" if m else None
            if not canonical_market:
                continue

            outcomes = market.get("outcomes", [])
            for outcome in outcomes:
                odds_val = outcome.get("odds")
                if odds_val is None:
                    continue

                outcome_name = outcome.get("name", "")
                sel_name = self._map_selection(canonical_market, outcome_name)
                if not sel_name:
                    continue

                odds.append(RawOdds(
                    match_external_id=fixture_id,
                    market=canonical_market,
                    selection=sel_name,
                    odds=float(odds_val),
                ))

        return odds

    def discover_sports(self) -> list:
        """Fetch all available sports."""
        return self._api_get(f"{STRUCTURE}/sports") or []

    def discover_tournaments(self, sport_id: str = "ufo:sprt:00") -> dict:
        """Fetch all tournaments for a sport."""
        return self._api_get(
            f"{STRUCTURE}/sport/{sport_id}/tournaments?categories=true"
        ) or {}
