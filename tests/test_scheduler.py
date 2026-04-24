from __future__ import annotations

from datetime import datetime

import bettingmaster.scheduler as scheduler_mod
from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.models.scrape_run import ScrapeRun
from bettingmaster.models.sport import Sport
from bettingmaster.scheduler import (
    RoundRobinWorkItem,
    _build_round_robin_work_items,
    _discover_round_robin_matches,
    run_round_robin_cycle,
)
from bettingmaster.scrapers.base import RawMatch, RawOdds


def test_build_round_robin_work_items_groups_by_match_then_bookmaker():
    first_match = datetime(2026, 4, 19, 14, 0)
    second_match = datetime(2026, 4, 19, 16, 0)

    items = [
        RoundRobinWorkItem(
            bookmaker="fortuna",
            league_id="it-serie-a",
            match_id="match-b",
            home_team="Juventus",
            away_team="Bologna",
            start_time=second_match,
            status="prematch",
            raw_match=RawMatch(
                external_id="f-2",
                home_team="Juventus",
                away_team="Bologna",
                league_external_id="serie-a",
                start_time=second_match,
            ),
        ),
        RoundRobinWorkItem(
            bookmaker="doxxbet",
            league_id="it-serie-a",
            match_id="match-a",
            home_team="Inter",
            away_team="Roma",
            start_time=first_match,
            status="prematch",
            raw_match=RawMatch(
                external_id="d-1",
                home_team="Inter",
                away_team="Roma",
                league_external_id="serie-a",
                start_time=first_match,
            ),
        ),
        RoundRobinWorkItem(
            bookmaker="nike",
            league_id="it-serie-a",
            match_id="match-a",
            home_team="Inter",
            away_team="Roma",
            start_time=first_match,
            status="prematch",
            raw_match=RawMatch(
                external_id="n-1",
                home_team="Inter",
                away_team="Roma",
                league_external_id="26",
                start_time=first_match,
            ),
        ),
        RoundRobinWorkItem(
            bookmaker="nike",
            league_id="it-serie-a",
            match_id="match-b",
            home_team="Juventus",
            away_team="Bologna",
            start_time=second_match,
            status="prematch",
            raw_match=RawMatch(
                external_id="n-2",
                home_team="Juventus",
                away_team="Bologna",
                league_external_id="26",
                start_time=second_match,
            ),
        ),
    ]

    ordered = _build_round_robin_work_items(items)

    assert [(item.match_id, item.bookmaker) for item in ordered] == [
        ("match-a", "nike"),
        ("match-a", "doxxbet"),
        ("match-b", "nike"),
        ("match-b", "fortuna"),
    ]


def test_build_round_robin_work_items_coalesces_same_match_variants():
    start_time = datetime(2026, 4, 19, 16, 0)
    items = [
        RoundRobinWorkItem(
            bookmaker="nike",
            league_id="it-serie-a",
            match_id="nike-match",
            home_team="Juventus",
            away_team="Bologna",
            start_time=start_time,
            status="prematch",
            raw_match=RawMatch(
                external_id="n-1",
                home_team="Juventus",
                away_team="Bologna",
                league_external_id="26",
                start_time=start_time,
            ),
        ),
        RoundRobinWorkItem(
            bookmaker="doxxbet",
            league_id="it-serie-a",
            match_id="doxxbet-match",
            home_team="Juventus FC",
            away_team="Bologna FC 1909",
            start_time=start_time,
            status="prematch",
            raw_match=RawMatch(
                external_id="d-1",
                home_team="Juventus FC",
                away_team="Bologna FC 1909",
                league_external_id="serie-a",
                start_time=start_time,
            ),
        ),
    ]

    ordered = _build_round_robin_work_items(items)

    assert [item.bookmaker for item in ordered] == ["nike", "doxxbet"]
    assert ordered[0].match_id == ordered[1].match_id
    assert ordered[1].home_team == "Juventus"
    assert ordered[1].away_team == "Bologna"


class _StaticScraper:
    def __init__(self, matches):
        self._matches = matches

    def scrape_matches(self, league_external_id):
        return self._matches


class _NoopNormalizer:
    def normalize(self, value, bookmaker):
        return value


class _SuccessfulRoundRobinScraper:
    def __init__(self, db_session):
        self._db = db_session

    def scrape_matches(self, league_external_id):
        return [
            RawMatch(
                external_id="fortuna-match-1",
                home_team="Inter",
                away_team="Roma",
                league_external_id=league_external_id,
                start_time=datetime(2026, 4, 19, 14, 0),
            )
        ]

    def scrape_odds_for_raw_match(self, raw_match):
        return [
            RawOdds(
                match_external_id=raw_match.external_id,
                market="1x2",
                selection="home",
                odds=2.1,
                url="https://fortuna.example/home",
            ),
            RawOdds(
                match_external_id=raw_match.external_id,
                market="1x2",
                selection="away",
                odds=3.4,
                url="https://fortuna.example/away",
            ),
        ]

    def close(self):
        return None


