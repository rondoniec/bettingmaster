"""Shared project scope: active leagues and near-term match window."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Query

from bettingmaster.config import settings
from bettingmaster.models.match import Match

NEXT_24_SENTINEL = "next24"


def active_league_ids() -> list[str]:
    raw = settings.active_league_ids.strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def active_match_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = (now or datetime.now(UTC)).replace(tzinfo=None)
    return (
        current - timedelta(hours=settings.active_match_lookback_hours),
        current + timedelta(hours=settings.active_match_window_hours),
    )


def is_active_league(league_id: str) -> bool:
    leagues = active_league_ids()
    return not leagues or league_id in leagues


def is_match_in_active_scope(
    league_id: str,
    start_time: datetime,
    *,
    now: datetime | None = None,
) -> bool:
    if not is_active_league(league_id):
        return False
    window_start, window_end = active_match_window(now)
    return window_start <= start_time <= window_end


def apply_active_match_scope(query: Query) -> Query:
    leagues = active_league_ids()
    window_start, window_end = active_match_window()
    if leagues:
        query = query.filter(Match.league_id.in_(leagues))
    return query.filter(
        Match.status != "finished",
        Match.start_time >= window_start,
        Match.start_time <= window_end,
    )
