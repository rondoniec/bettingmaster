"""Polymarket scraper using the public Gamma API.

Polymarket is a prediction market where prices are probabilities (0–1).
We convert them to decimal odds via: decimal_odds = 1 / probability.

Confirmed API:
  GET https://gamma-api.polymarket.com/events/pagination
      ?tag_slug=soccer&active=true&closed=false&limit=100
      &order=startDate&ascending=true&offset=0
  → { data: [...events], pagination: { total, limit, offset } }

  GET https://gamma-api.polymarket.com/events/slug/{slug}
  → single event with markets (1X2)

  GET https://gamma-api.polymarket.com/events/slug/{slug}-more-markets
  → spreads (±1.5/±2.5), O/U (1.5/2.5/3.5/4.5), BTTS

  GET https://gamma-api.polymarket.com/events/slug/{slug}-halftime-result
  → halftime 1X2

Market name mapping:
  1x2 event         → market="1x2",            selections: home/draw/away
  Spread -1.5/-2.5  → market="handicap_1_5"/"handicap_2_5", selections: home/away
  O/U X.5           → market="over_under_1_5"/"over_under_2_5"/...  selections: over/under
  BTTS              → market="btts",            selections: yes/no
  Halftime 1X2      → market="1x2_ht",         selections: home/draw/away

Polymarket does NOT require league-specific IDs; it fetches all soccer events by tag.
This scraper overrides run() to iterate over all Polymarket soccer events and
cross-reference them with matches already in our DB.
"""

import json
import logging
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

import httpx
from rapidfuzz import fuzz

from bettingmaster.config import DATA_DIR, settings
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.scrapers.base import BaseScraper, RawOdds

logger = logging.getLogger(__name__)

GAMMA_API = "https://gamma-api.polymarket.com"
DEBUG_DIR = DATA_DIR / "debug"

# Match a handicap question: "Spread: FC Barcelona (-1.5)"
_SPREAD_RE = re.compile(r"Spread:\s*(.+?)\s*\(([+-]?\d+\.5)\)", re.IGNORECASE)

# Match a totals question: "... O/U 2.5 ..." or "... 2.5 O/U ..."
_TOTAL_RE = re.compile(r"O/U\s+(\d+\.5)|(\d+\.5)\s+O/U", re.IGNORECASE)

# Match a BTTS question
_BTTS_RE = re.compile(r"both teams (to )?score", re.IGNORECASE)


def _normalize(s: str) -> str:
    """Lowercase + strip accents so 'Atlético' == 'Atletico' for matching."""
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


def _prob_to_decimal(prob: float) -> Optional[float]:
    """Convert a probability (0–1) to decimal odds. Returns None if <= 0 or > 1."""
    if prob <= 0 or prob > 1:
        return None
    return round(1.0 / prob, 3)


def _parse_outcomes(market: dict) -> tuple[list[str], list[float]]:
    """Return (outcomes, probabilities) from a market dict."""
    raw_outcomes = market.get("outcomes", "[]")
    raw_prices = market.get("outcomePrices", "[]")
    try:
        outcomes = json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else list(raw_outcomes)
        prices_raw = json.loads(raw_prices) if isinstance(raw_prices, str) else list(raw_prices)
        prices = [float(p) for p in prices_raw]
    except Exception:
        return [], []
    return outcomes, prices


def _line_key(line: str) -> str:
    """Convert "1.5" → "1_5", "2.5" → "2_5", etc."""
    return line.replace(".", "_")