class _PartialRoundRobinScraper:
    def __init__(self, db_session):
        self._db = db_session

    def scrape_matches(self, league_external_id):
        start_time = datetime(2026, 4, 19, 16, 0)
        return [
            RawMatch(
                external_id="d-good",
                home_team="Inter",
                away_team="Roma",
                league_external_id=league_external_id,
                start_time=start_time,
            ),
            RawMatch(
                external_id="d-bad",
                home_team="Juventus",
                away_team="Milan",
                league_external_id=league_external_id,
                start_time=start_time,
            ),
        ]

    def scrape_odds_for_raw_match(self, raw_match):
        if raw_match.external_id == "d-bad":
            raise RuntimeError("second match save failed")
        return [
            RawOdds(
                match_external_id=raw_match.external_id,
                market="1x2",
                selection="home",
                odds=1.9,
                url="https://doxxbet.example/home",
            ),
            RawOdds(
                match_external_id=raw_match.external_id,
                market="1x2",
                selection="away",
                odds=4.2,
                url="https://doxxbet.example/away",
            ),
        ]

    def close(self):
        return None


class _FailingDiscoveryScraper:
    def __init__(self, db_session):
        self._db = db_session

    def scrape_matches(self, league_external_id):
        raise RuntimeError("discovery exploded")

    def close(self):
        return None


def test_discover_round_robin_matches_reuses_existing_similar_match(db_session):
    db_session.add(Sport(id="football", name="Football"))
    db_session.add(League(id="ucl", sport_id="football", name="UCL", country="EU"))
    start_time = datetime(2026, 4, 14, 19, 0)
    db_session.add(
        Match(
            id="canonical-match",
            league_id="ucl",
            home_team="Atletico Madrid",
            away_team="Barcelona",
            start_time=start_time,
            status="prematch",
            external_ids={"nike": "n-1"},
        )
    )
    db_session.commit()

    discovered = _discover_round_robin_matches(
        db_session,
        "doxxbet",
        _StaticScraper([
            RawMatch(
                external_id="d-1",
                home_team="Atl. Madrid",
                away_team="Barcelona",
                league_external_id="607245",
                start_time=start_time,
            )
        ]),
        {"ucl": "607245"},
        _NoopNormalizer(),
    )

    assert len(discovered) == 1
    assert discovered[0].match_id == "canonical-match"
    assert discovered[0].home_team == "Atletico Madrid"


def test_round_robin_cycle_persists_success_counters(db_session, monkeypatch):
    _seed_round_robin_league(db_session, bookmaker="fortuna", external_id="fortuna-league")
    _configure_scheduler_test_state(
        monkeypatch,
        db_session,
        {"fortuna": _SuccessfulRoundRobinScraper},
    )

    run_round_robin_cycle(force_bookmakers=["fortuna"])

    db_session.expire_all()
    run = db_session.query(ScrapeRun).one()
    assert run.bookmaker == "fortuna"
    assert run.trigger == "round_robin"
    assert run.status == "success"
    assert run.matches_found == 1
    assert run.odds_saved == 2
    assert run.error_message is None
    assert db_session.query(Match).count() == 1
    assert db_session.query(OddsSnapshot).count() == 2


def test_round_robin_cycle_persists_failure_status(db_session, monkeypatch):
    _seed_round_robin_league(db_session, bookmaker="tipsport", external_id="tipsport-league")
    _configure_scheduler_test_state(
        monkeypatch,
        db_session,
        {"tipsport": _FailingDiscoveryScraper},
    )

    run_round_robin_cycle(force_bookmakers=["tipsport"])

    db_session.expire_all()
    run = db_session.query(ScrapeRun).one()
    assert run.bookmaker == "tipsport"
    assert run.status == "failed"
    assert run.matches_found == 0
    assert run.odds_saved == 0
    assert run.error_message == "discovery exploded"
    assert db_session.query(OddsSnapshot).count() == 0


def test_round_robin_cycle_persists_partial_status(db_session, monkeypatch):
    _seed_round_robin_league(db_session, bookmaker="doxxbet", external_id="doxxbet-league")
    _configure_scheduler_test_state(
        monkeypatch,
        db_session,
        {"doxxbet": _PartialRoundRobinScraper},
    )

    run_round_robin_cycle(force_bookmakers=["doxxbet"])

    db_session.expire_all()
    run = db_session.query(ScrapeRun).one()
    assert run.bookmaker == "doxxbet"
    assert run.status == "partial"
    assert run.matches_found == 2
    assert run.odds_saved == 2
    assert run.error_message == "second match save failed"
    assert db_session.query(Match).count() == 1
    assert db_session.query(OddsSnapshot).count() == 2


def _seed_round_robin_league(db_session, *, bookmaker: str, external_id: str):
    db_session.add(Sport(id="football", name="Football"))
    db_session.add(
        League(
            id="it-serie-a",
            sport_id="football",
            name="Serie A",
            country="IT",
            external_ids={bookmaker: external_id},
        )
    )
    db_session.commit()


def _configure_scheduler_test_state(monkeypatch, db_session, scraper_classes):
    monkeypatch.setattr(scheduler_mod, "SCRAPER_CLASSES", scraper_classes)
    monkeypatch.setattr(scheduler_mod, "SessionLocal", db_session.info["session_factory"])
    monkeypatch.setattr(scheduler_mod, "_last_round_robin_run", {})
    monkeypatch.setattr(scheduler_mod, "_bookmaker_cooldowns", {})
