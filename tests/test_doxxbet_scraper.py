from __future__ import annotations

from datetime import datetime

from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.models.sport import Sport
from bettingmaster.normalizer import TeamNormalizer
from bettingmaster.scrapers.base import generate_match_id
from bettingmaster.scrapers.doxxbet import DoxxbetScraper


def test_doxxbet_scraper_uses_targeted_listing_pages_and_parses_local_time(db_session, monkeypatch):
    league_id = "919"
    listing_payload = [
        {
            "id": 74144581,
            "name": "Žilina vs. Slovan Bratislava",
            "teams": ["Žilina", "Slovan Bratislava"],
            "sportID": 54,
            "leagueID": 919,
            "date": "18.04.2026 - SOBOTA",
            "datetime": {"time": "18:00", "isToday": False, "date": "sobota"},
            "isLive": False,
            "url": "sk/sportove-tipovanie-online/kurzy/futbal/slovensko/1-liga?event=74144581&name=zilina-vs-slovan-bratislava",
        }
    ]
    detail_payload = {
        "Výsledok": {"0": 2.15, "1": 3.45, "2": 3.1, "3": 1.3, "4": 1.72, "5": 1.28},
        "Oba tímy dajú gól": {"0": 1.75, "1": 2.02},
    }

    requested_paths: list[str | None] = []

    def fake_load_listing_page(path: str | None = None):
        requested_paths.append(path)
        if path == "/sk/sportove-tipovanie-online/kurzy/futbal/slovensko/1-liga":
            return listing_payload
        raise AssertionError(f"Unexpected listing path: {path}")

    scraper = DoxxbetScraper(db_session=db_session)
    monkeypatch.setattr(scraper, "_load_listing_page", fake_load_listing_page)
    monkeypatch.setattr(scraper, "_load_match_detail", lambda event_id, event_url: detail_payload)

    scraper.run({"sk-fortuna-liga": league_id})

    assert requested_paths == ["/sk/sportove-tipovanie-online/kurzy/futbal/slovensko/1-liga"]

    match = db_session.query(Match).one()
    assert match.league_id == "sk-fortuna-liga"
    assert match.start_time == datetime(2026, 4, 18, 16, 0)
    assert match.external_ids == {"doxxbet": "74144581"}

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
        ("double_chance", "draw_away"),
        ("double_chance", "home_away"),
        ("double_chance", "home_draw"),
    }
    assert {item.url for item in odds} == {
        "https://www.doxxbet.sk/sk/sportove-tipovanie-online/kurzy/futbal/slovensko/1-liga?event=74144581&name=zilina-vs-slovan-bratislava"
    }


def test_doxxbet_scraper_persists_external_ids_when_match_already_exists(db_session, monkeypatch):
    start_time = datetime(2026, 4, 14, 19, 0)
    db_session.add(Sport(id="football", name="Football"))
    db_session.add(
        League(id="ucl", sport_id="football", name="UEFA Champions League", country="EU")
    )
    existing_match = Match(
        id=generate_match_id("ucl", "Atletico Madrid", "Barcelona", "2026-04-14"),
        league_id="ucl",
        home_team="Atletico Madrid",
        away_team="Barcelona",
        start_time=start_time,
        status="prematch",
        external_ids={"nike": "1011519925"},
    )
    db_session.add(existing_match)
    db_session.commit()

    listing_payload = [
        {
            "id": 73802717,
            "name": "Atl. Madrid vs Barcelona",
            "teams": ["Atl. Madrid", "Barcelona"],
            "sportID": 54,
            "leagueID": 607245,
            "date": "14.04.2026 - UTOROK",
            "datetime": {"time": "21:00", "isToday": False, "date": "utorok"},
            "isLive": False,
            "url": "sk/sportove-tipovanie-online/kurzy/futbal/kluby/liga-majstrov-uefa?event=73802717&name=atl-madrid-vs-fc-barcelona",
        }
    ]
    detail_payload = {
        "VÃ½sledok": {"0": 2.3, "1": 3.4, "2": 2.95},
    }

    scraper = DoxxbetScraper(db_session=db_session)
    monkeypatch.setattr(scraper, "_load_listing_page", lambda path=None: listing_payload)
    monkeypatch.setattr(scraper, "_load_match_detail", lambda event_id, event_url: detail_payload)

    scraper.run({"ucl": "607245"}, normalizer=TeamNormalizer(db_session=db_session))

    match = db_session.get(
        Match,
        generate_match_id("ucl", "Atletico Madrid", "Barcelona", "2026-04-14"),
    )
    assert match is not None
    assert match.external_ids == {"nike": "1011519925", "doxxbet": "73802717"}


def test_doxxbet_parser_ignores_team_specific_without_markets(db_session):
    scraper = DoxxbetScraper(db_session=db_session)

    parsed = scraper._parse_chance_types(
        {
            "V\u00fdsledok bez rem\u00edzy": {"0": 1.25, "1": 3.45},
            "V\u00fdsledok bez Bayern Munchen": {"0": 1.87, "1": 1.83},
            "V\u00fdsledok bez Real Madrid": {"0": 1.25, "1": 3.60},
        }
    )

    assert parsed == [
        ("draw_no_bet", "home", 1.25),
        ("draw_no_bet", "away", 3.45),
    ]
