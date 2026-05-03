"""Polymarket odds ingestion using Gamma discovery plus public CLOB pricing."""

from __future__ import annotations

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
from bettingmaster.odds_writer import add_odds_snapshot
from bettingmaster.scrapers.base import BaseScraper, RawOdds
from bettingmaster.scope import apply_active_match_scope

logger = logging.getLogger(__name__)

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
DEBUG_DIR = DATA_DIR / "debug"

_SPREAD_RE = re.compile(r"Spread:\s*(.+?)\s*\(([+-]?\d+\.5)\)", re.IGNORECASE)
_TOTAL_RE = re.compile(r"O/U\s+(\d+\.5)|(\d+\.5)\s+O/U", re.IGNORECASE)
_BTTS_RE = re.compile(r"both teams (to )?score", re.IGNORECASE)
_PROTECTED_EXTRA_TOKENS = {"sc", "sporting"}


def _normalize(value: str) -> str:
    """Lowercase and strip accents so 'Atletico' and 'Atlético' compare cleanly."""
    return unicodedata.normalize("NFD", value.lower()).encode("ascii", "ignore").decode()


def _normalize_team_for_match(value: str) -> str:
    normalized = _normalize(value)
    normalized = re.sub(r"\b(fc|cf|afc)\b", " ", normalized)
    normalized = re.sub(r"\b(18|19|20)\d{2}\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _team_similarity(left: str, right: str) -> float:
    """Return a 0..1 fuzzy similarity score between two team names."""
    left_key = _normalize_team_for_match(left)
    right_key = _normalize_team_for_match(right)
    if _has_protected_extra_token(left_key, right_key):
        return 0.0
    return fuzz.WRatio(left_key, right_key) / 100.0


def _has_protected_extra_token(left_key: str, right_key: str) -> bool:
    if left_key == right_key:
        return False
    left_tokens = set(left_key.split())
    right_tokens = set(right_key.split())
    if not left_tokens or not right_tokens:
        return False
    if right_tokens < left_tokens:
        return bool((left_tokens - right_tokens) & _PROTECTED_EXTRA_TOKENS)
    if left_tokens < right_tokens:
        return bool((right_tokens - left_tokens) & _PROTECTED_EXTRA_TOKENS)
    return False


def _team_pair_score(
    home: str,
    away: str,
    candidate_home: str,
    candidate_away: str,
) -> tuple[float, bool]:
    normal_home = _team_similarity(home, candidate_home)
    normal_away = _team_similarity(away, candidate_away)
    swapped_home = _team_similarity(home, candidate_away)
    swapped_away = _team_similarity(away, candidate_home)

    normal_score = normal_home + normal_away if min(normal_home, normal_away) >= 0.9 else 0.0
    swapped_score = swapped_home + swapped_away if min(swapped_home, swapped_away) >= 0.9 else 0.0
    if swapped_score > normal_score:
        return swapped_score, True
    return normal_score, False


def _prob_to_decimal(prob: float) -> Optional[float]:
    """Convert a 0..1 probability into decimal odds.

    Polymarket order books often have sparse asks at the long-tail end of a
    market (a single 1¢ resting offer turns into 100.00 decimal odds and
    nukes any margin comparison). Reject anything below 4¢ (= 25.0 odds)
    so we don't poison the comparison with non-executable noise.
    """
    if prob is None or prob <= 0.04 or prob > 1:
        return None
    return round(1.0 / prob, 3)


def _parse_outcomes(market: dict) -> tuple[list[str], list[float]]:
    """Return (outcomes, probabilities) from a Gamma market object."""
    raw_outcomes = market.get("outcomes", "[]")
    raw_prices = market.get("outcomePrices", "[]")
    try:
        outcomes = json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else list(raw_outcomes)
        prices_raw = json.loads(raw_prices) if isinstance(raw_prices, str) else list(raw_prices)
        prices = [float(price) for price in prices_raw]
    except Exception:
        return [], []
    return outcomes, prices


def _line_key(line: str) -> str:
    """Convert '2.5' to '2_5' for market keys like over_under_2_5."""
    return line.replace(".", "_")


class PolymarketScraper(BaseScraper):
    """Fetch football odds from Polymarket's public APIs."""

    BOOKMAKER = "polymarket"
    BASE_URL = GAMMA_API
    REQUEST_DELAY = 0.8

    def __init__(self, db_session, http_client: httpx.Client | None = None):
        super().__init__(db_session, http_client)

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        response = self._request("GET", f"{GAMMA_API}{path}", params=params)
        return response.json()

    def _post_clob(self, path: str, payload: list[dict]) -> dict | list:
        response = self._request("POST", f"{CLOB_API}{path}", json=payload)
        return response.json()

    def _get_slug(self, slug: str) -> Optional[dict]:
        """Fetch a single Gamma event by slug. Returns None on 404."""
        url = f"{GAMMA_API}/events/slug/{slug}"
        self._rate_limit()
        self._last_request_time = __import__("time").time()
        try:
            response = self._client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.debug(f"[polymarket] Slug '{slug}' HTTP {exc.response.status_code}")
            return None
        except Exception as exc:
            logger.debug(f"[polymarket] Slug '{slug}' error: {exc}")
            return None

    def _dump_debug(self, name: str, data):
        if not settings.debug_dump:
            return
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = DEBUG_DIR / f"polymarket_{name}_{timestamp}.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
        logger.info(f"[polymarket] Debug dump: {path}")

    def _parse_clob_token_ids(self, market: dict) -> list[str]:
        raw = market.get("clobTokenIds", "[]")
        if not raw:
            return []

        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            if isinstance(raw, str) and "," in raw:
                parsed = [part.strip() for part in raw.split(",")]
            elif isinstance(raw, str):
                parsed = [raw]
            else:
                return []

        if isinstance(parsed, str):
            return [parsed]
        if isinstance(parsed, (list, tuple)):
            return [str(token_id) for token_id in parsed if token_id]
        return []

    def _fetch_clob_midpoints(self, token_ids: list[str]) -> dict[str, float]:
        if not token_ids:
            return {}

        try:
            response = self._post_clob(
                "/midpoints",
                [{"token_id": token_id} for token_id in token_ids],
            )
        except Exception as exc:
            logger.warning(f"[polymarket] Failed to fetch CLOB midpoints: {exc}")
            return {}

        prices: dict[str, float] = {}
        if isinstance(response, dict):
            for token_id, price in response.items():
                try:
                    prices[str(token_id)] = float(price)
                except (TypeError, ValueError):
                    continue
        return prices

    def _fetch_clob_ask_prices(self, token_ids: list[str]) -> dict[str, float]:
        """Best ask (price a user pays to BUY the outcome token).

        Polymarket CLOB semantics:
          side=BUY  -> the BUY side of the book (= bids = orders to buy)
          side=SELL -> the SELL side (= asks = orders to sell)

        A user who wants to BUY a YES contract has to MATCH a sell order,
        so they pay the ASK price. That maps to `side: SELL` here, even
        though it reads counter-intuitively.
        """
        if not token_ids:
            return {}

        try:
            response = self._post_clob(
                "/prices",
                [{"token_id": token_id, "side": "SELL"} for token_id in token_ids],
            )
        except Exception as exc:
            logger.warning(f"[polymarket] Failed to fetch CLOB ask prices: {exc}")
            return {}

        prices: dict[str, float] = {}
        if isinstance(response, dict):
            for token_id, row in response.items():
                try:
                    if isinstance(row, dict):
                        raw_price = row.get("SELL") or row.get("BUY")
                    else:
                        raw_price = row
                    if raw_price is not None:
                        prices[str(token_id)] = float(raw_price)
                except (TypeError, ValueError):
                    continue
        return prices

    def _fetch_clob_last_trades(self, token_ids: list[str]) -> dict[str, float]:
        if not token_ids:
            return {}

        try:
            response = self._post_clob(
                "/last-trades-prices",
                [{"token_id": token_id} for token_id in token_ids],
            )
        except Exception as exc:
            logger.warning(f"[polymarket] Failed to fetch CLOB last trades: {exc}")
            return {}

        prices: dict[str, float] = {}
        if isinstance(response, list):
            for row in response:
                if not isinstance(row, dict):
                    continue
                token_id = row.get("token_id")
                if not token_id:
                    continue
                try:
                    prices[str(token_id)] = float(row["price"])
                except (KeyError, TypeError, ValueError):
                    continue
        return prices

    def _fetch_clob_prices(self, token_ids: list[str]) -> dict[str, float]:
        # For betting comparison we need executable odds. The user's price to
        # ENTER a position is the best ask (lowest sell-side offer). Fall
        # back to midpoint, then last-trade, only when the live ask is gone.
        prices = self._fetch_clob_ask_prices(token_ids)
        missing = [token_id for token_id in token_ids if token_id not in prices]
        if missing:
            prices.update(self._fetch_clob_midpoints(missing))
            missing = [token_id for token_id in token_ids if token_id not in prices]
        if missing:
            prices.update(self._fetch_clob_last_trades(missing))
        return prices

    def _collect_clob_token_ids(self, *events: Optional[dict]) -> list[str]:
        token_ids: list[str] = []
        seen: set[str] = set()

        for event in events:
            if not event:
                continue
            for market in event.get("markets", []):
                for token_id in self._parse_clob_token_ids(market):
                    if token_id in seen:
                        continue
                    seen.add(token_id)
                    token_ids.append(token_id)

        return token_ids

    def _parse_market_probabilities(
        self,
        market: dict,
        clob_prices: dict[str, float] | None = None,
    ) -> tuple[list[str], list[float]]:
        outcomes, prices = _parse_outcomes(market)
        if not prices:
            return outcomes, prices

        if clob_prices:
            token_ids = self._parse_clob_token_ids(market)
            for idx, token_id in enumerate(token_ids):
                price = clob_prices.get(token_id)
                if price is None:
                    continue
                if idx < len(prices):
                    prices[idx] = price
                else:
                    prices.append(price)

        return outcomes, prices

    # ------------------------------------------------------------------
    # Event discovery and DB matching
    # ------------------------------------------------------------------

    def _fetch_all_soccer_events(self) -> list[dict]:
        all_events: list[dict] = []
        offset = 0
        limit = 100
        max_pages = 20

        for _ in range(max_pages):
            try:
                result = self._get(
                    "/events/pagination",
                    params={
                        "tag_slug": "soccer",
                        "active": "true",
                        "closed": "false",
                        "limit": limit,
                        "order": "startDate",
                        "ascending": "false",
                        "offset": offset,
                    },
                )
            except Exception as exc:
                logger.error(f"[polymarket] Pagination fetch failed (offset={offset}): {exc}")
                break

            data = result.get("data", []) if isinstance(result, dict) else []
            if not data:
                break

            all_events.extend(data)
            offset += limit

            if len(data) < limit:
                break

        logger.info(f"[polymarket] Fetched {len(all_events)} active soccer events")
        return all_events

    def _is_match_event(self, event: dict) -> bool:
        slug = event.get("slug", "")
        if slug.endswith("-more-markets") or slug.endswith("-halftime-result"):
            return False

        markets = event.get("markets", [])
        if len(markets) != 3:
            return False

        titles = [market.get("groupItemTitle", "") for market in markets]
        return any("draw" in title.lower() for title in titles)

    def _parse_team_names(self, event: dict) -> tuple[str, str]:
        markets = event.get("markets", [])
        if len(markets) != 3:
            return "", ""

        non_draw = [
            market.get("groupItemTitle", "")
            for market in markets
            if "draw" not in market.get("groupItemTitle", "").lower()
        ]
        if len(non_draw) < 2:
            return "", ""

        return non_draw[0].strip(), non_draw[1].strip()

    def _parse_match_date(self, event: dict) -> Optional[datetime]:
        raw = event.get("startDate") or event.get("endDate")
        if not raw:
            return None

        for fmt in (
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(raw[: len(fmt)], fmt)
            except ValueError:
                continue
        return None

    def _find_db_match(
        self,
        home: str,
        away: str,
        match_date: Optional[datetime],
    ) -> Optional[Match]:
        query = apply_active_match_scope(self._db.query(Match))

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
        best_match: Optional[Match] = None

        for candidate in candidates:
            final_score, _ = _team_pair_score(
                home,
                away,
                candidate.home_team,
                candidate.away_team,
            )
            if final_score > best_score:
                best_score = final_score
                best_match = candidate

        if best_score >= 1.8 and best_match:
            logger.debug(
                f"[polymarket] Matched '{home} vs {away}' -> "
                f"'{best_match.home_team} vs {best_match.away_team}' (score={best_score:.2f})"
            )
            return best_match

        logger.debug(
            f"[polymarket] No DB match for '{home} vs {away}' "
            f"(best_score={best_score:.2f}, candidates={len(candidates)})"
        )
        return None

    def _selection_for_team(self, team_name: str, match: Match) -> Optional[str]:
        """Map a Polymarket team label to our canonical home/away selection."""
        home_score = _team_similarity(team_name, match.home_team)
        away_score = _team_similarity(team_name, match.away_team)
        if max(home_score, away_score) < 0.9:
            return None
        return "home" if home_score >= away_score else "away"

    # ------------------------------------------------------------------
    # Odds extraction
    # ------------------------------------------------------------------

    def _extract_1x2(
        self,
        event: dict,
        match: Match,
        url: str,
        clob_prices: dict[str, float],
    ) -> list[RawOdds]:
        markets = event.get("markets", [])
        if len(markets) != 3:
            return []

        result: list[RawOdds] = []
        for market in markets:
            title = market.get("groupItemTitle", "").lower()
            _, prices = self._parse_market_probabilities(market, clob_prices)
            if not prices:
                continue

            decimal_odds = _prob_to_decimal(prices[0])
            if not decimal_odds or not (1.01 <= decimal_odds <= 500):
                continue

            if "draw" in title:
                selection = "draw"
            else:
                selection = self._selection_for_team(
                    market.get("groupItemTitle", ""),
                    match,
                )
                if selection is None:
                    continue

            result.append(
                RawOdds(
                    match_external_id=match.id,
                    market="1x2",
                    selection=selection,
                    odds=decimal_odds,
                    url=url,
                )
            )

        return result

    def _extract_more_markets(
        self,
        event: dict,
        match: Match,
        url: str,
        clob_prices: dict[str, float],
    ) -> list[RawOdds]:
        result: list[RawOdds] = []

        for market in event.get("markets", []):
            question = market.get("question", "") or market.get("groupItemTitle", "")
            outcomes, prices = self._parse_market_probabilities(market, clob_prices)
            if not outcomes or not prices:
                continue

            spread_match = _SPREAD_RE.search(question)
            if spread_match:
                favored_team = spread_match.group(1).strip()
                line_abs = spread_match.group(2).lstrip("+-")
                market_key = f"handicap_{_line_key(line_abs)}"

                favored_selection = self._selection_for_team(favored_team, match)
                if favored_selection is None:
                    continue

                other_selection = "away" if favored_selection == "home" else "home"
                pairs = [(favored_selection, prices[0]), (other_selection, prices[1])]

                for selection, probability in pairs:
                    decimal_odds = _prob_to_decimal(probability)
                    if decimal_odds and 1.01 <= decimal_odds <= 500:
                        result.append(
                            RawOdds(
                                match_external_id=match.id,
                                market=market_key,
                                selection=selection,
                                odds=decimal_odds,
                                url=url,
                            )
                        )
                continue

            totals_match = _TOTAL_RE.search(question)
            if totals_match:
                line = totals_match.group(1) or totals_match.group(2)
                market_key = f"over_under_{_line_key(line)}"

                for outcome, probability in zip(outcomes, prices):
                    outcome_lower = outcome.lower()
                    if "over" in outcome_lower:
                        selection = "over"
                    elif "under" in outcome_lower:
                        selection = "under"
                    else:
                        continue

                    decimal_odds = _prob_to_decimal(probability)
                    if decimal_odds and 1.01 <= decimal_odds <= 500:
                        result.append(
                            RawOdds(
                                match_external_id=match.id,
                                market=market_key,
                                selection=selection,
                                odds=decimal_odds,
                                url=url,
                            )
                        )
                continue

            if _BTTS_RE.search(question):
                for outcome, probability in zip(outcomes, prices):
                    outcome_lower = outcome.lower()
                    if "yes" in outcome_lower:
                        selection = "yes"
                    elif "no" in outcome_lower:
                        selection = "no"
                    else:
                        continue

                    decimal_odds = _prob_to_decimal(probability)
                    if decimal_odds and 1.01 <= decimal_odds <= 500:
                        result.append(
                            RawOdds(
                                match_external_id=match.id,
                                market="btts",
                                selection=selection,
                                odds=decimal_odds,
                                url=url,
                            )
                        )

        return result

    def _extract_halftime(
        self,
        event: dict,
        match: Match,
        url: str,
        clob_prices: dict[str, float],
    ) -> list[RawOdds]:
        markets = event.get("markets", [])
        if len(markets) != 3:
            return []

        result: list[RawOdds] = []
        for market in markets:
            title = market.get("groupItemTitle", "").lower()
            _, prices = self._parse_market_probabilities(market, clob_prices)
            if not prices:
                continue

            decimal_odds = _prob_to_decimal(prices[0])
            if not decimal_odds or not (1.01 <= decimal_odds <= 500):
                continue

            if "draw" in title:
                selection = "draw"
            else:
                selection = self._selection_for_team(
                    market.get("groupItemTitle", ""),
                    match,
                )
                if selection is None:
                    continue

            result.append(
                RawOdds(
                    match_external_id=match.id,
                    market="1x2_ht",
                    selection=selection,
                    odds=decimal_odds,
                    url=url,
                )
            )

        return result

    def _extract_event_bundle(self, slug: str, event: dict, match: Match) -> list[RawOdds]:
        url = f"https://polymarket.com/event/{slug}"
        more_event = self._get_slug(f"{slug}-more-markets")
        halftime_event = self._get_slug(f"{slug}-halftime-result")
        clob_prices = self._fetch_clob_prices(
            self._collect_clob_token_ids(event, more_event, halftime_event)
        )

        all_odds: list[RawOdds] = []
        all_odds.extend(self._extract_1x2(event, match, url, clob_prices))

        if more_event:
            all_odds.extend(
                self._extract_more_markets(
                    more_event,
                    match,
                    url,
                    clob_prices,
                )
            )

        if halftime_event:
            all_odds.extend(
                self._extract_halftime(
                    halftime_event,
                    match,
                    url,
                    clob_prices,
                )
            )

        return all_odds

    # ------------------------------------------------------------------
    # Required abstract methods (unused; run() is overridden)
    # ------------------------------------------------------------------

    def scrape_matches(self, league_external_id: str) -> list:
        return []

    def scrape_odds(self, match_external_id: str) -> list[RawOdds]:
        return []

    def refresh_match(self, match: Match) -> int:
        """Refresh a previously matched Polymarket event for one DB match."""
        slug = (match.external_ids or {}).get("polymarket")
        if not slug:
            return 0

        event = self._get_slug(slug)
        if not event or not self._is_match_event(event):
            return 0

        home, away = self._parse_team_names(event)
        score, _ = _team_pair_score(home, away, match.home_team, match.away_team)
        if score < 1.8:
            self._db.query(OddsSnapshot).filter_by(
                match_id=match.id,
                bookmaker=self.BOOKMAKER,
            ).delete(synchronize_session=False)
            ext = dict(match.external_ids or {})
            ext.pop("polymarket", None)
            match.external_ids = ext
            self._db.commit()
            logger.warning(
                "[polymarket] Removed mismatched event '%s' from %s vs %s during refresh",
                slug,
                match.home_team,
                match.away_team,
            )
            return 0

        all_odds = self._extract_event_bundle(slug, event, match)
        if not all_odds:
            return 0

        now = datetime.utcnow()
        for raw_odds in all_odds:
            add_odds_snapshot(
                self._db,
                match_id=match.id,
                bookmaker=self.BOOKMAKER,
                market=raw_odds.market,
                selection=raw_odds.selection,
                odds=raw_odds.odds,
                url=raw_odds.url,
                scraped_at=now,
            )

        self._db.commit()
        logger.info(
            "[polymarket] Refreshed %s odds for %s vs %s",
            len(all_odds),
            match.home_team,
            match.away_team,
        )
        return len(all_odds)

    def _prune_mismatched_existing_events(self):
        matches = apply_active_match_scope(self._db.query(Match)).all()
        for match in matches:
            slug = (match.external_ids or {}).get("polymarket")
            if not slug:
                continue

            event = self._get_slug(slug)
            if not event or not self._is_match_event(event):
                continue

            home, away = self._parse_team_names(event)
            score, _ = _team_pair_score(home, away, match.home_team, match.away_team)
            if score >= 1.8:
                continue

            self._db.query(OddsSnapshot).filter_by(
                match_id=match.id,
                bookmaker=self.BOOKMAKER,
            ).delete(synchronize_session=False)
            ext = dict(match.external_ids or {})
            ext.pop("polymarket", None)
            match.external_ids = ext
            logger.warning(
                "[polymarket] Removed mismatched event '%s' from %s vs %s",
                slug,
                match.home_team,
                match.away_team,
            )
        self._db.commit()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, league_ids: dict | None = None, normalizer=None):
        self._prune_mismatched_existing_events()
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
            all_odds = self._extract_event_bundle(slug, event, db_match)

            if not all_odds:
                logger.debug(f"[polymarket] No odds extracted for '{home} vs {away}'")
                continue

            try:
                ext = dict(db_match.external_ids or {})
                ext["polymarket"] = slug
                db_match.external_ids = ext

                now = datetime.utcnow()
                for raw_odds in all_odds:
                    add_odds_snapshot(
                        self._db,
                        match_id=db_match.id,
                        bookmaker=self.BOOKMAKER,
                        market=raw_odds.market,
                        selection=raw_odds.selection,
                        odds=raw_odds.odds,
                        url=raw_odds.url,
                        scraped_at=now,
                    )

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
            f"[polymarket] Done. Processed {processed} match events, matched {matched} to DB."
        )
