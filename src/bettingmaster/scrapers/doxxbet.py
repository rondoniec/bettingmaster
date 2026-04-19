"""DOXXbet.sk scraper using Playwright to extract AngularJS scope data.

DOXXbet loads all offer data via SignalR WebSocket into an AngularJS scope.
There is no public REST API. The scraper uses two pages:

  1. Offer listing page — fast, gets all match IDs + URLs for a league
  2. Match detail page  — per-match, populates eventChanceTypes with full markets

Data structure on detail page (eventChanceTypes):
  "Výsledok"            → 6 selections: {0:home, 1:draw, 2:away, 3:home_draw, 4:draw_away, 5:home_away}
  "Oba tímy dajú gól"   → 2 selections: {0:yes, 1:no}
  "Počet gólov X.X"     → 2 selections: {0:over, 1:under}
  "Výsledok bez remízy" → 2 selections: {0:home, 1:away}
  "Kto postúpi ..."     → 2 selections: {0:home, 1:away}
  "1. Polčas - X"       → same patterns, half-time variants
  "2. Polčas - X"       → same patterns, 2nd-half variants

Known sport IDs: 54 = Football
Known league IDs: 919 = Niké Liga, 607245 = UCL
"""

import logging
import re
import unicodedata
from datetime import UTC, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from bettingmaster.scrapers.base import BaseScraper, RawMatch, RawOdds
from bettingmaster.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Selection key mappings  (all use numeric string keys on detail page)
# ---------------------------------------------------------------------------

# 6-way result market: 0-2 = 1x2, 3-5 = double chance
SEL_RESULT_6 = {
    "0": ("1x2",           "home"),
    "1": ("1x2",           "draw"),
    "2": ("1x2",           "away"),
    "3": ("double_chance", "home_draw"),
    "4": ("double_chance", "draw_away"),
    "5": ("double_chance", "home_away"),
}

# 2-way result (DNB / to qualify)
SEL_RESULT_2 = {"0": "home", "1": "away"}

# BTTS / yes-no markets
SEL_BTTS = {"0": "yes", "1": "no"}

# Over / under markets
SEL_OU = {"0": "over", "1": "under"}


def _normalized_market_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    asciiish = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    asciiish = re.sub(r"\s+", " ", asciiish).strip()
    return asciiish

# ---------------------------------------------------------------------------
# Market name → (canonical_base, sel_map_key)
# canonical_base may be suffixed with "_ht" / "_2h" automatically for halves
# ---------------------------------------------------------------------------

MARKET_MAP: dict[str, tuple[str, dict]] = {
    "Výsledok":                        ("result_6way",   SEL_RESULT_6),
    "Oba tímy dajú gól":               ("btts",          SEL_BTTS),
    "Výsledok bez remízy":             ("draw_no_bet",   SEL_RESULT_2),
    "Výsledok bez Real Madrid":        ("draw_no_bet",   SEL_RESULT_2),
    "Výsledok bez Bayern Munchen":     ("draw_no_bet",   SEL_RESULT_2),
    "Kto postúpi / Lepší z dvojice":   ("to_qualify",    SEL_RESULT_2),
    # Half-time
    "1. Polčas - Výsledok":            ("result_6way_ht", SEL_RESULT_6),
    "1. Polčas - Oba tímy dajú gól":   ("btts_ht",       SEL_BTTS),
    # 2nd half
    "2. Polčas - Výsledok":            ("result_6way_2h", SEL_RESULT_6),
    "2. Polčas - Oba tímy dajú gól":   ("btts_2h",        SEL_BTTS),
}

# Regex for over/under markets  e.g. "Počet gólov 2.5", "1. Polčas - Počet gólov 1.5"
_OU_RE = re.compile(
    r"^(?:(1\. Polčas|2\. Polčas) - )?Počet gólov (\d+(?:\.\d+)?)$"
)

