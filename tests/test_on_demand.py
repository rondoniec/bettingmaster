from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bettingmaster.config import settings
from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.models.sport import Sport
from bettingmaster.services.on_demand import refresh_polymarket_match_if_stale


def _add_match(db_session, *, checked_at: datetime) -> Match:
    db_session.add_all([
        Sport(id="football", name="Football"),
        League(id="en-premier-league", sport_id="football", name="Premier League", country="EN"),
    ])
    match = Match(
        id="match-1",
        league_id="en-premier-league",
        home_team="Arsenal",
        away_team="Chelsea",
        start_time=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=2),
        status="prematch",
        external_ids={"polymarket": "arsenal-vs-chelsea"},
    )
    db_session.add(match)
    db_session.add(
        OddsSnapshot(
            match_id="match-1",
            bookmaker="polymarket",
            market="1x2",
            selection="home",
            odds=2.1,
            url="https://polymarket.com/event/arsenal-vs-chelsea",
            scraped_at=checked_at - timedelta(hours=1),
            checked_at=checked_at,
        )
    )
    db_session.commit()
    return match


def test_polymarket_on_demand_refresh_skips_recent_check(db_session, monkeypatch):
    now = datetime.now(UTC).replace(tzinfo=None)
    match = _add_match(db_session, checked_at=now)
    monkeypatch.setattr(settings, "on_demand_polymarket_max_age_seconds", 60)

    class FailIfCalledScraper:
        BOOKMAKER = "polymarket"

        def __init__(self, db):
            raise AssertionError("fresh Polymarket odds should not refresh")

    monkeypatch.setattr("bettingmaster.services.on_demand.PolymarketScraper", FailIfCalledScraper)

    assert refresh_polymarket_match_if_stale(db_session, match) == 0


def test_polymarket_on_demand_refreshes_stale_check(db_session, monkeypatch):
    old_check = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10)
    match = _add_match(db_session, checked_at=old_check)
    monkeypatch.setattr(settings, "on_demand_polymarket_max_age_seconds", 60)
    called = []

    class FakeScraper:
        BOOKMAKER = "polymarket"

        def __init__(self, db):
            self._db = db

        def refresh_match(self, refreshed_match):
            called.append(refreshed_match.id)
            return 7

        def close(self):
            pass

    monkeypatch.setattr("bettingmaster.services.on_demand.PolymarketScraper", FakeScraper)

    assert refresh_polymarket_match_if_stale(db_session, match) == 7
    assert called == ["match-1"]
