"""Odds history endpoint.

Returns the full chronological history of odds for a given match, optionally
filtered to a single market.  Each (market, selection) pair is returned as its
own group so the caller can render separate time-series charts per selection.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from bettingmaster.database import get_db
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.schemas.common import OddsHistoryOut, OddsHistoryPoint

router = APIRouter()


@router.get("/matches/{match_id}/history", response_model=list[OddsHistoryOut])
def get_odds_history(
    match_id: str,
    market: Optional[str] = Query(None, description="Filter to a specific market, e.g. '1x2'"),
    bookmakers: Optional[str] = Query(
        None,
        description="Comma-separated bookmaker ids, e.g. 'fortuna,nike'",
    ),
    db: Session = Depends(get_db),
):
    """Return the full odds history for a match, grouped by (market, selection).

    Each element in the returned list covers one (market, selection) combination
    and contains every scraped odds point in chronological order so clients can
    draw movement charts.
    """
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    q = (
        db.query(OddsSnapshot)
        .filter(OddsSnapshot.match_id == match_id)
        .order_by(
            OddsSnapshot.market,
            OddsSnapshot.selection,
            OddsSnapshot.scraped_at,
        )
    )

    if market:
        q = q.filter(OddsSnapshot.market == market)
    if bookmakers:
        bookmaker_list = [item.strip() for item in bookmakers.split(",") if item.strip()]
        q = q.filter(OddsSnapshot.bookmaker.in_(bookmaker_list))

    snapshots = q.all()

    if not snapshots:
        return []

    # Group by (market, selection) preserving chronological order
    groups: dict[tuple[str, str], list[OddsSnapshot]] = {}
    for snap in snapshots:
        key = (snap.market, snap.selection)
        groups.setdefault(key, []).append(snap)

    result: list[OddsHistoryOut] = []
    for (mkt, sel), snaps in groups.items():
        history = [
            OddsHistoryPoint(
                bookmaker=s.bookmaker,
                odds=s.odds,
                scraped_at=s.scraped_at,
            )
            for s in snaps
        ]
        result.append(
            OddsHistoryOut(
                market=mkt,
                selection=sel,
                history=history,
            )
        )

    return result
