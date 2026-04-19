"""Tipos.sk (eTipos) scraper using tipkurz.etipos.sk JSON/protobuf API.

Discovery notes (from explore_tipos*.py):
- Base URL: https://tipkurz.etipos.sk
- API service: /WebServices/Api/SportsBettingService.svc/<Method>
- All requests are POST with Content-Type: application/json
- Responses have shape: {"ReturnValue": <base64-encoded protobuf>, ...}
- Session token obtained from GetLiveInitData (SessionService endpoint)
- Key endpoints:
    GetLiveInitData    – returns {"Token": "..."} used in all subsequent calls
    GetWebTopBets      – top offers (LanguageID, Token, TopOfferType, ...)
    GetWebStandardEventExt – single match detail with odds (EventID, LanguageID, Token)
    GetWebStandardCategories – category tree (sports/leagues)
- The page is NOT behind Cloudflare but does require cookies/session.
  Playwright is used to load the page once, grab the token, then make API
  calls directly from within the browser context (avoiding CORS and auth issues).
- LanguageID 17 = Slovak
"""

import base64
import json
import logging
import struct
from datetime import datetime
from typing import Optional

from bettingmaster.config import DATA_DIR, settings
from bettingmaster.scrapers.base import BaseScraper, RawMatch, RawOdds

logger = logging.getLogger(__name__)

DEBUG_DIR = DATA_DIR / "debug"

BASE = "https://tipkurz.etipos.sk"
SVC = "/WebServices/Api/SportsBettingService.svc"
LANG = 17  # Slovak


# ---------------------------------------------------------------------------
# Protobuf helpers (hand-rolled — no protobuf library dependency)
# ---------------------------------------------------------------------------

def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if not (byte & 0x80):
            break
    return result, pos


def _decode_b64(b64_str: str) -> bytes:
    clean = b64_str.strip().strip('"')
    padding = 4 - len(clean) % 4
    if padding != 4:
        clean += "=" * padding
    return base64.b64decode(clean)


