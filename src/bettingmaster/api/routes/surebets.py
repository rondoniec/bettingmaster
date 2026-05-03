"""Surebet detection endpoint.

A surebet (arbitrage) exists when the sum of reciprocal best odds across all
selections in a market is less than 1, meaning a guaranteed profit is possible
by backing all outcomes at different bookmakers.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from bettingmaster.database import get_db
from bettingmaster.schemas.common import SurebetOut
from bettingmaster.services.odds import SUREBET_MAX_AGE_HOURS, build_surebets, query_upcoming_latest_odds

router = APIRouter()


@router.get("/surebets", response_model=list[SurebetOut])
def list_surebets(
    sport: Optional[str] = Query(None, description="Filter by sport id, e.g. 'football'"),
    min_profit: float = Query(0.0, description="Minimum profit percentage (0 = all surebets)"),
    market: Optional[str] = Query(None, description="Filter to a single market, e.g. '1x2'"),
    bookmakers: Optional[str] = Query(
        None,
        description="Comma-separated bookmaker ids, e.g. 'fortuna,nike'",
    ),
    db: Session = Depends(get_db),
):
    """Return all current surebets sorted by profit (most profitable first).

    Only considers matches that are not finished and haven't started yet
    (start_time > now). A surebet is any market where the sum of (1/best_odds)
    across all selections is < 1.
    """
    bookmaker_list = [item.strip() for item in bookmakers.split(",") if item.strip()] if bookmakers else None
    rows = query_upcoming_latest_odds(db, sport=sport, max_age_hours=SUREBET_MAX_AGE_HOURS).all()
    return build_surebets(
        rows,
        min_profit=min_profit,
        market_filter=market,
        bookmakers=bookmaker_list,
    )
