"""Odds query and comparison helpers shared by API routes."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from bettingmaster.config import settings
from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.schemas.common import (
    BestOddsOut,
    BestOddsSelection,
    MatchBestOddsOut,
    SurebetOut,
    SurebetSelection,
)
from bettingmaster.scope import active_match_window, apply_active_match_scope

TODAY_SENTINEL = "today"
TOMORROW_SENTINEL = "tomorrow"
NEXT_24_SENTINEL = "next24"
NIKE_MATCH_URL = "https://www.nike.sk/tipovanie/zapas/{sport_event_id}"


def _local_timezone() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def resolve_date_filter(date_filter: str | None, *, now: datetime | None = None) -> date:
    """Resolve API date filters like today, tomorrow, or YYYY-MM-DD."""
    local_now = (now or datetime.now(UTC)).astimezone(_local_timezone())
    current = local_now.date()
    if date_filter is None:
        return current

    normalized = date_filter.strip().lower()
    if normalized == TODAY_SENTINEL:
        return current
    if normalized == TOMORROW_SENTINEL:
        return current + timedelta(days=1)
    return date.fromisoformat(normalized)


def utc_day_bounds_for_local_date(target_date: date) -> tuple[datetime, datetime]:
    """Convert a local calendar date to naive UTC bounds used in the database."""
    timezone = _local_timezone()
    local_start = datetime.combine(target_date, time.min, tzinfo=timezone)
    local_end = datetime.combine(target_date, time.max, tzinfo=timezone)
    return (
        local_start.astimezone(UTC).replace(tzinfo=None),
        local_end.astimezone(UTC).replace(tzinfo=None),
    )


ODDS_MAX_AGE_HOURS = 24
LIVE_ODDS_MAX_AGE_MINUTES = 20


def odds_max_age_hours_for_status(status: str | None) -> float:
    """Return the freshness window for odds based on match status."""
    if status == "live":
        return LIVE_ODDS_MAX_AGE_MINUTES / 60
    return ODDS_MAX_AGE_HOURS


def build_latest_odds_subquery(
    db: Session,
    *,
    match_id: str | None = None,
    max_age_hours: float = ODDS_MAX_AGE_HOURS,
):
    """Return the latest timestamp per odds key, excluding stale rows."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=max_age_hours)
    query = db.query(
        OddsSnapshot.match_id,
        OddsSnapshot.bookmaker,
        OddsSnapshot.market,
        OddsSnapshot.selection,
        func.max(OddsSnapshot.scraped_at).label("max_ts"),
    ).filter(OddsSnapshot.scraped_at >= cutoff)
    if match_id:
        query = query.filter(OddsSnapshot.match_id == match_id)
    return query.group_by(
        OddsSnapshot.match_id,
        OddsSnapshot.bookmaker,
        OddsSnapshot.market,
        OddsSnapshot.selection,
    ).subquery()


def latest_odds_for_match(
    db: Session,
    match_id: str,
    *,
    market: str | None = None,
    bookmakers: list[str] | None = None,
) -> list[OddsSnapshot]:
    """Return the latest odds rows for a single match."""
    match = db.get(Match, match_id)
    latest_subquery = build_latest_odds_subquery(
        db,
        match_id=match_id,
        max_age_hours=odds_max_age_hours_for_status(match.status if match else None),
    )
    query = (
        db.query(OddsSnapshot)
        .join(
            latest_subquery,
            (OddsSnapshot.match_id == latest_subquery.c.match_id)
            & (OddsSnapshot.bookmaker == latest_subquery.c.bookmaker)
            & (OddsSnapshot.market == latest_subquery.c.market)
            & (OddsSnapshot.selection == latest_subquery.c.selection)
            & (OddsSnapshot.scraped_at == latest_subquery.c.max_ts),
        )
        .filter(OddsSnapshot.match_id == match_id)
    )
    if market:
        query = query.filter(OddsSnapshot.market == market)
    if bookmakers:
        query = query.filter(OddsSnapshot.bookmaker.in_(bookmakers))

    # Deduplicate: if multiple rows share the same (bookmaker, market, selection)
    # at the same max_ts (from legacy duplicate writes), keep the row with the
    # highest id — it was written last and is most authoritative.
    rows = query.all()
    seen: dict[tuple[str, str, str], OddsSnapshot] = {}
    for row in rows:
        key = (row.bookmaker, row.market, row.selection)
        existing = seen.get(key)
        if existing is None or row.id > existing.id:
            seen[key] = row
    return list(seen.values())


def resolve_bookmaker_url(
    match: Match,
    bookmaker: str,
    fallback_url: str | None = None,
) -> str | None:
    """Return the most precise public bookmaker URL available for a match."""
    external_ids = match.external_ids or {}

    if bookmaker == "nike":
        sport_event_id = external_ids.get("nike")
        if sport_event_id:
            return NIKE_MATCH_URL.format(sport_event_id=sport_event_id)

    return fallback_url


