from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from bettingmaster.database import get_db
from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.schemas.common import (
    BestOddsOut,
    MatchDetailOut,
    MatchBestOddsOut,
    MatchOut,
    OddsOut,
)
from bettingmaster.services.odds import (
    build_best_odds,
    latest_odds_for_match,
    list_best_odds_matches,
    resolve_bookmaker_url,
    resolve_date_filter,
    utc_day_bounds_for_local_date,
)

router = APIRouter()


@router.get("/leagues/{league_id}/matches", response_model=list[MatchOut])
def list_matches(
    league_id: str,
    day: date | None = Query(None, alias="date", description="Filter by date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    q = db.query(Match).filter(Match.league_id == league_id)
    if day:
        q = q.filter(
            Match.start_time >= datetime.combine(day, datetime.min.time()),
            Match.start_time < datetime.combine(day, datetime.max.time()),
        )
    return q.order_by(Match.start_time).all()


@router.get("/matches", response_model=list[MatchOut])
def list_all_matches(
    date_filter: str | None = Query(
        None,
        alias="date",
        description="Date filter: 'today' (default), 'tomorrow', or ISO date YYYY-MM-DD",
    ),
    sport: str | None = Query(None, description="Filter by sport id, e.g. 'football'"),
    status: str | None = Query(None, description="Filter by match status, e.g. 'prematch', 'live'"),
    db: Session = Depends(get_db),
):
    """Return matches across all leagues for a given day (default: today).

    Optionally filter by sport and/or status.
    """
    try:
        target_date = resolve_date_filter(date_filter)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid date format '{date_filter}'. "
                "Use 'today', 'tomorrow', or 'YYYY-MM-DD'."
            ),
        )

    day_start, day_end = utc_day_bounds_for_local_date(target_date)

    q = (
        db.query(Match)
        .filter(
            Match.start_time >= day_start,
            Match.start_time <= day_end,
        )
    )

    if sport:
        q = q.join(League, Match.league_id == League.id).filter(League.sport_id == sport)

    if status:
        q = q.filter(Match.status == status)

    return q.order_by(Match.start_time).all()


@router.get("/matches/best-odds", response_model=list[MatchBestOddsOut])
def list_matches_with_best_odds(
    date_filter: str | None = Query(
        None,
        alias="date",
        description="Date filter: 'today' (default), 'tomorrow', or ISO date YYYY-MM-DD",
    ),
    market: str = Query("1x2", description="Market to compare, e.g. '1x2'"),
    sport: str | None = Query(None, description="Filter by sport id, e.g. 'football'"),
    league_id: str | None = Query(None, description="Filter by league id"),
    status: str | None = Query(None, description="Filter by match status, e.g. 'prematch', 'live'"),
    bookmakers: str | None = Query(
        None,
        description="Comma-separated bookmaker ids, e.g. 'fortuna,nike'",
    ),
    min_bookmakers: int = Query(2, ge=1, le=20, description="Minimum bookmakers required"),
    db: Session = Depends(get_db),
):
    try:
        target_date = resolve_date_filter(date_filter)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid date format '{date_filter}'. "
                "Use 'today', 'tomorrow', or 'YYYY-MM-DD'."
            ),
        )

    bookmaker_list = [item.strip() for item in bookmakers.split(",") if item.strip()] if bookmakers else None
    return list_best_odds_matches(
        db,
        target_date=target_date,
        market=market,
        sport=sport,
        league_id=league_id,
        status=status,
        bookmakers=bookmaker_list,
        min_bookmakers=min_bookmakers,
    )


@router.get("/matches/{match_id}", response_model=MatchDetailOut)
def get_match(
    match_id: str,
    market: str | None = Query(None, description="Filter odds to a single market, e.g. '1x2'"),
    bookmakers: str | None = Query(
        None,
        description="Comma-separated bookmaker ids, e.g. 'fortuna,nike'",
    ),
    db: Session = Depends(get_db),
):
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    bookmaker_list = [item.strip() for item in bookmakers.split(",") if item.strip()] if bookmakers else None
    odds = latest_odds_for_match(db, match_id, market=market, bookmakers=bookmaker_list)
    return MatchDetailOut(
        id=match.id,
        league_id=match.league_id,
        home_team=match.home_team,
        away_team=match.away_team,
        start_time=match.start_time,
        status=match.status,
        odds=[
            OddsOut(
                bookmaker=odds_row.bookmaker,
                market=odds_row.market,
                selection=odds_row.selection,
                odds=odds_row.odds,
                url=resolve_bookmaker_url(match, odds_row.bookmaker, odds_row.url),
                scraped_at=odds_row.scraped_at,
            )
            for odds_row in odds
        ],
    )


@router.get("/matches/{match_id}/best-odds", response_model=list[BestOddsOut])
def get_best_odds(
    match_id: str,
    market: str | None = Query(None, description="Filter to a single market, e.g. '1x2'"),
    bookmakers: str | None = Query(
        None,
        description="Comma-separated bookmaker ids, e.g. 'fortuna,nike'",
    ),
    db: Session = Depends(get_db),
):
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    bookmaker_list = [item.strip() for item in bookmakers.split(",") if item.strip()] if bookmakers else None
    odds = latest_odds_for_match(db, match_id, market=market, bookmakers=bookmaker_list)
    if not odds:
        return []

    return build_best_odds(match, odds)
