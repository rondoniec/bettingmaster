from __future__ import annotations

from datetime import datetime

from bettingmaster.bookmaker_validation import is_valid_polymarket_url
from bettingmaster.models.match import Match


def test_polymarket_url_rejects_barcelona_sc_for_fc_barcelona_match():
    match = Match(
        id="m1",
        league_id="es-la-liga",
        home_team="Barcelona",
        away_team="Celta Vigo",
        start_time=datetime(2026, 4, 22, 19, 0),
        status="prematch",
    )

    assert not is_valid_polymarket_url(
        match,
        "https://polymarket.com/event/barcelona-sc-vs-celta-vigo",
    )


def test_polymarket_url_allows_fc_barcelona_slug_for_barcelona_match():
    match = Match(
        id="m1",
        league_id="es-la-liga",
        home_team="Barcelona",
        away_team="Celta Vigo",
        start_time=datetime(2026, 4, 22, 19, 0),
        status="prematch",
    )

    assert is_valid_polymarket_url(
        match,
        "https://polymarket.com/event/fc-barcelona-vs-celta-vigo",
    )