def build_best_odds(match: Match, odds_rows: list[OddsSnapshot]) -> list[BestOddsOut]:
    """Build best-odds response models from latest odds rows."""
    markets: dict[str, list[OddsSnapshot]] = {}
    for odds_row in odds_rows:
        markets.setdefault(odds_row.market, []).append(odds_row)

    result: list[BestOddsOut] = []
    for market, market_odds in markets.items():
        best_per_selection: dict[str, OddsSnapshot] = {}
        for odds_row in market_odds:
            existing = best_per_selection.get(odds_row.selection)
            if existing is None or odds_row.odds > existing.odds:
                best_per_selection[odds_row.selection] = odds_row

        selections = [
            BestOddsSelection(
                selection=selection,
                odds=selection_odds.odds,
                bookmaker=selection_odds.bookmaker,
                url=resolve_bookmaker_url(
                    match,
                    selection_odds.bookmaker,
                    selection_odds.url,
                ),
                scraped_at=selection_odds.scraped_at,
                checked_at=selection_odds.checked_at,
            )
            for selection, selection_odds in sorted(best_per_selection.items())
        ]
        inv_sum = sum(1.0 / selection.odds for selection in selections if selection.odds > 0)
        margin = (inv_sum - 1.0) * 100 if inv_sum > 0 else 0.0
        result.append(
            BestOddsOut(
                match_id=match.id,
                market=market,
                selections=selections,
                combined_margin=round(margin, 2),
            )
        )

    return sorted(result, key=lambda item: item.market)


def list_best_odds_matches(
    db: Session,
    *,
    target_date: date | None = None,
    time_window: tuple[datetime, datetime] | None = None,
    market: str,
    sport: str | None = None,
    league_id: str | None = None,
    status: str | None = None,
    bookmakers: list[str] | None = None,
    min_bookmakers: int = 2,
) -> list[MatchBestOddsOut]:
    """Return match summaries with best odds for a single market."""
    if time_window is None:
        time_window = (
            utc_day_bounds_for_local_date(target_date)
            if target_date is not None
            else active_match_window()
        )
    window_start, window_end = time_window
    latest_subquery = build_latest_odds_subquery(db)
    query = (
        db.query(OddsSnapshot, Match)
        .join(
            latest_subquery,
            (OddsSnapshot.match_id == latest_subquery.c.match_id)
            & (OddsSnapshot.bookmaker == latest_subquery.c.bookmaker)
            & (OddsSnapshot.market == latest_subquery.c.market)
            & (OddsSnapshot.selection == latest_subquery.c.selection)
            & (OddsSnapshot.scraped_at == latest_subquery.c.max_ts),
        )
        .join(Match, OddsSnapshot.match_id == Match.id)
        .filter(
            Match.start_time >= window_start,
            Match.start_time <= window_end,
            OddsSnapshot.market == market,
        )
    )
    query = apply_active_match_scope(query)
    if sport:
        query = query.join(League, Match.league_id == League.id).filter(League.sport_id == sport)
    if league_id:
        query = query.filter(Match.league_id == league_id)
    if status:
        query = query.filter(Match.status == status)
    if bookmakers:
        query = query.filter(OddsSnapshot.bookmaker.in_(bookmakers))

    rows = query.order_by(Match.start_time, Match.id, OddsSnapshot.selection, OddsSnapshot.bookmaker).all()

    grouped_rows: dict[str, tuple[Match, list[OddsSnapshot]]] = {}
    for odds_row, match in rows:
        if match.id not in grouped_rows:
            grouped_rows[match.id] = (match, [])
        grouped_rows[match.id][1].append(odds_row)

    result: list[MatchBestOddsOut] = []
    for match, odds_rows in grouped_rows.values():
        if match.status == "live":
            live_cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
                minutes=LIVE_ODDS_MAX_AGE_MINUTES
            )
            odds_rows = [odds_row for odds_row in odds_rows if odds_row.scraped_at >= live_cutoff]
            if not odds_rows:
                continue

        participating_bookmakers = sorted({odds_row.bookmaker for odds_row in odds_rows})
        if len(participating_bookmakers) < min_bookmakers:
            continue

        best_markets = build_best_odds(match, odds_rows)
        if not best_markets:
            continue

        best_market = best_markets[0]
        result.append(
            MatchBestOddsOut(
                id=match.id,
                league_id=match.league_id,
                home_team=match.home_team,
                away_team=match.away_team,
                start_time=match.start_time,
                status=match.status,
                market=best_market.market,
                selections=best_market.selections,
                combined_margin=best_market.combined_margin,
                bookmakers=participating_bookmakers,
            )
        )

    return sorted(result, key=lambda item: (item.start_time, item.home_team, item.away_team))


