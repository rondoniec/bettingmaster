from __future__ import annotations

from datetime import datetime

from bettingmaster.scheduler import RoundRobinWorkItem, _build_round_robin_work_items
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