def _parse_proto_values(data: bytes, depth: int = 0) -> dict:
    """Recursively extract strings, floats, and ints from raw protobuf bytes."""
    strings: list[tuple[int, str]] = []
    floats: list[tuple[int, float]] = []
    ints: list[int] = []
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _read_varint(data, pos)
            field_num = tag_wire >> 3
            wire_type = tag_wire & 0x7
            if field_num == 0 and wire_type == 0:
                break
            if wire_type == 0:
                val, pos = _read_varint(data, pos)
                ints.append(val)
            elif wire_type == 1:  # 64-bit (double)
                if pos + 8 <= len(data):
                    val = struct.unpack("<d", data[pos : pos + 8])[0]
                    if 1.0 <= val <= 1000.0:
                        floats.append((field_num, round(val, 3)))
                    pos += 8
                else:
                    break
            elif wire_type == 2:  # length-delimited
                length, pos = _read_varint(data, pos)
                if pos + length > len(data):
                    break
                raw = data[pos : pos + length]
                pos += length
                try:
                    s = raw.decode("utf-8")
                    ratio = sum(1 for c in s if ord(c) >= 32 or c in "\n\t") / max(len(s), 1)
                    if ratio > 0.7 and len(s.strip()) >= 2:
                        strings.append((field_num, s.strip()))
                    elif depth < 5:
                        sub = _parse_proto_values(raw, depth + 1)
                        strings.extend(sub["strings"])
                        floats.extend(sub["floats"])
                        ints.extend(sub["ints"])
                except UnicodeDecodeError:
                    if depth < 5:
                        sub = _parse_proto_values(raw, depth + 1)
                        strings.extend(sub["strings"])
                        floats.extend(sub["floats"])
                        ints.extend(sub["ints"])
            elif wire_type == 5:  # 32-bit (float)
                if pos + 4 <= len(data):
                    val = struct.unpack("<f", data[pos : pos + 4])[0]
                    if 1.0 <= val <= 1000.0:
                        floats.append((field_num, round(val, 3)))
                    pos += 4
                else:
                    break
            else:
                break
        except Exception:
            break
    return {"strings": strings, "floats": floats, "ints": ints}


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class TiposScraper(BaseScraper):
    """Scraper for tipos.sk using the tipkurz.etipos.sk JSON API via Playwright."""

    BOOKMAKER = "tipos"
    BASE_URL = BASE
    REQUEST_DELAY = 2.0

    def __init__(self, db_session, http_client=None):
        super().__init__(db_session, http_client)
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._token: str = ""
        self._ready = False
        self._init_browser()

    # ------------------------------------------------------------------
    # Browser / session setup
    # ------------------------------------------------------------------

    def _init_browser(self):
        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self._context = self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="sk-SK",
            )
            self._page = self._context.new_page()

            logger.info("[tipos] Loading page via Playwright...")
            self._page.goto(f"{BASE}/sk/futbal", wait_until="networkidle", timeout=30000)
            self._page.wait_for_timeout(2000)

            # Grab session token
            self._token = self._fetch_token()
            logger.info(f"[tipos] Browser ready. Token={'<ok>' if self._token else '<missing>'}")
            self._ready = True
        except Exception:
            logger.exception("[tipos] Playwright init failed")
            self._ready = False

    def _fetch_token(self) -> str:
        """Obtain a session token from GetLiveInitData."""
        try:
            result = self._page.evaluate("""async () => {
                const resp = await fetch(
                    '/WebServices/ApiSession/SportsBettingSessionService.svc/GetLiveInitData',
                    {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}
                );
                return resp.json();
            }""")
            return result.get("Token", "") if isinstance(result, dict) else ""
        except Exception:
            logger.debug("[tipos] GetLiveInitData failed, continuing without token")
            return ""

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _api_call(self, endpoint: str, payload: dict) -> dict:
        """POST to SportsBettingService from within the Playwright context."""
        import time as _time

        self._rate_limit()
        self._last_request_time = _time.time()

        payload_json = json.dumps(payload)
        url = f"{SVC}/{endpoint}"
        try:
            result = self._page.evaluate(
                """async ({url, body}) => {
                    const resp = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json;charset=UTF-8',
                            'Accept': 'application/json'
                        },
                        body: body
                    });
                    const text = await resp.text();
                    return {status: resp.status, body: text};
                }""",
                {"url": url, "body": payload_json},
            )
        except Exception as e:
            logger.error(f"[tipos] API call to {endpoint} failed: {e}")
            return {}

        if result.get("status") != 200:
            logger.warning(f"[tipos] {endpoint} returned HTTP {result.get('status')}")
            return {}

        try:
            return json.loads(result.get("body", "{}"))
        except json.JSONDecodeError:
            logger.warning(f"[tipos] {endpoint} non-JSON response")
            return {}

    def _decode_return_value(self, data: dict) -> dict:
        """Decode the base64+protobuf ReturnValue from an API response."""
        rv = data.get("ReturnValue", "")
        if not rv or not isinstance(rv, str) or len(rv) < 10:
            return {"strings": [], "floats": [], "ints": []}
        try:
            raw = _decode_b64(rv)
            return _parse_proto_values(raw)
        except Exception as e:
            logger.debug(f"[tipos] ReturnValue decode failed: {e}")
            return {"strings": [], "floats": [], "ints": []}

    def _dump_debug(self, name: str, data):
        if not settings.debug_dump:
            return
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = DEBUG_DIR / f"tipos_{name}_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"[tipos] Debug dump: {path}")

    # ------------------------------------------------------------------
    # Discovery helpers (used by CLI --discover)
    # ------------------------------------------------------------------

    def discover_categories(self) -> dict:
        """Fetch the category tree (sports/leagues)."""
        data = self._api_call(
            "GetWebStandardCategories",
            {"LanguageID": LANG, "Token": self._token, "IncludeLiveCategories": True},
        )
        self._dump_debug("categories", data)
        return data

    def discover_top_bets(self) -> dict:
        """Fetch top bet offers."""
        data = self._api_call(
            "GetWebTopBets",
            {"LanguageID": LANG, "Token": self._token, "TopOfferType": 8,
             "TypeAddData": None, "TimeStamp": None},
        )
        self._dump_debug("top_bets", data)
        return data

    def discover_event(self, event_id: int) -> dict:
        """Fetch full detail for a single event (match + odds)."""
        data = self._api_call(
            "GetWebStandardEventExt",
            {"EventID": event_id, "LanguageID": LANG, "Token": self._token,
             "UseLongPolling": True},
        )
        self._dump_debug(f"event_{event_id}", data)
        return data

    # ------------------------------------------------------------------
    # Category → match-listing
    # ------------------------------------------------------------------

    def _get_category_events(self, category_id: str) -> list[dict]:
        """
        Fetch matches for a category (league).

        The API uses GetWebTopBets with TopOfferType=8 for "all offers"
        or GetWebStandardCategoryOffer. We attempt several known endpoints.
        The CategoryID from our seed data is the Tipos internal category ID
        (e.g. "150" for Slovak football Niké Liga).
        """
        # Primary: GetWebStandardCategoryOffer
        for ep, payload in [
            (
                "GetWebStandardCategoryOffer",
                {"LanguageID": LANG, "Token": self._token,
                 "CategoryID": int(category_id)},
            ),
            (
                "GetWebCategoryOffer",
                {"LanguageID": LANG, "Token": self._token,
                 "CategoryID": int(category_id)},
            ),
            (
                "GetWebEventsByCategory",
                {"LanguageID": LANG, "Token": self._token,
                 "CategoryID": int(category_id)},
            ),
        ]:
            data = self._api_call(ep, payload)
            if data:
                self._dump_debug(f"category_{category_id}_{ep}", data)
                event_ids = self._extract_event_ids(data)
                if event_ids:
                    logger.info(
                        f"[tipos] {ep}(category={category_id}) → {len(event_ids)} events"
                    )
                    return event_ids

        logger.warning(f"[tipos] No events found for category {category_id}")
        return []

    def _extract_event_ids(self, data: dict) -> list[dict]:
        """
        Pull event IDs out of an API response.

        Tipos API returns protobuf; we decode it and look for large integer
        IDs and paired team-name strings. Returns list of dicts with keys:
        event_id, home, away (best-effort).
        """
        rv = data.get("ReturnValue")

        # Case 1: ReturnValue is a plain list of event dicts
        if isinstance(rv, list):
            return rv

        # Case 2: ReturnValue is a base64 protobuf blob
        if isinstance(rv, str) and len(rv) > 10:
            parsed = self._decode_return_value(data)
            ids = [i for i in parsed["ints"] if 1_000_000 < i < 9_999_999_999]
            strings = [s for _, s in parsed["strings"] if len(s) >= 3]
            # Pair up IDs (best-effort — each event has one id and two team names)
            events = []
            for i, eid in enumerate(ids):
                base = i * 3
                home = strings[base] if base < len(strings) else ""
                away = strings[base + 1] if base + 1 < len(strings) else ""
                events.append({"event_id": eid, "home": home, "away": away})
            return events

        return []

    # ------------------------------------------------------------------
    # BaseScraper interface
    # ------------------------------------------------------------------

    def scrape_matches(self, league_external_id: str) -> list[RawMatch]:
        if not self._ready:
            logger.error("[tipos] Playwright not initialised, skipping")
            return []

        events = self._get_category_events(league_external_id)
        matches = []
        for ev in events:
            try:
                rm = self._event_to_raw_match(ev, league_external_id)
                if rm:
                    matches.append(rm)
            except Exception:
                logger.exception(f"[tipos] Failed to parse event: {ev}")
        return matches

    def scrape_odds(self, match_external_id: str) -> list[RawOdds]:
        if not self._ready:
            return []

        try:
            event_id = int(match_external_id)
        except (ValueError, TypeError):
            logger.warning(f"[tipos] Invalid match_external_id: {match_external_id}")
            return []

        data = self._api_call(
            "GetWebStandardEventExt",
            {"EventID": event_id, "LanguageID": LANG, "Token": self._token,
             "UseLongPolling": True},
        )
        if not data:
            return []
        self._dump_debug(f"odds_{event_id}", data)
        return self._extract_odds(data, match_external_id)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _event_to_raw_match(self, ev: dict, league_ext_id: str) -> Optional[RawMatch]:
        """Convert a raw event dict (from category listing) to RawMatch."""
        if isinstance(ev, dict) and "event_id" in ev:
            # From our protobuf extraction
            eid = str(ev["event_id"])
            home = ev.get("home", "")
            away = ev.get("away", "")
            start = ev.get("startTime") or ev.get("start_time")
        else:
            # Might be a direct JSON dict from ReturnValue list
            eid = str(
                ev.get("EventID") or ev.get("eventId") or ev.get("ID", "")
            )
            home = (
                ev.get("HomeTeam") or ev.get("home") or
                ev.get("HomeTeamName", "")
            )
            away = (
                ev.get("AwayTeam") or ev.get("away") or
                ev.get("AwayTeamName", "")
            )
            start = ev.get("StartTime") or ev.get("startTime")

        if not eid:
            return None

        # Try to parse combined name like "Home - Away"
        if not home or not away:
            name = ev.get("Name") or ev.get("name", "")
            for sep in [" - ", " vs ", " – "]:
                if sep in name:
                    parts = name.split(sep, 1)
                    home, away = parts[0].strip(), parts[1].strip()
                    break

        if not home or not away:
            return None

        start_time = self._parse_datetime(start) if start else datetime.utcnow()

        return RawMatch(
            external_id=eid,
            home_team=home,
            away_team=away,
            league_external_id=league_ext_id,
            start_time=start_time,
            status="prematch",
            url=f"{BASE}/zapas/{eid}",
        )

    def _extract_odds(self, data: dict, match_ext_id: str) -> list[RawOdds]:
        """Extract odds from GetWebStandardEventExt response."""
        odds: list[RawOdds] = []
        parsed = self._decode_return_value(data)
        floats = [(fnum, fval) for fnum, fval in parsed["floats"]
                  if 1.01 <= fval <= 500.0]

        if not floats:
            return odds

        # Heuristic: odds come in groups of 2 (home/away) or 3 (1x2)
        # Try to map to 1x2 if we have exactly 3 odds in range
        plausible = [fval for _, fval in floats if 1.01 <= fval <= 50.0]

        url = f"{BASE}/zapas/{match_ext_id}"

        if len(plausible) >= 3:
            markets = [
                ("1x2", "home", plausible[0]),
                ("1x2", "draw", plausible[1]),
                ("1x2", "away", plausible[2]),
            ]
            for market, sel, val in markets:
                odds.append(RawOdds(
                    match_external_id=match_ext_id,
                    market=market,
                    selection=sel,
                    odds=val,
                    url=url,
                ))
        elif len(plausible) == 2:
            for sel, val in zip(["home", "away"], plausible):
                odds.append(RawOdds(
                    match_external_id=match_ext_id,
                    market="1x2",
                    selection=sel,
                    odds=val,
                    url=url,
                ))

        logger.debug(
            f"[tipos] Extracted {len(odds)} odds for event {match_ext_id} "
            f"(raw floats: {floats[:10]})"
        )
        return odds

    def _parse_datetime(self, raw) -> datetime:
        if isinstance(raw, (int, float)):
            ts = raw / 1000 if raw > 1e12 else raw
            return datetime.utcfromtimestamp(ts)
        if isinstance(raw, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%d.%m.%Y %H:%M",
            ]:
                try:
                    return datetime.strptime(raw.rstrip("Z"), fmt)
                except ValueError:
                    continue
        return datetime.utcnow()

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
