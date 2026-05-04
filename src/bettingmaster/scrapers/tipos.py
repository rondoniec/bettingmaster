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

Why an isolated thread: APScheduler's worker threads sometimes carry a running
asyncio event loop that Playwright's sync API refuses to share. Every scrape
call spawns a fresh concurrent.futures.ThreadPoolExecutor thread — each new
Python thread starts with empty asyncio threadlocal state.
"""

import base64
import concurrent.futures
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
    # Large Tipos responses have deeply nested wrapper messages (field 1 wraps
    # everything). Depth 20 is needed to reach actual leaf nodes.
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
                    elif depth < 20:
                        sub = _parse_proto_values(raw, depth + 1)
                        strings.extend(sub["strings"])
                        floats.extend(sub["floats"])
                        ints.extend(sub["ints"])
                except UnicodeDecodeError:
                    if depth < 20:
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


def _decode_return_value(data: dict) -> dict:
    rv = data.get("ReturnValue", "")
    if not rv or not isinstance(rv, str) or len(rv) < 10:
        return {"strings": [], "floats": [], "ints": []}
    try:
        raw = _decode_b64(rv)
        return _parse_proto_values(raw)
    except Exception as e:
        logger.debug("[tipos] ReturnValue decode failed: %s", e)
        return {"strings": [], "floats": [], "ints": []}


def _extract_event_ids_from_data(data: dict) -> list[dict]:
    """Pull event IDs out of a GetWebTopBets response.

    The ReturnValue protobuf includes match title strings in "Team A - Team B"
    format. We prefer those over raw sequential string assignment, which
    mis-pairs team names with unrelated strings (channel names, etc.).
    """
    rv = data.get("ReturnValue")

    if isinstance(rv, list):
        return rv

    if isinstance(rv, str) and len(rv) > 10:
        parsed = _decode_return_value(data)
        ids = [i for i in parsed["ints"] if 1_000_000 < i < 9_999_999_999]
        all_strings = [s for _, s in parsed["strings"] if len(s) >= 2]

        # Prefer "Team A - Team B" title strings over raw sequential pairing.
        # Match titles contain exactly one " - " and are 6-80 chars long.
        match_titles = [
            s for s in all_strings
            if " - " in s and 6 < len(s) < 80 and s.count(" - ") == 1
        ]

        events = []
        for i, eid in enumerate(ids):
            if i < len(match_titles):
                title = match_titles[i]
                parts = title.split(" - ", 1)
                home, away = parts[0].strip(), parts[1].strip()
            else:
                home = away = ""
            events.append({"event_id": eid, "home": home, "away": away})
        return events

    return []


# ---------------------------------------------------------------------------
# Module-level Playwright functions (run in fresh threads)
# ---------------------------------------------------------------------------

def _make_api_call(page, endpoint: str, payload: dict) -> dict:
    """POST to SportsBettingService from within a Playwright page context."""
    payload_json = json.dumps(payload)
    url = f"{SVC}/{endpoint}"
    try:
        result = page.evaluate(
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
        logger.error("[tipos] API call to %s failed: %s", endpoint, e)
        return {}

    if result.get("status") != 200:
        logger.warning("[tipos] %s returned HTTP %s", endpoint, result.get("status"))
        return {}

    try:
        return json.loads(result.get("body", "{}"))
    except json.JSONDecodeError:
        return {}


def _open_browser_and_get_token(headless: bool = True):
    """Start Playwright, load the tipos page, capture the session token.

    Returns (playwright, browser, context, page, token). Caller must close.
    """
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        locale="sk-SK",
    )
    page = context.new_page()

    captured: list[str] = []

    def _on_response(resp):
        if "GetLiveInitData" in resp.url:
            try:
                body = resp.body()
                data = json.loads(body)
                tok = data.get("Token", "")
                if tok:
                    captured.append(tok)
            except Exception:
                pass

    page.on("response", _on_response)
    logger.info("[tipos] Loading page via Playwright...")
    page.goto(f"{BASE}/sk/futbal", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    page.remove_listener("response", _on_response)

    token = captured[0] if captured else ""
    logger.info("[tipos] Browser ready. Token=%s", "<ok>" if token else "<missing>")
    return pw, browser, context, page, token


def _close_browser_session(pw, browser, context) -> None:
    """Close Playwright browser session objects in reverse order."""
    for obj in (context, browser):
        if obj is not None:
            try:
                obj.close()
            except Exception:
                pass
    if pw is not None:
        try:
            pw.stop()
        except Exception:
            pass


def _scrape_tipos_matches(headless: bool = True) -> list[dict]:
    """Full Tipos scraping session: load page, get token, fetch all events + odds.

    Returns list of dicts: {event_id, home, away, detail_data}.
    """
    pw = browser = context = None
    try:
        pw, browser, context, page, token = _open_browser_and_get_token(headless)
        if not token:
            logger.warning("[tipos] No token — skipping scrape")
            return []

        top_bets = _make_api_call(
            page,
            "GetWebTopBets",
            {"LanguageID": LANG, "Token": token,
             "TopOfferType": 8, "TypeAddData": None, "TimeStamp": None},
        )
        events = _extract_event_ids_from_data(top_bets)
        logger.info("[tipos] GetWebTopBets → %d events", len(events))

        results = []
        for ev in events:
            event_id = ev.get("event_id")
            if not event_id:
                continue
            detail = _make_api_call(
                page,
                "GetWebStandardEventExt",
                {"EventID": event_id, "LanguageID": LANG, "Token": token,
                 "UseLongPolling": True},
            )
            ev["detail_data"] = detail
            results.append(ev)

        return results
    except Exception:
        logger.exception("[tipos] Scrape session failed")
        return []
    finally:
        _close_browser_session(pw, browser, context)


def _scrape_tipos_event(event_id: int, headless: bool = True) -> dict:
    """Fetch a single event's detail data in a fresh browser session."""
    pw = browser = context = None
    try:
        pw, browser, context, page, token = _open_browser_and_get_token(headless)
        if not token:
            return {}
        return _make_api_call(
            page,
            "GetWebStandardEventExt",
            {"EventID": event_id, "LanguageID": LANG, "Token": token,
             "UseLongPolling": True},
        )
    except Exception:
        logger.exception("[tipos] Single-event fetch failed for %s", event_id)
        return {}
    finally:
        _close_browser_session(pw, browser, context)


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class TiposScraper(BaseScraper):
    """Scraper for tipos.sk using the tipkurz.etipos.sk JSON API via Playwright."""

    BOOKMAKER = "tipos"
    BASE_URL = BASE
    REQUEST_DELAY = 2.0
    CREATES_MATCHES = False  # no reliable kickoff times; only attach to existing records

    def __init__(self, db_session, http_client=None):
        super().__init__(db_session, http_client)
        self._odds_cache: dict[str, list[RawOdds]] = {}
        self._url_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Fresh-thread runner
    # ------------------------------------------------------------------

    def _run_in_fresh_thread(self, fn, *args, timeout: int = 180):
        import subprocess as _sp
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(fn, *args)
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning("[tipos] Playwright timed out after %ds — killing chrome", timeout)
            _sp.run(["pkill", "-9", "-f", "chrom"], capture_output=True)
            return None
        except Exception:
            logger.exception("[tipos] thread crashed")
            _sp.run(["pkill", "-9", "-f", "chrom"], capture_output=True)
            return None
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------
    # Discovery helpers (used by CLI --discover)
    # ------------------------------------------------------------------

    def discover_top_bets(self) -> dict:
        """Fetch top bet offers (CLI debugging helper)."""
        def _fetch():
            pw, browser, context, page, token = _open_browser_and_get_token()
            try:
                return _make_api_call(
                    page, "GetWebTopBets",
                    {"LanguageID": LANG, "Token": token, "TopOfferType": 8,
                     "TypeAddData": None, "TimeStamp": None},
                )
            finally:
                _close_browser_session(pw, browser, context)

        return self._run_in_fresh_thread(_fetch) or {}

    # ------------------------------------------------------------------
    # BaseScraper interface
    # ------------------------------------------------------------------

    def scrape_matches(self, league_external_id: str) -> list[RawMatch]:
        raw = self._run_in_fresh_thread(_scrape_tipos_matches, settings.tipos_headless)
        if not raw:
            return []

        self._odds_cache.clear()
        self._url_cache.clear()

        _OUTRIGHT_TOKENS = frozenset(
            ["stávky", "strelec", "strelci", "víťaz", "postup", "zostup",
             "champion", "winner", "scorer", "liga", "league", "hlavné",
             "celkovo", "canal", "sport 1", "sport 2"]
        )

        def _is_garbage(name: str) -> bool:
            if not name or name[0].isdigit():
                return True
            low = name.lower()
            return any(tok in low for tok in _OUTRIGHT_TOKENS)

        matches = []
        for ev in raw:
            try:
                rm = self._event_to_raw_match(ev, league_external_id)
                if not rm:
                    continue
                if _is_garbage(rm.home_team) or _is_garbage(rm.away_team):
                    logger.debug("[tipos] skip garbage: %s vs %s", rm.home_team, rm.away_team)
                    continue
                matches.append(rm)
                eid = str(ev.get("event_id", ""))
                detail = ev.get("detail_data") or {}
                if detail:
                    self._odds_cache[eid] = self._extract_odds(detail, eid)
                    self._url_cache[eid] = rm.url
            except Exception:
                logger.exception("[tipos] Failed to parse event: %s", ev)
        return matches

    def scrape_odds(self, match_external_id: str) -> list[RawOdds]:
        cached = self._odds_cache.get(match_external_id)
        if cached is not None:
            return cached

        try:
            event_id = int(match_external_id)
        except (ValueError, TypeError):
            logger.warning("[tipos] Invalid match_external_id: %s", match_external_id)
            return []

        detail = self._run_in_fresh_thread(_scrape_tipos_event, event_id, settings.tipos_headless)
        if not detail:
            return []

        odds = self._extract_odds(detail, match_external_id)
        self._odds_cache[match_external_id] = odds
        return odds

    def scrape_odds_for_raw_match(self, raw_match: RawMatch) -> list[RawOdds]:
        cached = self._odds_cache.get(raw_match.external_id)
        if cached is not None:
            return cached
        return self.scrape_odds(raw_match.external_id)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _event_to_raw_match(self, ev: dict, league_ext_id: str) -> Optional[RawMatch]:
        """Convert a raw event dict (from category listing) to RawMatch."""
        if isinstance(ev, dict) and "event_id" in ev:
            eid = str(ev["event_id"])
            home = ev.get("home", "")
            away = ev.get("away", "")
            start = ev.get("startTime") or ev.get("start_time")
        else:
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
        parsed = _decode_return_value(data)
        floats = [(fnum, fval) for fnum, fval in parsed["floats"]
                  if 1.01 <= fval <= 500.0]

        if not floats:
            return odds

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

        logger.info(
            "[tipos] Extracted %d odds for event %s (raw floats: %s)",
            len(odds), match_ext_id, floats[:10],
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
