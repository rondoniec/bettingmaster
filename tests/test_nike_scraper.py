from __future__ import annotations

from datetime import datetime

from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.scrapers.nike import NikeScraper


def test_nike_menu_catalog_and_run_use_dynamic_box_ids_and_slugs(db_session, monkeypatch):
    menu_payload = {
        "items": [
            {
                "itemId": 164,
                "boxId": "bi-1-null-null",
                "slug": "/futbal",
                "items": [
                    {
                        "itemId": 9999,
                        "boxId": "bi-1-929-26",
                        "slug": "/futbal/taliansko/taliansko-i-liga",
                        "label": "Taliansko I. liga",
                        "items": [],
                    }
                ],
            }
        ]
    }
    top_tournaments_payload = {
        "26": {
            "matches": [
                {
                    "id": "9001",
                    "tournamentId": "26",
                    "startTime": "2026-04-12T20:45:00+02:00",
                    "home": {"sk": "Juventus"},
                    "away": {"sk": "Bologna"},
                    "bets": [],
                    "isLive": False,
                }
            ]
        }
    }
    detail_payload = {
        "bets": [
            {
                "header": "Zápas",
                "selectionGrid": [[
                    {"type": "selection", "tip": "49", "odds": 2.2, "enabled": True},
                    {"type": "selection", "tip": "88", "odds": 3.4, "enabled": True},
                    {"type": "selection", "tip": "50", "odds": 3.1, "enabled": True},
                ]],
            },
            {
                "header": "Obaja dajú gól",
                "selectionGrid": [[
                    {"type": "selection", "name": "áno", "odds": 1.8, "enabled": True},
                    {"type": "selection", "name": "nie", "odds": 2.0, "enabled": True},
                ]],
            },
        ]
    }

    def fake_nike_get(path: str):
        if path == "/api-gw/nikeone/v1/menu":
            return menu_payload
        if path == "/api-gw/nikeone/v1/matches/special/top-tournaments?tournamentId=26":
            return top_tournaments_payload
        if path == "/api-gw/nikeone/v1/boxes/extended/sport-event-id?boxId=bi-1-929-26&sportEventId=9001":
            return detail_payload
        raise AssertionError(f"Unexpected path: {path}")

    scraper = NikeScraper(db_session=db_session)
    monkeypatch.setattr(scraper, "_nike_get", fake_nike_get)

    scraper.run({"it-serie-a": "26"})

    match = db_session.query(Match).one()
    assert match.league_id == "it-serie-a"
    assert match.start_time == datetime(2026, 4, 12, 18, 45)

    odds = (
        db_session.query(OddsSnapshot)
        .order_by(OddsSnapshot.market, OddsSnapshot.selection)
        .all()
    )
    assert {(item.market, item.selection) for item in odds} == {
        ("1x2", "away"),
        ("1x2", "draw"),
        ("1x2", "home"),
        ("btts", "no"),
        ("btts", "yes"),
    }
    assert {item.url for item in odds} == {"https://www.nike.sk/tipovanie/zapas/9001"}


def test_nike_parser_ignores_team_specific_goal_totals(db_session):
    scraper = NikeScraper(db_session=db_session)

    generic = scraper._parse_bet(
        {
            "header": "Atletico Madrid - FC Barcelona Počet gólov",
            "selectionGrid": [[
                {"type": "selection", "name": "menej ako 2.0", "odds": 5.37, "enabled": True},
                {"type": "selection", "name": "viac ako 2.0", "odds": 1.14, "enabled": True},
            ]],
        }
    )
    team_specific = scraper._parse_bet(
        {
            "header": "Atletico Madrid - FC Barcelona: Atletico Madrid počet gólov",
            "selectionGrid": [[
                {"type": "selection", "name": "menej ako 2.0", "odds": 1.3, "enabled": True},
                {"type": "selection", "name": "viac ako 2.0", "odds": 3.57, "enabled": True},
            ]],
        }
    )

    assert generic == [("over_under_2.0", "under", 5.37), ("over_under_2.0", "over", 1.14)]
    assert team_specific == []


def test_nike_parser_maps_btts_half_headers_to_half_markets(db_session):
    scraper = NikeScraper(db_session=db_session)

    full_time = scraper._parse_bet(
        {
            "header": "FC Liverpool - Paris St.G. Obaja dajú gól",
            "selectionGrid": [[
                {"type": "selection", "name": "áno", "odds": 1.43, "enabled": True},
                {"type": "selection", "name": "nie", "odds": 2.7, "enabled": True},
            ]],
        }
    )
    first_half = scraper._parse_bet(
        {
            "header": "FC Liverpool - Paris St.G.: Obaja dajú gól 1.pol.",
            "selectionGrid": [[
                {"type": "selection", "name": "áno", "odds": 3.2, "enabled": True},
                {"type": "selection", "name": "nie", "odds": 1.3, "enabled": True},
            ]],
        }
    )
    second_half = scraper._parse_bet(
        {
            "header": "FC Liverpool - Paris St.G.: Obaja dajú gól 2.pol.",
            "selectionGrid": [[
                {"type": "selection", "name": "áno", "odds": 2.5, "enabled": True},
                {"type": "selection", "name": "nie", "odds": 1.46, "enabled": True},
            ]],
        }
    )

    assert full_time == [("btts", "yes", 1.43), ("btts", "no", 2.7)]
    assert first_half == [("btts_ht", "yes", 3.2), ("btts_ht", "no", 1.3)]
    assert second_half == [("btts_2h", "yes", 2.5), ("btts_2h", "no", 1.46)]
