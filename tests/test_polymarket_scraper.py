from datetime import datetime

from bettingmaster.models.match import Match
from bettingmaster.scrapers.polymarket import PolymarketScraper


def test_parse_clob_token_ids_accepts_json_string_and_lists(db_session):
    scraper = PolymarketScraper(db_session)

    assert scraper._parse_clob_token_ids({"clobTokenIds": '["tok-a","tok-b"]'}) == [
        "tok-a",
        "tok-b",
    ]
    assert scraper._parse_clob_token_ids({"clobTokenIds": ["tok-a", "tok-b"]}) == [
        "tok-a",
        "tok-b",
    ]


def test_parse_market_probabilities_prefers_clob_prices(db_session):
    scraper = PolymarketScraper(db_session)
    market = {
        "outcomes": '["Yes","No"]',
        "outcomePrices": "[0.20, 0.80]",
        "clobTokenIds": '["tok-yes","tok-no"]',
    }

    outcomes, prices = scraper._parse_market_probabilities(
        market,
        {"tok-yes": 0.45, "tok-no": 0.55},
    )

    assert outcomes == ["Yes", "No"]
    assert prices == [0.45, 0.55]


def test_parse_market_probabilities_falls_back_when_clob_price_missing(db_session):
    scraper = PolymarketScraper(db_session)
    market = {
        "outcomes": '["Over","Under"]',
        "outcomePrices": "[0.33, 0.67]",
        "clobTokenIds": '["tok-over","tok-under"]',
    }

    outcomes, prices = scraper._parse_market_probabilities(
        market,
        {"tok-over": 0.4},
    )

    assert outcomes == ["Over", "Under"]
    assert prices == [0.4, 0.67]


def test_extract_1x2_maps_team_titles_to_canonical_match_sides(db_session):
    scraper = PolymarketScraper(db_session)
    match = Match(
        id="juve-bologna",
        league_id="it-serie-a",
        home_team="Juventus",
        away_team="Bologna",
        start_time=datetime(2026, 4, 19, 18, 45),
        status="prematch",
    )
    event = {
        "markets": [
            {
                "groupItemTitle": "Bologna FC 1909",
                "outcomes": '["Yes","No"]',
                "outcomePrices": "[0.125, 0.875]",
            },
            {
                "groupItemTitle": "Juventus FC",
                "outcomes": '["Yes","No"]',
                "outcomePrices": "[0.685, 0.315]",
            },
            {
                "groupItemTitle": "Draw (Juventus FC vs. Bologna FC 1909)",
                "outcomes": '["Yes","No"]',
                "outcomePrices": "[0.195, 0.805]",
            },
        ]
    }

    odds = scraper._extract_1x2(event, match, "https://polymarket.com/event/test", {})

    assert {(row.selection, row.odds) for row in odds} == {
        ("away", 8.0),
        ("home", 1.46),
        ("draw", 5.128),
    }