MARKET_MAP_NORMALIZED = {
    _normalized_market_name(name): value
    for name, value in MARKET_MAP.items()
}
MARKET_MAP_NORMALIZED.update({
    _normalized_market_name("Výsledok"): ("result_6way", SEL_RESULT_6),
    _normalized_market_name("Oba tímy dajú gól"): ("btts", SEL_BTTS),
    _normalized_market_name("Výsledok bez remízy"): ("draw_no_bet", SEL_RESULT_2),
    _normalized_market_name("Kto postúpi / Lepší z dvojice"): ("to_qualify", SEL_RESULT_2),
    _normalized_market_name("1. Polčas - Výsledok"): ("result_6way_ht", SEL_RESULT_6),
    _normalized_market_name("1. Polčas - Oba tímy dajú gól"): ("btts_ht", SEL_BTTS),
    _normalized_market_name("2. Polčas - Výsledok"): ("result_6way_2h", SEL_RESULT_6),
    _normalized_market_name("2. Polčas - Oba tímy dajú gól"): ("btts_2h", SEL_BTTS),
})

_OU_NORMALIZED_RE = re.compile(
    r"^(?:(1\. polcas|2\. polcas) - )?pocet golov (\d+(?:\.\d+)?)$"
)
MARKET_MAP_NORMALIZED.update({
    _normalized_market_name("V\u00fdsledok"): ("result_6way", SEL_RESULT_6),
    _normalized_market_name("Oba t\u00edmy daj\u00fa g\u00f3l"): ("btts", SEL_BTTS),
    _normalized_market_name("V\u00fdsledok bez rem\u00edzy"): ("draw_no_bet", SEL_RESULT_2),
    _normalized_market_name("Kto post\u00fapi / Lep\u0161\u00ed z dvojice"): ("to_qualify", SEL_RESULT_2),
    _normalized_market_name("1. Pol\u010das - V\u00fdsledok"): ("result_6way_ht", SEL_RESULT_6),
    _normalized_market_name("1. Pol\u010das - Oba t\u00edmy daj\u00fa g\u00f3l"): ("btts_ht", SEL_BTTS),
    _normalized_market_name("2. Pol\u010das - V\u00fdsledok"): ("result_6way_2h", SEL_RESULT_6),
    _normalized_market_name("2. Pol\u010das - Oba t\u00edmy daj\u00fa g\u00f3l"): ("btts_2h", SEL_BTTS),
})

# ---------------------------------------------------------------------------
# League map
# ---------------------------------------------------------------------------

LEAGUE_MAP = {
    "919":    "sk-fortuna-liga",
    "607245": "ucl",
}
LEAGUE_TO_DOXXBET = {v: k for k, v in LEAGUE_MAP.items()}

LISTING_PATHS = {
    "919": "/sk/sportove-tipovanie-online/kurzy/futbal/slovensko/1-liga",
    "607245": "/sk/sportove-tipovanie-online/kurzy/futbal/kluby/liga-majstrov-uefa",
}

# ---------------------------------------------------------------------------
# JavaScript snippets
# ---------------------------------------------------------------------------

# Step 1: listing page — collect events with their detail URLs
EXTRACT_EVENTS_JS = """
() => {
    const offerEl = document.querySelector('[ng-controller="OfferController"]');
    if (!offerEl || !window.angular) return null;
    const scope = angular.element(offerEl).scope();
    if (!scope || !scope.events) return null;
    const result = [];
    for (const key of Object.keys(scope.events)) {
        const e = scope.events[key];
        if (!e || !e.sportID) continue;
        result.push({
            id:       e.ID,
            name:     e.name || '',
            teams:    e.teams || [],
            sportID:  e.sportID,
            leagueID: e.leagueID,
            date:     e.dateStr || '',
            datetime: e.datetime || 0,
            isLive:   !!e.isLive,
            url:      e.URL || '',
        });
    }
    return result;
}
"""

