"""Nike.sk scraper using their public API gateway."""

from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime
from typing import Optional

from scrapling.fetchers import Fetcher

from bettingmaster.odds_writer import add_odds_snapshot
from bettingmaster.scrapers.base import BaseScraper, RawMatch, RawOdds, ScraperRunSummary
from bettingmaster.scope import is_match_in_active_scope

logger = logging.getLogger(__name__)


class NikeRateLimitError(RuntimeError):
    """Raised when Nike keeps returning HTTP 429 after retries."""


def _normalized_text(value: str | None) -> str:
    return (
        (value or "")
        .strip()
        .lower()
        .replace("Ã¡", "á")
        .replace("Ã­", "í")
        .replace("Ã³", "ó")
        .replace("Ãº", "ú")
        .replace("Ä", "č")
    )

def _btts_market(normalized_header: str) -> str:
    if "1.pol." in normalized_header or "1. pol" in normalized_header:
        return "btts_ht"
    if "2.pol." in normalized_header or "2. pol" in normalized_header:
        return "btts_2h"
    return "btts"


# Tournament config: tournamentId -> fallback metadata.
TOURNAMENT_MAP: dict[str, dict[str, str]] = {
    "30": {
        "league_id": "sk-fortuna-liga",
        "box_id": "bi-1-809-30",
        "slug": "/futbal/slovensko/nike-liga",
    },
    "1": {
        "league_id": "en-premier-league",
        "box_id": "bi-1-802-1",
        "slug": "/futbal/anglicko/anglicko-i-liga",
    },
    "12": {
        "league_id": "de-bundesliga",
        "box_id": "bi-1-872-12",
        "slug": "/futbal/nemecko/nemecko-i-liga",
    },
    "24": {
        "league_id": "es-la-liga",
        "box_id": "bi-1-994-24",
        "slug": "/futbal/spanielsko/spanielsko-i-liga",
    },
    "26": {
        "league_id": "it-serie-a",
        "box_id": "bi-1-929-26",
        "slug": "/futbal/taliansko/taliansko-i-liga",
    },
    "285": {
        "league_id": "sk-tipos-extraliga",
        "box_id": "bi-3-816-285",
        "slug": "/hokej/slovensko/slovensko-extraliga",
    },
    "953": {
        "league_id": "ucl",
        "box_id": "bi-1-97-953",
        "slug": "/futbal/liga-majstrov/liga-majstrov",
    },
}

LEAGUE_TO_TOURNAMENT: dict[str, str] = {
    meta["league_id"]: tournament_id for tournament_id, meta in TOURNAMENT_MAP.items()
}

ZAPAS_TIP_MAP = {
    "49": ("1x2", "home"),
    "88": ("1x2", "draw"),
    "50": ("1x2", "away"),
    "52": ("double_chance", "home_draw"),
    "51": ("double_chance", "home_away"),
    "53": ("double_chance", "draw_away"),
}

SK_YESNO = {"áno": "yes", "ano": "yes", "nie": "no"}
_OU_NAME_RE = re.compile(r"(menej|viac) ako (\d+(?:\.\d+)?)", re.IGNORECASE)
_HT_RE = re.compile(r"1\.?\s*pol[cč]as", re.IGNORECASE)
_2H_RE = re.compile(r"2\.?\s*pol[cč]as", re.IGNORECASE)

HEADER_MAP: dict[str, str] = {
    "Zápas": "1x2",
    "1. polčas": "1x2_ht",
    "2. polčas": "1x2_2h",
    "Stávka bez remízy": "draw_no_bet",
    "1. polčas stávka bez remízy": "draw_no_bet_ht",
    "2. polčas stávka bez remízy": "draw_no_bet_2h",
    "Postup": "to_qualify",
    "1.polčas alebo zápas": "ht_or_ft",
}

_OU_FULL_HEADER_RE = re.compile(r"^(?:[^:]+ - [^:]+ )?počet gólov$", re.IGNORECASE)
_OU_HALF_HEADER_RE = re.compile(
    r"^(?:(?:[^:]+ - [^:]+): )?(1\. polčas|2\. polčas) počet gólov$",
    re.IGNORECASE,
)
_BTTS_HEADER_RE = re.compile(r"Obaj[ai]\s+daj[úu]\s+gól|Obaja\s+daj", re.IGNORECASE)


