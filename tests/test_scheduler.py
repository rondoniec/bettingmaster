from __future__ import annotations

from datetime import datetime

from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.models.sport import Sport
from bettingmaster.scheduler import (
    RoundRobinWorkItem,
    _build_round_robin_work_items,
    _discover_round_robin_matches,
)
from bettingmaster.scrapers.base import RawMatch


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
