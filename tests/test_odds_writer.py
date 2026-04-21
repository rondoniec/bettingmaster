from __future__ import annotations

from datetime import datetime, timedelta

from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.models.sport import Sport
from bettingmaster.odds_writer import add_odds_snapshot


def test_add_odds_snapshot_preserves_timestamp_when_price_is_unchanged(db_session):
    db_session.add(Sport(id="football", name="Football"))
    db_session.add(
        League(id="en-premier-league", sport_id="football", name="Premier League", country="EN")
    )
    start_time = datetime(2026, 4, 21, 18, 0)
    db_session.add(
        Match(
            id="match-1",
            league_id="en-premier-league",
            home_team="Arsenal",
            away_team="Chelsea",
            start_time=start_time,
            status="prematch",
        )
    )
    first_seen = datetime(2026, 4, 21, 12, 0)
    later_seen = first_seen + timedelta(minutes=50)

    add_odds_snapshot(
        db_session,
        match_id="match-1",
        bookmaker="polymarket",
        market="1x2",
        selection="home",
        odds=1.89,
        url="https://polymarket.example/event",
        scraped_at=first_seen,
    )
    db_session.commit()

    snapshot = add_odds_snapshot(
        db_session,
        match_id="match-1",
        bookmaker="polymarket",
        market="1x2",
        selection="home",
        odds=1.89,
        url="https://polymarket.example/event",
        scraped_at=later_seen,
    )

    assert snapshot.scraped_at == first_seen


def test_add_odds_snapshot_uses_new_timestamp_when_price_changes(db_session):
    db_session.add(Sport(id="football", name="Football"))
    db_session.add(
        League(id="en-premier-league", sport_id="football", name="Premier League", country="EN")
    )
    start_time = datetime(2026, 4, 21, 18, 0)
    db_session.add(
        Match(
            id="match-1",
            league_id="en-premier-league",
            home_team="Arsenal",
            away_team="Chelsea",
            start_time=start_time,
            status="prematch",
        )
    )
    first_seen = datetime(2026, 4, 21, 12, 0)
    later_seen = first_seen + timedelta(minutes=50)

    add_odds_snapshot(
        db_session,
        match_id="match-1",
        bookmaker="polymarket",
        market="1x2",
        selection="home",
        odds=1.89,
        url="https://polymarket.example/event",
        scraped_at=first_seen,
    )
    db_session.commit()

    snapshot = add_odds_snapshot(
        db_session,
        match_id="match-1",
        bookmaker="polymarket",
        market="1x2",
        selection="home",
        odds=1.92,
        url="https://polymarket.example/event",
        scraped_at=later_seen,
    )

    assert snapshot.scraped_at == later_seen
