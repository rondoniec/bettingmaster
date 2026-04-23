"""On-demand refresh hooks for user-opened match pages."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from bettingmaster.config import settings
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.odds_writer import add_odds_snapshot
from bettingmaster.scrapers.base import RawMatch
from bettingmaster.scrapers.doxxbet import DoxxbetScraper
from bettingmaster.scrapers.fortuna import FortunaScraper
from bettingmaster.scrapers.nike import NikeScraper
from bettingmaster.scrapers.polymarket import PolymarketScraper
from bettingmaster.scrapers.tipos import TiposScraper
from bettingmaster.scrapers.tipsport import TipsportScraper

logger = logging.getLogger(__name__)

_SUPPORTED_BOOKMAKERS = (
    "fortuna",
    "doxxbet",
    "nike",
    "tipos",
    "tipsport",
    "polymarket",
)

_MAX_AGE_ATTRS = {
    "fortuna": "on_demand_fortuna_max_age_seconds",
    "doxxbet": "on_demand_doxxbet_max_age_seconds",
    "nike": "on_demand_nike_max_age_seconds",
    "tipos": "on_demand_tipos_max_age_seconds",
    "tipsport": "on_demand_tipsport_max_age_seconds",
    "polymarket": "on_demand_polymarket_max_age_seconds",
}


def _latest_checked_at(db: Session, match_id: str, bookmaker: str):
    return (
        db.query(func.max(func.coalesce(OddsSnapshot.checked_at, OddsSnapshot.scraped_at)))
        .filter(
            OddsSnapshot.match_id == match_id,
            OddsSnapshot.bookmaker == bookmaker,
        )
        .scalar()
    )


def _latest_outcome_url(
    db: Session,
    *,
    match_id: str,
    bookmaker: str,
    market: str,
    selection: str,
) -> str | None:
    row = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.match_id == match_id,
            OddsSnapshot.bookmaker == bookmaker,
            OddsSnapshot.market == market,
            OddsSnapshot.selection == selection,
            OddsSnapshot.url.isnot(None),
        )
        .order_by(
            func.coalesce(OddsSnapshot.checked_at, OddsSnapshot.scraped_at).desc(),
            OddsSnapshot.id.desc(),
        )
        .first()
    )
    return row.url if row else None


def _bookmaker_url(db: Session, match_id: str, bookmaker: str) -> str | None:
    row = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.match_id == match_id,
            OddsSnapshot.bookmaker == bookmaker,
            OddsSnapshot.url.isnot(None),
        )
        .order_by(
            func.coalesce(OddsSnapshot.checked_at, OddsSnapshot.scraped_at).desc(),
            OddsSnapshot.id.desc(),
        )
        .first()
    )
    return row.url if row else None


def _league_external_id(match: Match, bookmaker: str) -> str | None:
    league = match.league
    if league is None:
        return None
    external_ids = league.external_ids or {}
    ext_id = external_ids.get(bookmaker)
    return str(ext_id) if ext_id else None


def _should_refresh(db: Session, match: Match, bookmaker: str) -> bool:
    latest_checked_at = _latest_checked_at(db, match.id, bookmaker)
    if latest_checked_at is None:
        return True

    now = datetime.now(UTC).replace(tzinfo=None)
    max_age_attr = _MAX_AGE_ATTRS[bookmaker]
    max_age = timedelta(seconds=getattr(settings, max_age_attr))
    return latest_checked_at < now - max_age


def _persist_refreshed_odds(db: Session, match: Match, bookmaker: str, raw_odds) -> int:
    if not raw_odds:
        return 0

    now = datetime.now(UTC).replace(tzinfo=None)
    for raw_odds_row in raw_odds:
        url = raw_odds_row.url or _latest_outcome_url(
            db,
            match_id=match.id,
            bookmaker=bookmaker,
            market=raw_odds_row.market,
            selection=raw_odds_row.selection,
        )
        add_odds_snapshot(
            db,
            match_id=match.id,
            bookmaker=bookmaker,
            market=raw_odds_row.market,
            selection=raw_odds_row.selection,
            odds=raw_odds_row.odds,
            url=url,
            scraped_at=now,
        )
    db.commit()
    logger.info(
        "[%s] On-demand refreshed %s odds for %s vs %s",
        bookmaker,
        len(raw_odds),
        match.home_team,
        match.away_team,
    )
    return len(raw_odds)


def _refresh_standard_scraper(db: Session, match: Match, bookmaker: str, scraper_cls) -> int:
    external_id = (match.external_ids or {}).get(bookmaker)
    if not external_id:
        return 0

    scraper = scraper_cls(db)
    try:
        raw_odds = scraper.scrape_odds(str(external_id))
        return _persist_refreshed_odds(db, match, bookmaker, raw_odds)
    finally:
        scraper.close()


def _refresh_raw_match_scraper(db: Session, match: Match, bookmaker: str, scraper_cls) -> int:
    external_id = (match.external_ids or {}).get(bookmaker)
    league_external_id = _league_external_id(match, bookmaker)
    if not external_id or not league_external_id:
        return 0

    raw_match = RawMatch(
        external_id=str(external_id),
        home_team=match.home_team,
        away_team=match.away_team,
        league_external_id=league_external_id,
        start_time=match.start_time,
        status=match.status,
        url=_bookmaker_url(db, match.id, bookmaker),
    )

    scraper = scraper_cls(db)
    try:
        raw_odds = scraper.scrape_odds_for_raw_match(raw_match)
        return _persist_refreshed_odds(db, match, bookmaker, raw_odds)
    finally:
        scraper.close()


def _refresh_polymarket(db: Session, match: Match) -> int:
    if not (match.external_ids or {}).get("polymarket"):
        return 0

    scraper = PolymarketScraper(db)
    try:
        return scraper.refresh_match(match)
    finally:
        scraper.close()


def refresh_match_odds_if_stale(
    db: Session,
    match: Match,
    *,
    requested_bookmakers: list[str] | None = None,
) -> int:
    """Refresh stale bookmaker odds when a user opens a match page."""
    total = 0
    requested = {bookmaker.strip() for bookmaker in (requested_bookmakers or []) if bookmaker.strip()}
    bookmakers = [
        bookmaker
        for bookmaker in _SUPPORTED_BOOKMAKERS
        if not requested or bookmaker in requested
    ]

    for bookmaker in bookmakers:
        if not (match.external_ids or {}).get(bookmaker):
            continue
        if not _should_refresh(db, match, bookmaker):
            continue

        try:
            if bookmaker == "polymarket":
                total += _refresh_polymarket(db, match)
            elif bookmaker == "nike":
                total += _refresh_raw_match_scraper(db, match, bookmaker, NikeScraper)
            elif bookmaker == "doxxbet":
                total += _refresh_raw_match_scraper(db, match, bookmaker, DoxxbetScraper)
            elif bookmaker == "fortuna":
                total += _refresh_standard_scraper(db, match, bookmaker, FortunaScraper)
            elif bookmaker == "tipos":
                total += _refresh_standard_scraper(db, match, bookmaker, TiposScraper)
            elif bookmaker == "tipsport":
                total += _refresh_standard_scraper(db, match, bookmaker, TipsportScraper)
        except Exception:
            db.rollback()
            logger.exception(
                "[%s] On-demand refresh failed for %s vs %s",
                bookmaker,
                match.home_team,
                match.away_team,
            )

    return total


def refresh_polymarket_match_if_stale(db: Session, match: Match) -> int:
    """Backward-compatible wrapper for older callers/tests."""
    return refresh_match_odds_if_stale(db, match, requested_bookmakers=["polymarket"])
