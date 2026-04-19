from __future__ import annotations

from datetime import UTC, datetime

from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.scrapers.fortuna import FortunaScraper


def test_fortuna_scraper_persists_match_and_supported_markets(db_session, monkeypatch):
    fixture_id = "ufo:mtch:test-001"
    tournament_id = "ufo:tour:00-062"
    start_time = datetime(2026, 4, 12, 18, 0, tzinfo=UTC)
    fixture_payload = {
        "fixtures": [
            {
                "id": fixture_id,
                "kind": "PREMATCH",
                "startDatetime": int(start_time.timestamp() * 1000),
                "name": "Slovan Bratislava - Spartak Trnava",
                "participants": [
                    {"type": "HOME", "name": "Slovan Bratislava"},
                    {"type": "AWAY", "name": "Spartak Trnava"},
                ],
                "seoName": "slovan-bratislava-spartak-trnava",
                "categorySeoName": "slovensko",
                "tournamentSeoName": "nike-liga",
                "sportSeoName": "futbal",
            }
        ]
    }
    markets_payload = [
        {
            "name": "V\u00fdsledok z\u00e1pasu",
            "outcomes": [
                {"name": "1", "odds": 2.45},
                {"name": "0", "odds": 3.5},
                {"name": "2", "odds": 2.95},
            ],
        },
        {
            "name": "Oba t\u00edmy daj\u00fa g\u00f3l",
            "outcomes": [
                {"name": "\u00c1no", "odds": 1.82},
                {"name": "Nie", "odds": 1.98},
            ],
        },
        {
            "name": "Po\u010det g\u00f3lov 2.5",
            "outcomes": [
                {"name": "+ 2.5", "odds": 1.91},
                {"name": "- 2.5", "odds": 1.87},
            ],
        },
        {
            "name": "Nezn\u00e1my market",
            "outcomes": [
                {"name": "foo", "odds": 9.99},
            ],
        },
    ]

    def fake_api_get(path: str):
        if path.endswith(f"/tournament/{tournament_id}/matches"):
            return fixture_payload
        if path.endswith(f"/fixture/{fixture_id}/markets"):
            return markets_payload
        raise AssertionError(f"Unexpected path: {path}")

    scraper = FortunaScraper(db_session=db_session)
    monkeypatch.setattr(scraper, "_api_get", fake_api_get)

    scraper.run({"sk-fortuna-liga": tournament_id})

    matches = db_session.query(Match).all()
    assert len(matches) == 1
    assert matches[0].home_team == "Slovan Bratislava"
    assert matches[0].away_team == "Spartak Trnava"
    assert matches[0].external_ids == {"fortuna": fixture_id}

    odds = (
        db_session.query(OddsSnapshot)
        .order_by(OddsSnapshot.market, OddsSnapshot.selection)
        .all()
    )
    assert len(odds) == 7
    assert {(item.market, item.selection) for item in odds} == {
        ("1x2", "away"),
        ("1x2", "draw"),
        ("1x2", "home"),
        ("btts", "no"),
        ("btts", "yes"),
        ("over_under_2.5", "over"),
        ("over_under_2.5", "under"),
    }