class NikeScraper(BaseScraper):
    BOOKMAKER = "nike"
    BASE_URL = "https://www.nike.sk"
    REQUEST_DELAY = 3.0

    def __init__(self, db_session, http_client=None):
        super().__init__(db_session, http_client)
        self._tournament_catalog: dict[str, dict[str, str]] | None = None

    def _nike_get(self, path: str) -> dict | list | None:
        url = f"{self.BASE_URL}{path}"
        retry_delays = (10, 30, 60)
        for attempt in range(len(retry_delays) + 1):
            self._rate_limit()
            self._last_request_time = time.time()
            page = Fetcher.get(url, impersonate="chrome", stealthy_headers=True)
            if page.status == 200 and page.body:
                return page.json()
            if page.status == 429:
                if attempt >= len(retry_delays):
                    raise NikeRateLimitError(f"[nike] Rate limited after retries: {url}")
                delay = retry_delays[attempt]
                logger.warning(
                    "[nike] %s returned 429; sleeping %ss before retry %s/%s",
                    url,
                    delay,
                    attempt + 1,
                    len(retry_delays),
                )
                time.sleep(delay)
                continue
            logger.warning(f"[nike] {url} returned {page.status}")
            return None
        return None

    def scrape_matches(self, league_external_id: str) -> list[RawMatch]:
        path = (
            "/api-gw/nikeone/v1/matches/special/top-tournaments"
            f"?tournamentId={league_external_id}"
        )
        data = self._nike_get(path)
        if not data or league_external_id not in data:
            return []
        tdata = data[league_external_id]
        return [
            rm
            for match_data in tdata.get("matches", [])
            for rm in [self._parse_match(match_data, league_external_id)]
            if rm
        ]

    def scrape_odds(self, match_external_id: str) -> list[RawOdds]:
        return []

    def scrape_odds_for_raw_match(self, raw_match: RawMatch) -> list[RawOdds]:
        tournament_id = raw_match.league_external_id
        fallback = TOURNAMENT_MAP.get(tournament_id, {})
        dynamic = self._get_tournament_catalog().get(tournament_id, {})
        box_id = dynamic.get("box_id", fallback.get("box_id", ""))
        if not box_id:
            return []

        detail = self._nike_get(
            "/api-gw/nikeone/v1/boxes/extended/sport-event-id"
            f"?boxId={box_id}&sportEventId={raw_match.external_id}"
        )
        if not detail:
            return []

        match_url = raw_match.url or f"{self.BASE_URL}/tipovanie/zapas/{raw_match.external_id}"
        best: dict[tuple[str, str], float] = {}
        for bet in detail.get("bets", []):
            for market, selection, rate in self._parse_bet(bet):
                key = (market, selection)
                if rate > best.get(key, 0.0):
                    best[key] = rate

        return [
            RawOdds(
                match_external_id=raw_match.external_id,
                market=market,
                selection=selection,
                odds=rate,
                url=match_url,
            )
            for (market, selection), rate in best.items()
        ]

    def run(self, league_ids: dict[str, str], normalizer=None) -> ScraperRunSummary:
        from bettingmaster.models.match import Match
        from bettingmaster.models.odds import OddsSnapshot
        from bettingmaster.scrapers.base import generate_match_id

        summary = ScraperRunSummary()
        tid_map: dict[str, dict[str, str]] = {}
        tournament_catalog = self._get_tournament_catalog()
        for league_id, tournament_id in league_ids.items():
            fallback = TOURNAMENT_MAP.get(
                tournament_id,
                {"league_id": league_id, "box_id": "", "slug": ""},
            )
            dynamic = tournament_catalog.get(tournament_id, {})
            tid_map[league_id] = {
                "tournament_id": tournament_id,
                "box_id": dynamic.get("box_id", fallback.get("box_id", "")),
                "slug": dynamic.get("slug", fallback.get("slug", "")),
            }

        all_tids = [meta["tournament_id"] for meta in tid_map.values()]
        params = "&".join(f"tournamentId={tournament_id}" for tournament_id in all_tids)
        data = self._nike_get(f"/api-gw/nikeone/v1/matches/special/top-tournaments?{params}")
        if not data:
            logger.error("[nike] Failed to fetch tournaments")
            summary.record_error("Failed to fetch tournaments")
            return summary

        summary.mark_progress()
        now = datetime.now(UTC).replace(tzinfo=None)

        for league_id, meta in tid_map.items():
            tournament_id = meta["tournament_id"]
            box_id = meta["box_id"]
            tournament_slug = meta["slug"]
            tdata = data.get(tournament_id, {})
            matches_raw = tdata.get("matches", [])
            logger.info(f"[nike] Tournament {tournament_id}: {len(matches_raw)} matches")

            for match_data in matches_raw:
                try:
                    odds_count = self._process_match(
                        match_data,
                        league_id,
                        box_id,
                        tournament_slug,
                        now,
                        generate_match_id,
                        Match,
                        OddsSnapshot,
                        normalizer,
                    )
                    if odds_count is None:
                        continue
                    summary.matches_found += 1
                    summary.odds_saved += odds_count
                    summary.mark_progress()
                except Exception as exc:
                    summary.record_error(exc)
                    home = match_data.get("home", {}).get("sk", "?")
                    away = match_data.get("away", {}).get("sk", "?")
                    logger.exception(f"[nike] Failed: {home} vs {away}")

        return summary

    def _get_tournament_catalog(self) -> dict[str, dict[str, str]]:
        if self._tournament_catalog is not None:
            return self._tournament_catalog

        data = self._nike_get("/api-gw/nikeone/v1/menu")
        catalog: dict[str, dict[str, str]] = {}
        if isinstance(data, dict):
            for item in self._walk_menu_items(data.get("items", [])):
                box_id = item.get("boxId")
                tournament_id = self._tournament_id_from_box_id(box_id)
                if tournament_id and box_id and tournament_id not in catalog:
                    catalog[tournament_id] = {
                        "box_id": box_id,
                        "slug": item.get("slug", ""),
                    }

        self._tournament_catalog = catalog
        return catalog

    def _walk_menu_items(self, items: list[dict]) -> list[dict]:
        result: list[dict] = []
        stack = list(items)
        while stack:
            item = stack.pop()
            result.append(item)
            stack.extend(item.get("items") or [])
        return result

    def _tournament_id_from_box_id(self, box_id: str | None) -> str | None:
        if not box_id:
            return None
        parts = box_id.split("-")
        if len(parts) < 4:
            return None
        tournament_id = parts[-1]
        return tournament_id if tournament_id.isdigit() else None

    def _process_match(
        self,
        match_data,
        league_id,
        box_id,
        tournament_slug,
        now,
        generate_match_id,
        Match,
        OddsSnapshot,
        normalizer,
    ) -> int | None:
        home_raw = match_data.get("home", {}).get("sk", "")
        away_raw = match_data.get("away", {}).get("sk", "")
        if not home_raw or not away_raw:
            return None

        home = (
            normalizer.normalize(home_raw, self.BOOKMAKER) or home_raw
            if normalizer
            else home_raw
        )
        away = (
            normalizer.normalize(away_raw, self.BOOKMAKER) or away_raw
            if normalizer
            else away_raw
        )

        start_time = self._parse_start_time(match_data.get("startTime", ""))
        if not is_match_in_active_scope(league_id, start_time):
            return None
        match_id = generate_match_id(
            league_id,
            home,
            away,
            start_time.strftime("%Y-%m-%d"),
        )
        external_id = str(match_data.get("id", ""))
        match_url = f"{self.BASE_URL}/tipovanie/zapas/{external_id}"

        match = self._db.get(Match, match_id)
        if match is None:
            match = Match(
                id=match_id,
                league_id=league_id,
                home_team=home,
                away_team=away,
                start_time=start_time,
                status="live" if match_data.get("isLive") else "prematch",
                external_ids={self.BOOKMAKER: external_id},
            )
            self._db.add(match)
        else:
            ext = dict(match.external_ids or {})
            ext[self.BOOKMAKER] = external_id
            match.external_ids = ext
            if match_data.get("isLive"):
                match.status = "live"
        self._db.flush()

        # Collect all parsed odds then deduplicate — multiple bet headers can
        # map to the same (market, selection); keep the best odds among them.
        best: dict[tuple[str, str], float] = {}
        if box_id:
            detail = self._nike_get(
                "/api-gw/nikeone/v1/boxes/extended/sport-event-id"
                f"?boxId={box_id}&sportEventId={external_id}"
            )
            if detail:
                for bet in detail.get("bets", []):
                    for market, selection, rate in self._parse_bet(bet):
                        key = (market, selection)
                        if rate > best.get(key, 0.0):
                            best[key] = rate

        odds_count = len(best)
        for (market, selection), rate in best.items():
            add_odds_snapshot(
                self._db,
                match_id=match_id,
                bookmaker=self.BOOKMAKER,
                market=market,
                selection=selection,
                odds=rate,
                url=match_url,
                scraped_at=now,
            )

        self._db.commit()
        logger.debug(f"[nike] {home} vs {away}: {odds_count} odds")
        return odds_count

    def _parse_bet(self, bet: dict) -> list[tuple[str, str, float]]:
        header = bet.get("header", "")
        normalized_header = _normalized_text(header)
        results = []

        cells = [
            cell
            for row in bet.get("selectionGrid", [])
            for cell in row
            if cell.get("type") in {"result", "selection"}
            and cell.get("odds") is not None
            and cell.get("enabled", True)
        ]
        if not cells:
            return results

        if normalized_header == "zápas":
            for cell in cells:
                tip = str(cell.get("tip", ""))
                rate = cell.get("odds")
                mapped = ZAPAS_TIP_MAP.get(tip)
                if mapped and rate and float(rate) > 1.0:
                    market, selection = mapped
                    results.append((market, selection, float(rate)))
            return results

        for raw_header, canonical_market in HEADER_MAP.items():
            if _normalized_text(raw_header) == normalized_header:
                return self._parse_result_cells(canonical_market, cells)

        if _BTTS_HEADER_RE.search(normalized_header):
            canonical = _btts_market(normalized_header)
            for cell in cells:
                name = _normalized_text(cell.get("name", ""))
                rate = cell.get("odds")
                selection = SK_YESNO.get(name)
                if selection and rate and float(rate) > 1.0:
                    results.append((canonical, selection, float(rate)))
            return results

        half_match = _OU_HALF_HEADER_RE.match(normalized_header)
        if _OU_FULL_HEADER_RE.match(normalized_header) or half_match:
            if half_match:
                half = "_ht" if half_match.group(1).startswith("1.") else "_2h"
            else:
                half = ""
            for cell in cells:
                name = _normalized_text(cell.get("name", ""))
                rate = cell.get("odds")
                if not rate or float(rate) <= 1.0:
                    continue
                match = _OU_NAME_RE.match(name)
                if match:
                    direction = "under" if match.group(1).lower() == "menej" else "over"
                    line = match.group(2)
                    results.append((f"over_under{half}_{line}", direction, float(rate)))
            return results

        if normalized_header == "handicap":
            for cell in cells:
                name = cell.get("name", "").strip()
                rate = cell.get("odds")
                if rate and float(rate) > 1.0 and name:
                    results.append(("handicap", name.lower().replace(" ", "_"), float(rate)))
            return results

        return results

    def _parse_result_cells(self, canonical: str, cells: list[dict]) -> list[tuple[str, str, float]]:
        results = []
        if "_ht" in canonical:
            half_suffix = "_ht"
        elif "_2h" in canonical:
            half_suffix = "_2h"
        else:
            half_suffix = ""

        if any(part in canonical for part in ("draw_no_bet", "to_qualify", "ht_or_ft")):
            for cell in cells:
                name = _normalized_text(cell.get("name", ""))
                rate = cell.get("odds")
                if not rate or float(rate) <= 1.0:
                    continue
                if name in SK_YESNO:
                    results.append((canonical, SK_YESNO[name], float(rate)))
                elif "remíza" in name or "remiza" in name:
                    results.append((canonical, "draw", float(rate)))
                elif name:
                    selection = "home" if not any(item[1] == "home" for item in results) else "away"
                    results.append((canonical, selection, float(rate)))
            return results

        for cell in cells:
            tip = str(cell.get("tip", ""))
            rate = cell.get("odds")
            if not rate or float(rate) <= 1.0:
                continue
            mapped = ZAPAS_TIP_MAP.get(tip)
            if mapped:
                base_market, selection = mapped
                results.append((base_market + half_suffix, selection, float(rate)))

        return results

    def _parse_match(self, match_data: dict, tournament_id: str) -> Optional[RawMatch]:
        external_id = str(match_data.get("id", ""))
        home = match_data.get("home", {}).get("sk", "")
        away = match_data.get("away", {}).get("sk", "")
        if not external_id or not home or not away:
            return None
        start_time = self._parse_start_time(match_data.get("startTime", ""))
        return RawMatch(
            external_id=external_id,
            home_team=home,
            away_team=away,
            league_external_id=tournament_id,
            start_time=start_time,
            status="live" if match_data.get("isLive") else "prematch",
            url=f"{self.BASE_URL}/tipovanie/zapas/{external_id}",
        )

    def _parse_start_time(self, raw: str) -> datetime:
        if not raw:
            return datetime.now(UTC).replace(tzinfo=None)
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed.astimezone(UTC).replace(tzinfo=None)
            return parsed
        except (ValueError, AttributeError):
            return datetime.now(UTC).replace(tzinfo=None)
