from __future__ import annotations

from datetime import datetime

from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.models.sport import Sport
from bettingmaster.reconciliation import reconcile_matches


def test_reconcile_matches_merges_fortuna_and_nike_variants(db_session):
    db_session.add(Sport(id="football", name="Football"))
    db_session.add(
        League(id="en-premier-league", sport_id="football", name="Premier League", country="EN")
    )
    start_time = datetime(2026, 4, 12, 14, 0)

    fortuna_match = Match(
        id="fortuna-old",
        league_id="en-premier-league",
        home_team="Man.City",
        away_team="Arsenal",
        start_time=start_time,
        status="prematch",
        external_ids={"fortuna": "f-1"},
    )
    nike_match = Match(
        id="nike-old",
        league_id="en-premier-league",
        home_team="Manchester City",
        away_team="Arsenal FC",
        start_time=start_time,
        status="prematch",
        external_ids={"nike": "n-1"},
    )
    db_session.add_all([fortuna_match, nike_match])
    db_session.flush()
    db_session.add_all([
        OddsSnapshot(
            match_id="fortuna-old",
            bookmaker="fortuna",
            market="1x2",
            selection="home",
            odds=1.9,
            scraped_at=start_time,
        ),
        OddsSnapshot(
            match_id="nike-old",
            bookmaker="nike",
            market="1x2",
            selection="home",
            odds=2.0,
            scraped_at=start_time,
        ),
    ])
    db_session.commit()

    summary = reconcile_matches(db_session)

    assert summary.merged == 1
    matches = db_session.query(Match).all()
    assert len(matches) == 1
    match = matches[0]
    assert match.home_team == "Manchester City"
    assert match.away_team == "Arsenal"
    assert match.external_ids == {"fortuna": "f-1", "nike": "n-1"}
    assert {
        odds.match_id for odds in db_session.query(OddsSnapshot).all()
    } == {match.id}


def test_reconcile_matches_merges_doxxbet_abbreviations(db_session):
    db_session.add(Sport(id="football", name="Football"))
    db_session.add(
        League(id="ucl", sport_id="football", name="UEFA Champions League", country="EU")
    )
    start_time = datetime(2026, 4, 14, 19, 0)

    merged_match = Match(
        id="merged-old",
        league_id="ucl",
        home_team="Atletico Madrid",
        away_team="Barcelona",
        start_time=start_time,
        status="prematch",
        external_ids={"fortuna": "f-1", "nike": "n-1"},
    )
    doxxbet_match = Match(
        id="doxxbet-old",
        league_id="ucl",
        home_team="Atl. Madrid",
        away_team="Barcelona",
        start_time=start_time,
        status="prematch",
        external_ids={"doxxbet": "d-1"},
    )
    db_session.add_all([merged_match, doxxbet_match])
    db_session.flush()
    db_session.add(
        OddsSnapshot(
            match_id="doxxbet-old",
            bookmaker="doxxbet",
            market="1x2",
            selection="home",
            odds=2.2,
            scraped_at=start_time,
        )
    )
    db_session.commit()

    summary = reconcile_matches(db_session)

    assert summary.merged == 1
    matches = db_session.query(Match).all()
    assert len(matches) == 1
    match = matches[0]
    assert match.home_team == "Atletico Madrid"
    assert match.away_team == "Barcelona"
    assert match.external_ids == {"fortuna": "f-1", "nike": "n-1", "doxxbet": "d-1"}
    assert {
        odds.match_id for odds in db_session.query(OddsSnapshot).all()
    } == {match.id}


def test_reconcile_matches_fuzzy_merges_existing_duplicate_rows(db_session):
    db_session.add(Sport(id="football", name="Football"))
    db_session.add(
        League(id="it-serie-a", sport_id="football", name="Serie A", country="IT")
    )
    start_time = datetime(2026, 4, 19, 16, 0)
    canonical_match = Match(
        id="canonical",
        league_id="it-serie-a",
        home_team="Juventus",
        away_team="Bologna",
        start_time=start_time,
        status="prematch",
        external_ids={"nike": "n-1"},
    )
    duplicate_match = Match(
        id="duplicate",
        league_id="it-serie-a",
        home_team="Juventus FC",
        away_team="Bologna FC 1909",
        start_time=start_time,
        status="prematch",
        external_ids={"doxxbet": "d-1"},
    )
    db_session.add_all([canonical_match, duplicate_match])
    db_session.flush()
    db_session.add(
        OddsSnapshot(
            match_id="duplicate",
            bookmaker="doxxbet",
            market="1x2",
            selection="home",
            odds=1.5,
            scraped_at=start_time,
        )
    )
    db_session.commit()

    summary = reconcile_matches(db_session)

    assert summary.merged == 1
    matches = db_session.query(Match).all()
    assert len(matches) == 1
    assert matches[0].external_ids == {"nike": "n-1", "doxxbet": "d-1"}
    assert db_session.query(OddsSnapshot).one().match_id == matches[0].id
