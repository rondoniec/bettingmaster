"""Helpers for writing odds snapshots without faking freshness."""

from __future__ import annotations

from datetime import datetime

from bettingmaster.models.odds import OddsSnapshot


def add_odds_snapshot(
    db_session,
    *,
    match_id: str,
    bookmaker: str,
    market: str,
    selection: str,
    odds: float,
    url: str | None,
    scraped_at: datetime,
) -> OddsSnapshot:
    previous = (
        db_session.query(OddsSnapshot)
        .filter_by(
            match_id=match_id,
            bookmaker=bookmaker,
            market=market,
            selection=selection,
        )
        .order_by(OddsSnapshot.scraped_at.desc(), OddsSnapshot.id.desc())
        .first()
    )
    odds_unchanged = (
        previous is not None
        and abs(previous.odds - odds) <= 0.0001
        and (previous.url or "") == (url or "")
    )
    if odds_unchanged:
        previous.checked_at = scraped_at
        return previous

    snapshot = OddsSnapshot(
        match_id=match_id,
        bookmaker=bookmaker,
        market=market,
        selection=selection,
        odds=odds,
        url=url,
        scraped_at=scraped_at,
        checked_at=scraped_at,
    )
    db_session.add(snapshot)
    return snapshot
