"""Base scraper with rate limiting, retry, and persistence orchestration."""

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bettingmaster.match_identity import find_similar_match
from bettingmaster.models.match import Match
from bettingmaster.odds_writer import add_odds_snapshot
from bettingmaster.scope import is_match_in_active_scope

logger = logging.getLogger(__name__)


@dataclass
class RawMatch:
    external_id: str
    home_team: str
    away_team: str
    league_external_id: str
    start_time: datetime
    status: str = "prematch"
    url: Optional[str] = None


@dataclass
class RawOdds:
    match_external_id: str
    market: str
    selection: str
    odds: float
    url: Optional[str] = None


@dataclass
class ScraperRunSummary:
    matches_found: int = 0
    odds_saved: int = 0
    successful_steps: int = 0
    errors: int = 0
    last_error: str | None = None

    def mark_progress(self):
        self.successful_steps += 1

    def record_error(self, error: Exception | str):
        self.errors += 1
        message = str(error).strip()
        self.last_error = (message or error.__class__.__name__)[:500]

    def merge(self, other: "ScraperRunSummary"):
        self.matches_found += other.matches_found
        self.odds_saved += other.odds_saved
        self.successful_steps += other.successful_steps
        self.errors += other.errors
        if other.last_error:
            self.last_error = other.last_error[:500]

    @property
    def status(self) -> str:
        if self.errors and self.successful_steps:
            return "partial"
        if self.errors:
            return "failed"
        return "success"


def generate_match_id(league_id: str, home: str, away: str, start_date: str) -> str:
    """Deterministic match ID from content hash."""
    raw = f"{league_id}:{home}:{away}:{start_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class BaseScraper(ABC):
    BOOKMAKER: str = ""
    BASE_URL: str = ""
    REQUEST_DELAY: float = 1.0
    MAX_RETRIES: int = 3

    def __init__(self, db_session, http_client: httpx.Client | None = None):
        self._db = db_session
        self._client = http_client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Accept-Language": "sk-SK,sk;q=0.9,en;q=0.8",
            },
        )
        self._last_request_time: float = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)

    @retry(
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)
        ),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        self._rate_limit()
        self._last_request_time = time.time()
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    @abstractmethod
    def scrape_matches(self, league_external_id: str) -> list[RawMatch]:
        """Scrape matches for a league. Returns raw match data."""
        ...

    @abstractmethod
    def scrape_odds(self, match_external_id: str) -> list[RawOdds]:
        """Scrape odds for a single match. Returns raw odds data."""
        ...

    def scrape_odds_for_raw_match(self, raw_match: RawMatch) -> list[RawOdds]:
        """Scrape odds for a discovered raw match.

        Scrapers that need additional match context beyond the external ID
        can override this hook.
        """
        return self.scrape_odds(raw_match.external_id)

    def run(self, league_ids: dict[str, str], normalizer=None) -> ScraperRunSummary:
        """
        Main entry point. Scrape matches and odds for the given leagues.

        Args:
            league_ids: dict of {our_league_id: bookmaker_league_external_id}
            normalizer: optional TeamNormalizer instance
        """
        summary = ScraperRunSummary()
        for league_id, ext_id in league_ids.items():
            try:
                summary.merge(self._scrape_league(league_id, ext_id, normalizer))
            except Exception as exc:
                summary.record_error(exc)
                logger.exception(
                    f"[{self.BOOKMAKER}] Failed to scrape league {league_id}"
                )
        return summary

    def _scrape_league(self, league_id: str, ext_id: str, normalizer) -> ScraperRunSummary:
        summary = ScraperRunSummary()
        raw_matches = self.scrape_matches(ext_id)
        summary.mark_progress()
        logger.info(
            f"[{self.BOOKMAKER}] Found {len(raw_matches)} matches in {league_id}"
        )

        for rm in raw_matches:
            try:
                if not is_match_in_active_scope(league_id, rm.start_time):
                    continue
                home = rm.home_team
                away = rm.away_team
                if normalizer:
                    home = normalizer.normalize(home, self.BOOKMAKER) or home
                    away = normalizer.normalize(away, self.BOOKMAKER) or away

                match_id = generate_match_id(
                    league_id, home, away, rm.start_time.strftime("%Y-%m-%d")
                )
                existing_match = find_similar_match(
                    self._db,
                    league_id,
                    home,
                    away,
                    rm.start_time,
                )
                if existing_match is not None:
                    match_id = existing_match.id
                    home = existing_match.home_team
                    away = existing_match.away_team

                summary.matches_found += 1

                match = self._db.get(Match, match_id)
                if match is None:
                    match = Match(
                        id=match_id,
                        league_id=league_id,
                        home_team=home,
                        away_team=away,
                        start_time=rm.start_time,
                        status=rm.status,
                        external_ids={self.BOOKMAKER: rm.external_id},
                    )
                    self._db.add(match)
                else:
                    ext = dict(match.external_ids or {})
                    ext[self.BOOKMAKER] = rm.external_id
                    match.external_ids = ext
                    match.status = rm.status

                self._db.flush()

                raw_odds = self.scrape_odds(rm.external_id)
                now = datetime.utcnow()
                for ro in raw_odds:
                    add_odds_snapshot(
                        self._db,
                        match_id=match_id,
                        bookmaker=self.BOOKMAKER,
                        market=ro.market,
                        selection=ro.selection,
                        odds=ro.odds,
                        url=ro.url,
                        scraped_at=now,
                    )

                self._db.commit()
                summary.odds_saved += len(raw_odds)
                summary.mark_progress()
                logger.debug(
                    f"[{self.BOOKMAKER}] Saved {len(raw_odds)} odds for "
                    f"{home} vs {away}"
                )

            except Exception as exc:
                self._db.rollback()
                summary.record_error(exc)
                logger.exception(
                    f"[{self.BOOKMAKER}] Failed match {rm.home_team} vs {rm.away_team}"
                )

        return summary

    def close(self):
        self._client.close()
