"""Tipsport.sk scraper using their REST API.

Known endpoints (from tipsport.cz open-source wrapper, same pattern for .sk):
  GET  /rest/offer/v4/sports                              — sports tree
  GET  /rest/offer/v1/competitions/top                    — top competitions
  POST /rest/offer/v2/offer                               — offer data
  GET  /rest/offer/v3/sports/COMPETITION/{id}/matches     — matches per competition
  GET  /rest/offer/v3/matches/{id}/communityStats         — match details
  GET  /rest/offer/v2/search?text=...&prematch=true       — search

Auth: JSESSIONID cookie from initial page load.
Note: Tipsport.sk is behind Cloudflare. Plain httpx gets 403.
      Use Playwright to load the page in a real browser, extract cookies,
      then use those cookies with httpx for API calls.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import httpx

from bettingmaster.config import DATA_DIR, settings
from bettingmaster.scrapers.base import BaseScraper, RawMatch, RawOdds

logger = logging.getLogger(__name__)

DEBUG_DIR = DATA_DIR / "debug"

# Map Tipsport market type names to our canonical market names.
# These are guesses based on common patterns — will be refined after --discover.
MARKET_MAP = {
    "RESULT": "1x2",
    "MATCH_RESULT": "1x2",
    "1X2": "1x2",
    "OVER_UNDER": "over_under_2.5",
    "TOTAL": "over_under_2.5",
    "BOTH_TEAMS_SCORE": "btts",
    "BOTH_TO_SCORE": "btts",
    "DOUBLE_CHANCE": "double_chance",
    "HANDICAP": "handicap",
    "ASIAN_HANDICAP": "asian_handicap",
    "DRAW_NO_BET": "draw_no_bet",
}

SELECTION_MAP = {
    "1": "home",
    "X": "draw",
    "0": "draw",
    "2": "away",
    "OVER": "over",
    "UNDER": "under",
    "YES": "yes",
    "NO": "no",
    "1X": "home_draw",
    "12": "home_away",
    "X2": "draw_away",
}


class TipsportAccessError(RuntimeError):
    """Raised when Tipsport blocks API access for the current environment."""


def _detect_access_issue(status_code: int, headers: dict[str, str], body: str) -> str | None:
    header_map = {key.lower(): value for key, value in headers.items()}
    body_lower = body.lower()

    if header_map.get("cf-mitigated") == "challenge" or "<title>ověření" in body_lower:
        return "Cloudflare challenge"
    if status_code == 401 and "session_does_not_exist" in body_lower:
        return "session bootstrap failed"
    if status_code == 403 and "<title>chyba" in body_lower:
        return "request blocked"
    return None


class TipsportScraper(BaseScraper):
    BOOKMAKER = "tipsport"
    BASE_URL = "https://www.tipsport.sk"
    REQUEST_DELAY = 1.5

    def __init__(self, db_session, http_client: httpx.Client | None = None):
        super().__init__(db_session, http_client)
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._use_playwright = False
        self._access_error: str | None = None
        self._init_browser()

    def _init_browser(self):
        """Initialize Playwright browser and load the page to pass Cloudflare.

        Cloudflare uses TLS fingerprinting, so cookies alone don't work with httpx.
        We keep the browser open and make all API calls from within it using
        page.evaluate(fetch(...)).
        """
        try:
            try:
                from patchright.sync_api import sync_playwright
                _is_patchright = True
            except ImportError:
                from playwright.sync_api import sync_playwright
                _is_patchright = False

            import tempfile

            self._playwright = sync_playwright().start()
            user_data_dir = tempfile.mkdtemp(prefix="tipsport-profile-")
            context_kwargs: dict = {
                "user_data_dir": user_data_dir,
                "channel": settings.tipsport_browser_channel or "chrome",
                "headless": settings.tipsport_headless,
                "locale": "sk-SK",
                "no_viewport": True,
            }
            if settings.tipsport_proxy_url:
                context_kwargs["proxy"] = {"server": settings.tipsport_proxy_url}

            self._context = self._playwright.chromium.launch_persistent_context(
                **context_kwargs
            )
            self._browser = None
            self._page = (
                self._context.pages[0]
                if self._context.pages
                else self._context.new_page()
            )

            logger.info("[tipsport] Loading page via Playwright...")
            self._page.goto(self.BASE_URL, wait_until="networkidle", timeout=30000)
            self._page.wait_for_timeout(2000)

            cookies = self._context.cookies()
            logger.info(
                f"[tipsport] Browser ready. {len(cookies)} cookies: "
                f"{[c['name'] for c in cookies]}"
            )
            self._use_playwright = True
            self._validate_access()

        except Exception:
            logger.exception("[tipsport] Playwright init failed, falling back to httpx")
            self._use_playwright = False

    def _validate_access(self):
        try:
            self._api_get(
                "/rest/offer/v6/sports",
                params={
                    "fromResults": "false",
                    "withLive": "true",
                    "mySelectionWithLiveMatches": "true",
                },
            )
            self._access_error = None
        except TipsportAccessError as exc:
            self._access_error = str(exc)
            logger.warning("[tipsport] %s", self._access_error)

    def _blocked_message(self, reason: str) -> str:
        parts = [f"Tipsport access blocked: {reason}."]
        if settings.tipsport_proxy_url:
            parts.append("Current Tipsport proxy was rejected.")
        else:
            parts.append(
                "Set BM_TIPSPORT_PROXY_URL to a clean residential or local SK/CZ proxy."
            )
        if not settings.tipsport_browser_channel:
            parts.append(
                "If scraping from a desktop browser, BM_TIPSPORT_BROWSER_CHANNEL=chrome may help."
            )
        parts.append("Hetzner and other datacenter IPs are often blocked by Tipsport.")
        return " ".join(parts)

    def _ensure_access(self) -> bool:
        if self._access_error:
            logger.warning("[tipsport] %s", self._access_error)
            return False
        return True

    def _http_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        import time as _time

        self._rate_limit()
        self._last_request_time = _time.time()
        response = self._client.request(method, url, **kwargs)
        body = response.text
        reason = _detect_access_issue(response.status_code, dict(response.headers), body)
        if reason:
            raise TipsportAccessError(self._blocked_message(reason))
        response.raise_for_status()
        return response

    def _api_get(self, path: str, **kwargs) -> dict:
        url = f"{self.BASE_URL}{path}"
        params = kwargs.get("params", {})
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{qs}"

        if self._use_playwright and self._page:
            return self._playwright_fetch(url)

        resp = self._http_request("GET", url, **kwargs)
        return resp.json()

    def _api_post(self, path: str, json_data: dict, **kwargs) -> dict:
        url = f"{self.BASE_URL}{path}"

        if self._use_playwright and self._page:
            return self._playwright_fetch(url, method="POST", body=json_data)

        resp = self._http_request("POST", url, json=json_data, **kwargs)
        return resp.json()

    def _playwright_fetch(self, url: str, method: str = "GET", body: dict | None = None) -> dict:
        """Make an API call from within the Playwright browser context.

        This uses the browser's own TLS stack and cookies, bypassing Cloudflare.
        """
        import time as _time

        self._rate_limit()
        self._last_request_time = _time.time()

        if method == "GET":
            js = f"""
                async () => {{
                    const resp = await fetch("{url}", {{
                        method: "GET",
                        headers: {{
                            "Accept": "application/json",
                            "X-Requested-With": "XMLHttpRequest"
                        }},
                        credentials: "include"
                    }});
                    return {{
                        status: resp.status,
                        headers: Object.fromEntries(resp.headers.entries()),
                        text: await resp.text()
                    }};
                }}
            """
        else:
            body_json = json.dumps(body) if body else "{}"
            js = f"""
                async () => {{
                    const resp = await fetch("{url}", {{
                        method: "POST",
                        headers: {{
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                            "X-Requested-With": "XMLHttpRequest"
                        }},
                        credentials: "include",
                        body: JSON.stringify({body_json})
                    }});
                    return {{
                        status: resp.status,
                        headers: Object.fromEntries(resp.headers.entries()),
                        text: await resp.text()
                    }};
                }}
            """

        result = self._page.evaluate(js)
        reason = _detect_access_issue(result["status"], result["headers"], result["text"])
        if reason:
            raise TipsportAccessError(self._blocked_message(reason))
        if result["status"] >= 400:
            raise httpx.HTTPStatusError(
                f"Tipsport returned HTTP {result['status']}",
                request=httpx.Request(method, url),
                response=httpx.Response(
                    result["status"],
                    request=httpx.Request(method, url),
                    content=result["text"].encode("utf-8"),
                ),
            )

        logger.debug(f"[tipsport] Playwright fetch {method} {url} -> OK")
        return json.loads(result["text"])

    def _dump_debug(self, name: str, data):
        """Dump raw JSON response to debug directory."""
        if not settings.debug_dump:
            return
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = DEBUG_DIR / f"tipsport_{name}_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"[tipsport] Debug dump: {path}")

    # --- Discovery methods ---

    def discover_sports(self) -> dict:
        """Fetch and return the full sports tree."""
        data = self._api_get("/rest/offer/v4/sports")
        self._dump_debug("sports", data)
        return data

    def discover_top_competitions(self) -> dict:
        data = self._api_get("/rest/offer/v1/competitions/top")
        self._dump_debug("top_competitions", data)
        return data

    def discover_competition_matches(self, competition_id: str) -> dict:
        data = self._api_get(
            f"/rest/offer/v3/sports/COMPETITION/{competition_id}/matches"
        )
        self._dump_debug(f"matches_{competition_id}", data)
        return data

    def discover_offer(self, competition_id: int) -> dict:
        payload = {
            "competitionId": competition_id,
            "fromResults": False,
            "fromFilter": False,
            "limit": 100,
        }
        data = self._api_post("/rest/offer/v2/offer", payload)
        self._dump_debug(f"offer_{competition_id}", data)
        return data

    def search(self, text: str) -> dict:
        data = self._api_get(
            "/rest/offer/v2/search",
            params={"text": text, "prematch": "true", "results": "false"},
        )
        self._dump_debug(f"search_{text}", data)
        return data

    # --- Scraping implementation ---

    def scrape_matches(self, league_external_id: str) -> list[RawMatch]:
        """Scrape matches for a competition/league by its Tipsport ID."""
        if not self._ensure_access():
            return []
        try:
            data = self._api_get(
                f"/rest/offer/v3/sports/COMPETITION/{league_external_id}/matches"
            )
            self._dump_debug(f"matches_{league_external_id}", data)
        except TipsportAccessError as exc:
            self._access_error = str(exc)
            logger.warning("[tipsport] %s", self._access_error)
            return []
        except Exception as e:
            logger.error(
                f"[tipsport] Failed to fetch matches for {league_external_id}: {e}"
            )
            return []

        matches = []
        # The response structure needs verification via --discover.
        # Common patterns: data is a list, or data["matches"], or data["eventTables"]
        match_list = self._extract_match_list(data)

        for item in match_list:
            try:
                rm = self._parse_match(item, league_external_id)
                if rm:
                    matches.append(rm)
            except Exception:
                logger.exception(f"[tipsport] Failed to parse match item: {item}")

        return matches

    def _extract_match_list(self, data) -> list:
        """Extract the list of matches from API response.

        The exact structure depends on the API version. This tries common patterns.
        """
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ["matches", "eventTables", "events", "data", "items"]:
                if key in data:
                    val = data[key]
                    return val if isinstance(val, list) else [val]
        return []

    def _parse_match(self, item: dict, league_ext_id: str) -> Optional[RawMatch]:
        """Parse a single match from the API response."""
        # Try common field names — will be refined after discovery
        ext_id = str(
            item.get("id") or item.get("matchId") or item.get("eventId", "")
        )
        if not ext_id:
            return None

        home = (
            item.get("homeName")
            or item.get("home", {}).get("name", "")
            or item.get("name", "").split(" - ")[0]
            if " - " in item.get("name", "")
            else ""
        )
        away = (
            item.get("awayName")
            or item.get("away", {}).get("name", "")
            or item.get("name", "").split(" - ")[-1]
            if " - " in item.get("name", "")
            else ""
        )

        if not home or not away:
            # Try parsing from a combined name field
            name = item.get("name", "") or item.get("title", "")
            for sep in [" - ", " vs ", " – ", " — "]:
                if sep in name:
                    parts = name.split(sep, 1)
                    home, away = parts[0].strip(), parts[1].strip()
                    break

        if not home or not away:
            logger.debug(f"[tipsport] Could not parse teams from: {item}")
            return None

        # Parse start time
        start_raw = item.get("startTime") or item.get("date") or item.get("dateClosed")
        start_time = self._parse_datetime(start_raw) if start_raw else datetime.utcnow()

        status = "prematch"
        if item.get("live") or item.get("isLive"):
            status = "live"

        return RawMatch(
            external_id=ext_id,
            home_team=home,
            away_team=away,
            league_external_id=league_ext_id,
            start_time=start_time,
            status=status,
        )

    def _parse_datetime(self, raw) -> datetime:
        """Parse datetime from various formats."""
        if isinstance(raw, (int, float)):
            # Unix timestamp in milliseconds
            if raw > 1e12:
                return datetime.utcfromtimestamp(raw / 1000)
            return datetime.utcfromtimestamp(raw)
        if isinstance(raw, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                "%d.%m.%Y %H:%M",
            ]:
                try:
                    return datetime.strptime(raw.rstrip("Z"), fmt)
                except ValueError:
                    continue
        logger.warning(f"[tipsport] Could not parse datetime: {raw}")
        return datetime.utcnow()

    def scrape_odds(self, match_external_id: str) -> list[RawOdds]:
        """Scrape odds for a specific match.

        Tries the offer endpoint first. If odds are already inline
        with the matches response, the caller should override this.
        """
        if not self._ensure_access():
            return []
        # For now, try to get odds from the match detail / community stats
        try:
            data = self._api_get(
                f"/rest/offer/v3/matches/{match_external_id}/communityStats"
            )
            self._dump_debug(f"odds_{match_external_id}", data)
        except TipsportAccessError as exc:
            self._access_error = str(exc)
            logger.warning("[tipsport] %s", self._access_error)
            return []
        except Exception:
            logger.debug(
                f"[tipsport] communityStats failed for {match_external_id}, "
                "trying offer endpoint"
            )
            data = {}

        odds = self._extract_odds(data, match_external_id)
        return odds

    def _extract_odds(self, data: dict, match_ext_id: str) -> list[RawOdds]:
        """Extract odds from API response. Tries common structures."""
        odds = []

        # Pattern 1: odds in "boxes" -> each box has "opportunities"
        boxes = data.get("boxes") or data.get("markets") or data.get("betOffers") or []
        for box in boxes:
            market_name = str(
                box.get("name") or box.get("type") or box.get("marketType", "")
            ).upper()
            canonical_market = MARKET_MAP.get(market_name, market_name.lower())

            opportunities = (
                box.get("opportunities")
                or box.get("outcomes")
                or box.get("selections")
                or []
            )
            for opp in opportunities:
                selection_raw = str(
                    opp.get("name") or opp.get("label") or opp.get("type", "")
                ).upper().strip()
                canonical_selection = SELECTION_MAP.get(
                    selection_raw, selection_raw.lower()
                )

                odds_val = opp.get("odd") or opp.get("odds") or opp.get("value")
                if odds_val is not None:
                    try:
                        odds_float = float(odds_val)
                        if 1.0 < odds_float < 1000:  # sanity check
                            odds.append(
                                RawOdds(
                                    match_external_id=match_ext_id,
                                    market=canonical_market,
                                    selection=canonical_selection,
                                    odds=odds_float,
                                )
                            )
                    except (ValueError, TypeError):
                        pass

        # Pattern 2: flat odds in the data dict itself (1x2)
        for key, selection in [("odd1", "home"), ("oddX", "draw"), ("odd2", "away"),
                                ("odds1", "home"), ("oddsX", "draw"), ("odds2", "away")]:
            val = data.get(key)
            if val is not None:
                try:
                    odds_float = float(val)
                    if 1.0 < odds_float < 1000:
                        odds.append(
                            RawOdds(
                                match_external_id=match_ext_id,
                                market="1x2",
                                selection=selection,
                                odds=odds_float,
                            )
                        )
                except (ValueError, TypeError):
                    pass

        return odds

    def scrape_matches_with_inline_odds(
        self, league_external_id: str
    ) -> tuple[list[RawMatch], dict[str, list[RawOdds]]]:
        """Scrape matches and extract inline odds in one pass.

        Returns (matches, {match_ext_id: [RawOdds]}).
        Useful if the matches endpoint already includes odds.
        """
        if not self._ensure_access():
            return [], {}
        try:
            data = self._api_get(
                f"/rest/offer/v3/sports/COMPETITION/{league_external_id}/matches"
            )
            self._dump_debug(f"matches_full_{league_external_id}", data)
        except TipsportAccessError as exc:
            self._access_error = str(exc)
            logger.warning("[tipsport] %s", self._access_error)
            return [], {}
        except Exception as e:
            logger.error(f"[tipsport] Failed: {e}")
            return [], {}

        matches = []
        odds_map: dict[str, list[RawOdds]] = {}
        match_list = self._extract_match_list(data)

        for item in match_list:
            rm = self._parse_match(item, league_external_id)
            if rm:
                matches.append(rm)
                # Try to extract inline odds
                inline_odds = self._extract_odds(item, rm.external_id)
                if inline_odds:
                    odds_map[rm.external_id] = inline_odds

        return matches, odds_map

    def close(self):
        """Clean up Playwright browser resources."""
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
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