# Step 2: detail page — extract all eventChanceTypes for a specific event ID
EXTRACT_DETAIL_JS = """
(eventId) => {
    const el = document.querySelector('[ng-controller="OfferController"]');
    if (!el || !window.angular) return null;
    const scope = angular.element(el).scope();
    if (!scope || !scope.events) return null;

    // Find event by numeric ID
    let e = null;
    for (const key of Object.keys(scope.events)) {
        const ev = scope.events[key];
        if (ev && ev.ID === eventId) { e = ev; break; }
    }
    if (!e) return null;

    const result = {};
    const ect = e.eventChanceTypes;
    if (!ect) return result;
    const types = Array.isArray(ect) ? ect : Object.values(ect);
    for (const ct of types) {
        if (!ct || !ct.name) continue;
        const odds = {};
        if (ct.odds) {
            for (const [sel, o] of Object.entries(ct.odds)) {
                if (o && o.rate) odds[sel] = o.rate;
            }
        }
        if (Object.keys(odds).length > 0) result[ct.name] = odds;
    }
    return result;
}
"""


class DoxxbetScraper(BaseScraper):
    BOOKMAKER = "doxxbet"
    BASE_URL = "https://www.doxxbet.sk"
    REQUEST_DELAY = 2.0

    def __init__(self, db_session, http_client=None):
        super().__init__(db_session, http_client)
        self._playwright = None
        self._browser = None
        self._page = None

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    def _init_browser(self) -> bool:
        if self._page:
            return True
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            context = self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="sk-SK",
            )
            self._page = context.new_page()
            return True
        except Exception:
            logger.exception("[doxxbet] Playwright init failed")
            return False

    def close(self):
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        super().close()

    # ------------------------------------------------------------------
    # Page loading helpers
    # ------------------------------------------------------------------

    def _load_listing_page(self, listing_path: str | None = None) -> list[dict] | None:
        """Load a listing page and return all event stubs."""
        if not self._init_browser():
            return None
        try:
            if listing_path:
                url = f"{self.BASE_URL}{listing_path}"
            else:
                url = f"{self.BASE_URL}/sk/sportove-tipovanie-online/kurzy?date=WEEK"
            logger.info(f"[doxxbet] Loading listing page: {url}")
            self._page.goto(url, wait_until="networkidle", timeout=30000)
            self._page.wait_for_timeout(4000)
            try:
                self._page.wait_for_function(
                    """() => {
                        const el = document.querySelector('[ng-controller="OfferController"]');
                        if (!el || !window.angular) return false;
                        const scope = angular.element(el).scope();
                        return scope && scope.events && Object.keys(scope.events).length > 50;
                    }""",
                    timeout=20000,
                )
            except Exception:
                pass  # proceed with whatever loaded
            events = self._page.evaluate(EXTRACT_EVENTS_JS)
            logger.info(f"[doxxbet] Listing: {len(events or [])} events")
            return events
        except Exception:
            logger.exception("[doxxbet] Failed to load listing page")
            return None

    def _load_match_detail(self, event_id: int, event_url: str) -> dict | None:
        """Navigate to the match detail page and extract all eventChanceTypes."""
        if not self._page:
            return None
        try:
            full_url = f"{self.BASE_URL}/{event_url.lstrip('/')}"
            logger.debug(f"[doxxbet] Loading detail: {full_url}")
            self._page.goto(full_url, wait_until="networkidle", timeout=30000)
            self._page.wait_for_timeout(3000)

            # Wait until eventChanceTypes is populated for this event
            try:
                self._page.wait_for_function(
                    f"""() => {{
                        const el = document.querySelector('[ng-controller="OfferController"]');
                        if (!el || !window.angular) return false;
                        const scope = angular.element(el).scope();
                        if (!scope || !scope.events) return false;
                        for (const key of Object.keys(scope.events)) {{
                            const e = scope.events[key];
                            if (e && e.ID === {event_id} && e.eventChanceTypes) {{
                                const types = Array.isArray(e.eventChanceTypes)
                                    ? e.eventChanceTypes
                                    : Object.values(e.eventChanceTypes);
                                return types.filter(t => t && t.name).length > 5;
                            }}
                        }}
                        return false;
                    }}""",
                    timeout=20000,
                )
            except Exception:
                logger.warning(f"[doxxbet] Timeout waiting for detail data (event {event_id})")

            return self._page.evaluate(EXTRACT_DETAIL_JS, event_id)
        except Exception:
            logger.exception(f"[doxxbet] Failed to load detail for event {event_id}")
            return None

    # ------------------------------------------------------------------
    # Odds parsing
    # ------------------------------------------------------------------

    def _parse_chance_types(self, chance_types: dict) -> list[tuple[str, str, float]]:
        """Parse eventChanceTypes dict → list of (market, selection, odds) tuples."""
        results = []

        for market_name, odds_dict in chance_types.items():
            normalized_market_name = _normalized_market_name(market_name)
            if " bez " in normalized_market_name and "rem" not in normalized_market_name:
                continue

            # Check exact market map first
            mapped_market = MARKET_MAP_NORMALIZED.get(normalized_market_name)
            if mapped_market:
                canonical, sel_map = mapped_market
                for sel_key, rate in odds_dict.items():
                    if rate is None or rate <= 1.0:
                        continue
                    if canonical == "result_6way":
                        mapped = SEL_RESULT_6.get(sel_key)
                        if mapped:
                            market_out, sel_out = mapped
                            results.append((market_out, sel_out, float(rate)))
                    elif canonical == "result_6way_ht":
                        mapped = SEL_RESULT_6.get(sel_key)
                        if mapped:
                            market_out, sel_out = mapped
                            results.append((market_out + "_ht", sel_out, float(rate)))
                    elif canonical == "result_6way_2h":
                        mapped = SEL_RESULT_6.get(sel_key)
                        if mapped:
                            market_out, sel_out = mapped
                            results.append((market_out + "_2h", sel_out, float(rate)))
                    else:
                        sel_out = sel_map.get(sel_key)
                        if sel_out:
                            results.append((canonical, sel_out, float(rate)))
                continue

            # Over/under regex
            m = _OU_RE.match(market_name)
            if m:
                half_prefix, line = m.group(1), m.group(2)
                if half_prefix == "1. Polčas":
                    canonical = f"over_under_ht_{line}"
                elif half_prefix == "2. Polčas":
                    canonical = f"over_under_2h_{line}"
                else:
                    canonical = f"over_under_{line}"
                for sel_key, rate in odds_dict.items():
                    if rate is None or rate <= 1.0:
                        continue
                    sel_out = SEL_OU.get(sel_key)
                    if sel_out:
                        results.append((canonical, sel_out, float(rate)))

        return results

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def scrape_matches(self, league_external_id: str) -> list[RawMatch]:
        listing_path = LISTING_PATHS.get(str(league_external_id))
        events = self._load_listing_page(listing_path)
        if not events:
            return []
        league_id = int(league_external_id)
        return [
            rm for e in events
            if e.get("sportID") == 54
            and e.get("leagueID") == league_id
            and not e.get("isLive")
            for rm in [self._parse_event(e)] if rm
        ]

    def scrape_odds(self, match_external_id: str) -> list[RawOdds]:
        return []  # handled inline in run()

    def run(self, league_ids: dict[str, str], normalizer=None):
        from bettingmaster.scrapers.base import generate_match_id
        from bettingmaster.models.match import Match
        from bettingmaster.models.odds import OddsSnapshot

        league_map = {int(ext_id): our_id for our_id, ext_id in league_ids.items()}
        relevant: list[dict] = []

        for ext_id in league_ids.values():
            listing_path = LISTING_PATHS.get(str(ext_id))
            events = self._load_listing_page(listing_path)
            if not events:
                logger.warning(f"[doxxbet] Failed to load listing page for league {ext_id}")
                continue
            relevant.extend(
                e for e in events
                if e.get("sportID") == 54
                and e.get("leagueID") == int(ext_id)
                and not e.get("isLive")
            )

        now = datetime.now(UTC).replace(tzinfo=None)
        logger.info(f"[doxxbet] {len(relevant)} relevant events across {len(league_ids)} leagues")

        # Step 2: for each event, navigate to detail page for full markets
        for event in relevant:
            event_id = event.get("id")
            event_url = event.get("url", "")
            our_league = league_map[event.get("leagueID")]

            try:
                # Parse teams
                teams = event.get("teams", [])
                if len(teams) < 2:
                    name = event.get("name", "")
                    if " vs. " in name:
                        teams = [t.strip() for t in name.split(" vs. ", 1)]
                if len(teams) < 2:
                    continue

                home_raw, away_raw = teams[0], teams[1]
                home = normalizer.normalize(home_raw, self.BOOKMAKER) or home_raw if normalizer else home_raw
                away = normalizer.normalize(away_raw, self.BOOKMAKER) or away_raw if normalizer else away_raw

                start_time = self._parse_date(event.get("date", ""), event.get("datetime"))
                match_id = generate_match_id(our_league, home, away, start_time.strftime("%Y-%m-%d"))
                ext_id = str(event_id)

                # Upsert match record first
                match_url = f"{self.BASE_URL}/{event_url.lstrip('/')}" if event_url else f"{self.BASE_URL}/sk/sportove-tipovanie-online/kurzy"
                match = self._db.get(Match, match_id)
                if match is None:
                    match = Match(
                        id=match_id,
                        league_id=our_league,
                        home_team=home,
                        away_team=away,
                        start_time=start_time,
                        status="prematch",
                        external_ids={self.BOOKMAKER: ext_id},
                    )
                    self._db.add(match)
                else:
                    ext = dict(match.external_ids or {})
                    ext[self.BOOKMAKER] = ext_id
                    match.external_ids = ext
                self._db.flush()

                # Load detail page for full odds
                if not event_url:
                    logger.warning(f"[doxxbet] No URL for event {event_id}, skipping detail")
                    continue

                chance_types = self._load_match_detail(event_id, event_url)
                if not chance_types:
                    logger.warning(f"[doxxbet] No chance types for {home} vs {away}")
                    continue

                parsed = self._parse_chance_types(chance_types)
                odds_count = 0
                for market, selection, rate in parsed:
                    snap = OddsSnapshot(
                        match_id=match_id,
                        bookmaker=self.BOOKMAKER,
                        market=market,
                        selection=selection,
                        odds=rate,
                        url=match_url,
                        scraped_at=now,
                    )
                    self._db.add(snap)
                    odds_count += 1

                self._db.commit()
                logger.info(f"[doxxbet] {home} vs {away}: {odds_count} odds saved")

            except Exception:
                logger.exception(f"[doxxbet] Failed: {event.get('name', '?')}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_event(self, event: dict) -> Optional[RawMatch]:
        teams = event.get("teams", [])
        if len(teams) < 2:
            name = event.get("name", "")
            if " vs. " in name:
                teams = [t.strip() for t in name.split(" vs. ", 1)]
        if len(teams) < 2:
            return None
        ext_id = str(event.get("id", ""))
        start_time = self._parse_date(event.get("date", ""), event.get("datetime"))
        event_url = event.get("url", "")
        url = f"{self.BASE_URL}/{event_url.lstrip('/')}" if event_url else f"{self.BASE_URL}/sk/sportove-tipovanie-online/kurzy"
        return RawMatch(
            external_id=ext_id,
            home_team=teams[0],
            away_team=teams[1],
            league_external_id=str(event.get("leagueID", "")),
            start_time=start_time,
            status="prematch",
            url=url,
        )

    def _parse_date(self, date_str: str, timestamp=None) -> datetime:
        timezone = ZoneInfo(settings.timezone)

        if timestamp and isinstance(timestamp, (int, float)) and timestamp > 1e9:
            if timestamp > 1e12:
                return datetime.fromtimestamp(timestamp / 1000, UTC).replace(tzinfo=None)
            return datetime.fromtimestamp(timestamp, UTC).replace(tzinfo=None)
        if isinstance(timestamp, dict) and date_str:
            try:
                date_part = date_str.split(" - ")[0].strip()
                time_part = str(timestamp.get("time", "")).strip()
                local_dt = datetime.strptime(f"{date_part} {time_part}", "%d.%m.%Y %H:%M").replace(
                    tzinfo=timezone
                )
                return local_dt.astimezone(UTC).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass
        if date_str:
            try:
                date_part = date_str.split(" - ")[0].strip()
                local_dt = datetime.strptime(date_part, "%d.%m.%Y").replace(tzinfo=timezone)
                return local_dt.astimezone(UTC).replace(tzinfo=None)
            except (ValueError, IndexError):
                pass
        return datetime.now(UTC).replace(tzinfo=None)
