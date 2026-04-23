from __future__ import annotations

from datetime import datetime

import bettingmaster.scheduler as scheduler_module
from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.models.scrape_run import ScrapeRun
from bettingmaster.models.sport import Sport
from bettingmaster.scheduler import (
    RoundRobinWorkItem,
    _build_round_robin_work_items,
    _discover_round_robin_matches,
    run_round_robin_cycle,
)
from bettingmaster.scrapers.base import RawMatch, RawOdds
from bettingmaster.services.scraper_status import get_scraper_status_map


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


class _SuccessfulRoundRobinScraper:
    def __init__(self, db_session):
        self._db = db_session

    def scrape_matches(self, league_external_id):
        return [
            RawMatch(
                external_id="fortuna-match-1",
                home_team="Liverpool",
                away_team="Arsenal",
                league_external_id=league_external_id,
                start_time=datetime(2026, 4, 20, 18, 0),
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


class _FailingDiscoveryScraper:
    def __init__(self, db_session):
        self._db = db_session

    def scrape_matches(self, league_external_id):
        raise RuntimeError("discovery unavailable")

    def close(self):
        return None


class _PartialDiscoveryScraper:
    def __init__(self, db_session):
        self._db = db_session

    def scrape_matches(self, league_external_id):
        if league_external_id == "league-ok":
            return [
                RawMatch(
                    external_id="fortuna-match-2",
                    home_team="Chelsea",
                    away_team="Tottenham",
                    league_external_id=league_external_id,
                    start_time=datetime(2026, 4, 20, 20, 0),
                )
            ]
        raise RuntimeError("secondary feed timeout")

    def scrape_odds_for_raw_match(self, raw_match):
        return [
            RawOdds(
                match_external_id=raw_match.external_id,
                market="1x2",
                selection="home",
                odds=1.9,
                url="https://fortuna.example/chelsea",
            )
        ]

    def close(self):
        return None


class _SchedulerNormalizer:
    def __init__(self, db_session):
        self._db = db_session

    def normalize(self, value, bookmaker):
        return value


def _configure_scheduler(monkeypatch, db_session, scraper_cls):
    scheduler_module._last_round_robin_run.clear()
    scheduler_module._bookmaker_cooldowns.clear()
    monkeypatch.setattr(scheduler_module, "SessionLocal", db_session.info["session_factory"])
    monkeypatch.setattr(scheduler_module, "SCRAPER_CLASSES", {"fortuna": scraper_cls})
    monkeypatch.setattr("bettingmaster.normalizer.TeamNormalizer", _SchedulerNormalizer)


def test_round_robin_cycle_persists_scrape_run_summary(db_session, monkeypatch):
    _configure_scheduler(monkeypatch, db_session, _SuccessfulRoundRobinScraper)

    db_session.add(Sport(id="football", name="Football"))
    db_session.add(
        League(
            id="en-premier-league",
            sport_id="football",
            name="Premier League",
            country="GB",
            external_ids={"fortuna": "league-ok"},
        )
    )
    db_session.commit()

    run_round_robin_cycle(force_bookmakers=["fortuna"])
    db_session.expire_all()

    scrape_runs = db_session.query(ScrapeRun).all()
    assert len(scrape_runs) == 1
    scrape_run = scrape_runs[0]
    assert scrape_run.bookmaker == "fortuna"
    assert scrape_run.source == "round_robin"
    assert scrape_run.status == "success"
    assert scrape_run.matches_found == 1
    assert scrape_run.odds_saved == 2
    assert scrape_run.error_message is None
    assert scrape_run.finished_at >= scrape_run.started_at


def test_round_robin_cycle_persists_failed_scrape_run_status(db_session, monkeypatch):
    _configure_scheduler(monkeypatch, db_session, _FailingDiscoveryScraper)

    db_session.add(Sport(id="football", name="Football"))
    db_session.add(
        League(
            id="en-premier-league",
            sport_id="football",
            name="Premier League",
            country="GB",
            external_ids={"fortuna": "league-fail"},
        )
    )
    db_session.commit()

    run_round_robin_cycle(force_bookmakers=["fortuna"])
    db_session.expire_all()

    scrape_run = db_session.query(ScrapeRun).one()
    assert scrape_run.status == "failed"
    assert scrape_run.matches_found == 0
    assert scrape_run.odds_saved == 0
    assert scrape_run.error_message == "RuntimeError: discovery unavailable"

    scraper_status = get_scraper_status_map(db_session, ["fortuna"])["fortuna"]
    assert scraper_status["last_status"] == "failed"
    assert scraper_status["last_failure_at"] == scrape_run.finished_at


def test_round_robin_cycle_marks_partial_status_for_mixed_outcomes(db_session, monkeypatch):
    _configure_scheduler(monkeypatch, db_session, _PartialDiscoveryScraper)

    db_session.add(Sport(id="football", name="Football"))
    db_session.add_all(
        [
            League(
                id="en-premier-league",
                sport_id="football",
                name="Premier League",
                country="GB",
                external_ids={"fortuna": "league-ok"},
            ),
            League(
                id="es-la-liga",
                sport_id="football",
                name="La Liga",
                country="ES",
                external_ids={"fortuna": "league-fail"},
            ),
        ]
    )
    db_session.commit()

    run_round_robin_cycle(force_bookmakers=["fortuna"])
    db_session.expire_all()

    scrape_run = db_session.query(ScrapeRun).one()
    assert scrape_run.status == "partial"
    assert scrape_run.matches_found == 1
    assert scrape_run.odds_saved == 1
    assert scrape_run.error_message == "RuntimeError: secondary feed timeout"