class PolymarketScraper(BaseScraper):
    """Scrapes football match odds from Polymarket's public Gamma API."""

    BOOKMAKER = "polymarket"
    BASE_URL = GAMMA_API
    REQUEST_DELAY = 0.8

    def __init__(self, db_session, http_client: httpx.Client | None = None):
        super().__init__(db_session, http_client)

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        url = f"{GAMMA_API}{path}"
        resp = self._request("GET", url, params=params)
        return resp.json()

    def _get_slug(self, slug: str) -> Optional[dict]:
        """Fetch a single event by slug. Returns None on 404 / error."""
        url = f"{GAMMA_API}/events/slug/{slug}"
        self._rate_limit()
        self._last_request_time = __import__("time").time()
        try:
            resp = self._client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.debug(f"[polymarket] Slug '{slug}' HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.debug(f"[polymarket] Slug '{slug}' error: {e}")
            return None

    def _dump_debug(self, name: str, data):
        if not settings.debug_dump:
            return
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = DEBUG_DIR / f"polymarket_{name}_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"[polymarket] Debug dump: {path}")

    # ------------------------------------------------------------------
    # Fetch all active soccer events (paginated)
    # ------------------------------------------------------------------

    def _fetch_all_soccer_events(self) -> list[dict]:
        """Paginate through all active soccer events (newest start date first)."""
        all_events: list[dict] = []
        offset = 0
        limit = 100
        max_pages = 20  # safety cap (~2000 events)

        for _ in range(max_pages):
            try:
                result = self._get(
                    "/events/pagination",
                    params={
                        "tag_slug": "soccer",
                        "active": "true",
                        "closed": "false",
                        "limit": limit,
                        # Newest first so upcoming matches come before old closed ones
                        "order": "startDate",
                        "ascending": "false",
                        "offset": offset,
                    },
                )
            except Exception as e:
                logger.error(f"[polymarket] Pagination fetch failed (offset={offset}): {e}")
                break

            data = result.get("data", []) if isinstance(result, dict) else []
            if not data:
                break

            all_events.extend(data)
            offset += limit

            # API returns None for total — stop when a page comes back short
            if len(data) < limit:
                break

        logger.info(f"[polymarket] Fetched {len(all_events)} active soccer events")
        return all_events

    # ------------------------------------------------------------------
    # Identify which events are match-level 1X2 events
    # ------------------------------------------------------------------

    def _is_match_event(self, event: dict) -> bool:
        """
        Returns True if this event is a main 1X2 match event (not -more-markets,
        not -halftime-result, not an aggregate/outright).
        A match event has exactly 3 markets whose groupItemTitle values look like
        two team names + a draw entry.
        """
        slug = event.get("slug", "")
        if slug.endswith("-more-markets") or slug.endswith("-halftime-result"):
            return False

        markets = event.get("markets", [])
        if len(markets) != 3:
            return False

        titles = [m.get("groupItemTitle", "") for m in markets]
        has_draw = any("draw" in t.lower() for t in titles)
        return has_draw

    # ------------------------------------------------------------------
    # Parse team names and match date from main event
    # ------------------------------------------------------------------

    def _parse_team_names(self, event: dict) -> tuple[str, str]:
        """
        Extract (home_team, away_team) from an event's markets.
        The 3 markets have groupItemTitle = [home_name, "Draw (...)", away_name]
        in order.
        """
        markets = event.get("markets", [])
        if len(markets) != 3:
            return "", ""

        non_draw = [
            m.get("groupItemTitle", "")
            for m in markets
            if "draw" not in m.get("groupItemTitle", "").lower()
        ]
        if len(non_draw) < 2:
            return "", ""

        home = non_draw[0].strip()
        away = non_draw[1].strip()
        return home, away

    def _parse_match_date(self, event: dict) -> Optional[datetime]:
        raw = event.get("startDate") or event.get("endDate")
        if not raw:
            return None
        for fmt in [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                return datetime.strptime(raw[: len(fmt)], fmt)
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------
    # Find matching DB match by team name fuzzy matching + date
    # ------------------------------------------------------------------

    def _find_db_match(
        self,
        home: str,
        away: str,
        match_date: Optional[datetime],
    ) -> Optional[Match]:
        """
        Query all DB matches and return the one whose (home_team, away_team, date)
        best matches the Polymarket teams. Date window: ±1 day.
        """
        query = self._db.query(Match)

        if match_date:
            date_from = match_date - timedelta(days=1)
            date_to = match_date + timedelta(days=1)
            query = query.filter(
                Match.start_time >= date_from,
                Match.start_time <= date_to,
            )

        candidates = query.all()
        if not candidates:
            return None

        best_score = 0.0
        best_match = None

        hn = _normalize(home)
        an = _normalize(away)

        for m in candidates:
            mhn = _normalize(m.home_team)
            man = _normalize(m.away_team)

            home_score = fuzz.token_set_ratio(hn, mhn) / 100.0
            away_score = fuzz.token_set_ratio(an, man) / 100.0
            score = home_score + away_score

            # Also try swapped (Polymarket sometimes lists away first)
            home_score_sw = fuzz.token_set_ratio(hn, man) / 100.0
            away_score_sw = fuzz.token_set_ratio(an, mhn) / 100.0
            score_sw = home_score_sw + away_score_sw

            final_score = max(score, score_sw)
            if final_score > best_score:
                best_score = final_score
                best_match = m

        # Require combined score >= 1.4 (each team ~0.7 similarity)
        if best_score >= 1.4 and best_match:
            logger.debug(
                f"[polymarket] Matched '{home} vs {away}' → "
                f"'{best_match.home_team} vs {best_match.away_team}' (score={best_score:.2f})"
            )
            return best_match

        logger.debug(
            f"[polymarket] No DB match for '{home} vs {away}' "
            f"(best_score={best_score:.2f}, candidates={len(candidates)})"
        )
        return None

    # ------------------------------------------------------------------
    # Odds extraction from main event (1X2)
    # ------------------------------------------------------------------

    def _extract_1x2(self, event: dict, match_id: str, url: str) -> list[RawOdds]:
        markets = event.get("markets", [])
        if len(markets) != 3:
            return []

        result: list[RawOdds] = []
        for market in markets:
            title = market.get("groupItemTitle", "").lower()
            outcomes, prices = _parse_outcomes(market)
            if not outcomes or not prices:
                continue

            # Each market is a YES/NO market; the YES price (index 0) is what we want
            yes_price = prices[0] if len(prices) >= 1 else None
            if yes_price is None:
                continue

            dec = _prob_to_decimal(yes_price)
            if not dec or not (1.01 <= dec <= 500):
                continue

            if "draw" in title:
                selection = "draw"
            elif not result:
                selection = "home"
            else:
                selection = "away"

            result.append(RawOdds(
                match_external_id=match_id,
                market="1x2",
                selection=selection,
                odds=dec,
                url=url,
            ))

        return result

    # ------------------------------------------------------------------
    # Odds extraction from -more-markets event (spreads, O/U, BTTS)
    # ------------------------------------------------------------------

    def _extract_more_markets(
        self,
        event: dict,
        home: str,
        away: str,
        match_id: str,
        url: str,
    ) -> list[RawOdds]:
        markets = event.get("markets", [])
        result: list[RawOdds] = []

        for market in markets:
            question = market.get("question", "") or market.get("groupItemTitle", "")
            outcomes, prices = _parse_outcomes(market)
            if not outcomes or not prices:
                continue

            # --- Spread / Handicap ---
            spread_m = _SPREAD_RE.search(question)
            if spread_m:
                favored_team = spread_m.group(1).strip()
                line = spread_m.group(2)  # e.g. "-1.5"
                line_abs = line.lstrip("+-")  # "1.5"
                market_key = f"handicap_{_line_key(line_abs)}"

                # Determine which outcome is home vs away
                # outcomes[0] = favored team, outcomes[1] = underdog
                home_sim = fuzz.token_set_ratio(favored_team.lower(), home.lower())
                away_sim = fuzz.token_set_ratio(favored_team.lower(), away.lower())

                if home_sim >= away_sim:
                    # favored = home (home -X.5, away +X.5)
                    pairs = [("home", prices[0]), ("away", prices[1])]
                else:
                    # favored = away (away -X.5, home +X.5)
                    pairs = [("away", prices[0]), ("home", prices[1])]

                for selection, prob in pairs:
                    dec = _prob_to_decimal(prob)
                    if dec and 1.01 <= dec <= 500:
                        result.append(RawOdds(
                            match_external_id=match_id,
                            market=market_key,
                            selection=selection,
                            odds=dec,
                            url=url,
                        ))
                continue

            # --- Totals (Over/Under) ---
            total_m = _TOTAL_RE.search(question)
            if total_m:
                line = total_m.group(1) or total_m.group(2)  # e.g. "2.5"
                market_key = f"over_under_{_line_key(line)}"

                # outcomes order: ["Over", "Under"] or similar
                for outcome, prob in zip(outcomes, prices):
                    outcome_lower = outcome.lower()
                    if "over" in outcome_lower:
                        selection = "over"
                    elif "under" in outcome_lower:
                        selection = "under"
                    else:
                        continue
                    dec = _prob_to_decimal(prob)
                    if dec and 1.01 <= dec <= 500:
                        result.append(RawOdds(
                            match_external_id=match_id,
                            market=market_key,
                            selection=selection,
                            odds=dec,
                            url=url,
                        ))
                continue

            # --- Both Teams to Score ---
            if _BTTS_RE.search(question):
                for outcome, prob in zip(outcomes, prices):
                    outcome_lower = outcome.lower()
                    if "yes" in outcome_lower:
                        selection = "yes"
                    elif "no" in outcome_lower:
                        selection = "no"
                    else:
                        continue
                    dec = _prob_to_decimal(prob)
                    if dec and 1.01 <= dec <= 500:
                        result.append(RawOdds(
                            match_external_id=match_id,
                            market="btts",
                            selection=selection,
                            odds=dec,
                            url=url,
                        ))
                continue

        return result

    # ------------------------------------------------------------------
    # Odds extraction from -halftime-result event
    # ------------------------------------------------------------------

    def _extract_halftime(self, event: dict, match_id: str, url: str) -> list[RawOdds]:
        markets = event.get("markets", [])
        if len(markets) != 3:
            return []

        result: list[RawOdds] = []
        for market in markets:
            title = market.get("groupItemTitle", "").lower()
            outcomes, prices = _parse_outcomes(market)
            if not prices:
                continue

            yes_price = prices[0] if len(prices) >= 1 else None
            if yes_price is None:
                continue

            dec = _prob_to_decimal(yes_price)
            if not dec or not (1.01 <= dec <= 500):
                continue

            if "draw" in title:
                selection = "draw"
            elif not result:
                selection = "home"
            else:
                selection = "away"

            result.append(RawOdds(
                match_external_id=match_id,
                market="1x2_ht",
                selection=selection,
                odds=dec,
                url=url,
            ))

        return result

    # ------------------------------------------------------------------
    # Required abstract methods (not used directly; run() is overridden)
    # ------------------------------------------------------------------

    def scrape_matches(self, league_external_id: str) -> list:
        return []

    def scrape_odds(self, match_external_id: str) -> list[RawOdds]:
        return []

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, league_ids: dict | None = None, normalizer=None):
        """
        Fetch all active Polymarket soccer events and persist odds for any
        match already in our DB. league_ids is ignored — Polymarket fetches
        by sport tag globally.
        """
        events = self._fetch_all_soccer_events()
        self._dump_debug("all_events", events)

        processed = 0
        matched = 0

        for event in events:
            if not self._is_match_event(event):
                continue

            processed += 1
            slug = event.get("slug", "")
            home, away = self._parse_team_names(event)
            if not home or not away:
                logger.debug(f"[polymarket] Could not parse teams from slug '{slug}'")
                continue

            match_date = self._parse_match_date(event)
            db_match = self._find_db_match(home, away, match_date)
            if not db_match:
                logger.debug(
                    f"[polymarket] No DB match for '{home} vs {away}' "
                    f"({match_date.date() if match_date else 'no date'})"
                )
                continue

            matched += 1
            url = f"https://polymarket.com/event/{slug}"
            all_odds: list[RawOdds] = []

            # 1X2 from main event
            all_odds.extend(self._extract_1x2(event, db_match.id, url))

            # More markets (spreads, O/U, BTTS)
            more_event = self._get_slug(f"{slug}-more-markets")
            if more_event:
                all_odds.extend(
                    self._extract_more_markets(more_event, home, away, db_match.id, url)
                )

            # Halftime result
            ht_event = self._get_slug(f"{slug}-halftime-result")
            if ht_event:
                all_odds.extend(self._extract_halftime(ht_event, db_match.id, url))

            if not all_odds:
                logger.debug(f"[polymarket] No odds extracted for '{home} vs {away}'")
                continue

            # Persist
            try:
                # Update match external_ids
                ext = dict(db_match.external_ids or {})
                ext["polymarket"] = slug
                db_match.external_ids = ext

                now = datetime.utcnow()
                for ro in all_odds:
                    snap = OddsSnapshot(
                        match_id=db_match.id,
                        bookmaker=self.BOOKMAKER,
                        market=ro.market,
                        selection=ro.selection,
                        odds=ro.odds,
                        url=ro.url,
                        scraped_at=now,
                    )
                    self._db.add(snap)

                self._db.commit()
                logger.info(
                    f"[polymarket] Saved {len(all_odds)} odds for "
                    f"'{db_match.home_team} vs {db_match.away_team}'"
                )
            except Exception:
                self._db.rollback()
                logger.exception(
                    f"[polymarket] Failed to save odds for '{home} vs {away}'"
                )

        logger.info(
            f"[polymarket] Done. Processed {processed} match events, "
            f"matched {matched} to DB."
        )
