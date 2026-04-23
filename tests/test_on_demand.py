from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bettingmaster.config import settings
from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.models.sport import Sport
from bettingmaster.scrapers.base import RawOdds
from bettingmaster.services.on_demand import (
    refresh_match_odds_if_stale,
    refresh_polymarket_match_if_stale,
)


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


def test_standard_bookmaker_on_demand_refresh_preserves_existing_url(db_session, monkeypatch):
    now = datetime.now(UTC).replace(tzinfo=None)
    db_session.add_all([
        Sport(id="football", name="Football"),
        League(
            id="it-serie-a",
            sport_id="football",
            name="Serie A",
            country="IT",
            external_ids={"fortuna": "ufo:tour:test"},
        ),
    ])
    match = Match(
        id="match-fortuna",
        league_id="it-serie-a",
        home_team="Juventus",
        away_team="Bologna",
        start_time=now + timedelta(hours=2),
        status="prematch",
        external_ids={"fortuna": "fixture-1"},
    )
    db_session.add(match)
    db_session.add(
        OddsSnapshot(
            match_id="match-fortuna",
            bookmaker="fortuna",
            market="1x2",
            selection="home",
            odds=2.0,
            url="https://fortuna.example/home",
            scraped_at=now - timedelta(hours=2),
            checked_at=now - timedelta(minutes=15),
        )
    )
    db_session.commit()
    monkeypatch.setattr(settings, "on_demand_fortuna_max_age_seconds", 60)
    called = []

    class FakeFortunaScraper:
        def __init__(self, db):
            self._db = db

        def scrape_odds(self, match_external_id):
            called.append(match_external_id)
            return [
                RawOdds(
                    match_external_id=match_external_id,
                    market="1x2",
                    selection="home",
                    odds=2.2,
                    url=None,
                )
            ]

        def close(self):
            pass

    monkeypatch.setattr("bettingmaster.services.on_demand.FortunaScraper", FakeFortunaScraper)

    assert refresh_match_odds_if_stale(db_session, match, requested_bookmakers=["fortuna"]) == 1
    latest = (
        db_session.query(OddsSnapshot)
        .filter(OddsSnapshot.match_id == "match-fortuna", OddsSnapshot.bookmaker == "fortuna")
        .order_by(OddsSnapshot.id.desc())
        .first()
    )

    assert called == ["fixture-1"]
    assert latest is not None
    assert latest.odds == 2.2
    assert latest.url == "https://fortuna.example/home"
    assert latest.checked_at is not None