def live_feed_snapshot(
    db: Session,
    *,
    match_id: str | None = None,
    league_id: str | None = None,
    sport: str | None = None,
    target_date: date | None = None,
) -> dict[str, object]:
    """Return a compact snapshot signature for websocket subscribers."""
    match_query = db.query(Match)
    if match_id:
        match_query = match_query.filter(Match.id == match_id)
    if league_id:
        match_query = match_query.filter(Match.league_id == league_id)
    if sport:
        match_query = match_query.join(League, Match.league_id == League.id).filter(League.sport_id == sport)
    if target_date:
        day_start, day_end = utc_day_bounds_for_local_date(target_date)
        match_query = match_query.filter(Match.start_time >= day_start, Match.start_time <= day_end)

    matches = match_query.all()
    match_ids = sorted(match.id for match in matches)
    if not match_ids:
        return {
            "match_ids": [],
            "match_count": 0,
            "bookmaker_count": 0,
            "snapshot_count": 0,
            "latest_scraped_at": None,
        }

    snapshot_count, bookmaker_count, latest_scraped_at = (
        db.query(
            func.count(OddsSnapshot.id),
            func.count(func.distinct(OddsSnapshot.bookmaker)),
            func.max(OddsSnapshot.scraped_at),
        )
        .filter(OddsSnapshot.match_id.in_(match_ids))
        .one()
    )
    return {
        "match_ids": match_ids,
        "match_count": len(match_ids),
        "bookmaker_count": int(bookmaker_count or 0),
        "snapshot_count": int(snapshot_count or 0),
        "latest_scraped_at": latest_scraped_at.isoformat() if latest_scraped_at else None,
    }


def query_upcoming_latest_odds(
    db: Session,
    *,
    sport: str | None = None,
) -> Query:
    """Return a query over the latest odds for upcoming matches."""
    now = datetime.now(UTC).replace(tzinfo=None)
    latest_subquery = build_latest_odds_subquery(db)
    query = (
        db.query(OddsSnapshot, Match)
        .join(
            latest_subquery,
            (OddsSnapshot.match_id == latest_subquery.c.match_id)
            & (OddsSnapshot.bookmaker == latest_subquery.c.bookmaker)
            & (OddsSnapshot.market == latest_subquery.c.market)
            & (OddsSnapshot.selection == latest_subquery.c.selection)
            & (OddsSnapshot.scraped_at == latest_subquery.c.max_ts),
        )
        .join(Match, OddsSnapshot.match_id == Match.id)
        .filter(
            Match.status != "finished",
            Match.start_time > now,
        )
    )
    query = apply_active_match_scope(query)
    if sport:
        query = query.join(League, Match.league_id == League.id).filter(League.sport_id == sport)
    return query


def build_surebets(
    rows: list[tuple[OddsSnapshot, Match]],
    *,
    min_profit: float = 0.0,
    market_filter: str | None = None,
    bookmakers: list[str] | None = None,
) -> list[SurebetOut]:
    """Return surebet opportunities from latest odds rows."""
    match_lookup: dict[str, Match] = {}
    groups: dict[tuple[str, str], dict[str, OddsSnapshot]] = {}

    for odds_row, match in rows:
        if market_filter and odds_row.market != market_filter:
            continue
        if bookmakers and odds_row.bookmaker not in bookmakers:
            continue
        match_lookup[match.id] = match
        key = (odds_row.match_id, odds_row.market)
        groups.setdefault(key, {})
        existing = groups[key].get(odds_row.selection)
        if existing is None or odds_row.odds > existing.odds:
            groups[key][odds_row.selection] = odds_row

    surebets: list[SurebetOut] = []
    for (match_id, market), best_per_selection in groups.items():
        selections_list = list(best_per_selection.values())
        if not selections_list or any(item.odds <= 0 for item in selections_list):
            continue
        if len({item.bookmaker for item in selections_list}) < 2:
            continue

        inv_sum = sum(1.0 / item.odds for item in selections_list)
        margin = (inv_sum - 1.0) * 100
        if margin >= 0:
            continue

        profit_percent = abs(margin)
        if profit_percent < min_profit:
            continue

        match = match_lookup[match_id]
        selections = [
            SurebetSelection(
                selection=item.selection,
                odds=item.odds,
                bookmaker=item.bookmaker,
                url=resolve_bookmaker_url(match, item.bookmaker, item.url),
                scraped_at=item.scraped_at,
                checked_at=item.checked_at,
            )
            for item in sorted(selections_list, key=lambda odds_row: odds_row.selection)
        ]
        surebets.append(
            SurebetOut(
                match_id=match_id,
                home_team=match.home_team,
                away_team=match.away_team,
                league_id=match.league_id,
                start_time=match.start_time,
                market=market,
                selections=selections,
                margin=round(margin, 4),
                profit_percent=round(profit_percent, 4),
            )
        )

    surebets.sort(key=lambda item: item.margin)
    return surebets
