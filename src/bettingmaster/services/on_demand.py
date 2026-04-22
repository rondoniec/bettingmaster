"""Small on-demand refresh hooks for user-opened match pages."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from bettingmaster.config import settings
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.scrapers.polymarket import PolymarketScraper

logger = logging.getLogger(__name__)


def refresh_polymarket_match_if_stale(db: Session, match: Match) -> int:
    """Refresh Polymarket prices for a match when the cached check is stale."""
    if not (match.external_ids or {}).get("polymarket"):
        return 0

    latest_checked_at = (
        db.query(func.max(func.coalesce(OddsSnapshot.checked_at, OddsSnapshot.scraped_at)))
        .filter(
            OddsSnapshot.match_id == match.id,
            OddsSnapshot.bookmaker == PolymarketScraper.BOOKMAKER,
        )
        .scalar()
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    max_age = timedelta(seconds=settings.on_demand_polymarket_max_age_seconds)
    if latest_checked_at and latest_checked_at >= now - max_age:
        return 0

    scraper = PolymarketScraper(db)
    try:
        return scraper.refresh_match(match)
    except Exception:
        db.rollback()
        logger.exception(
            "[polymarket] On-demand refresh failed for %s vs %s",
            match.home_team,
            match.away_team,
        )
        return 0
    finally:
        scraper.close()
