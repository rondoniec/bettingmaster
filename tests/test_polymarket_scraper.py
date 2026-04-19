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
