from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bettingmaster.config import settings
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.models.scrape_run import ScrapeRun


def test_list_matches_supports_tomorrow_filter(client, seeded_db):
    response = client.get("/api/matches", params={"date": "tomorrow"})

    assert response.status_code == 200
    payload = response.json()
    assert [match["id"] for match in payload] == ["match-tomorrow"]


def test_league_matches_supports_date_alias(client, seeded_db):
    response = client.get("/api/leagues/sk-fortuna-liga/matches", params={"date": "2099-01-01"})

    assert response.status_code == 200
    assert response.json() == []


def test_match_detail_filters_latest_odds_by_market_and_bookmaker(client, seeded_db):
    response = client.get(
        "/api/matches/match-upcoming",
        params={"market": "1x2", "bookmakers": "nike"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "match-upcoming"
    assert {odd["bookmaker"] for odd in payload["odds"]} == {"nike"}
    assert len(payload["odds"]) == 3
    assert {odd["selection"] for odd in payload["odds"]} == {"home", "draw", "away"}
    assert all(odd["odds"] != 2.2 for odd in payload["odds"])
    assert {odd["url"] for odd in payload["odds"]} == {"https://www.nike.sk/tipovanie/zapas/1010917852"}


def test_match_detail_excludes_stale_live_odds(client, seeded_db):
    match = seeded_db.get(Match, "match-upcoming")
    assert match is not None
    match.status = "live"

    stale_time = seeded_db.info["seed_now"] - timedelta(hours=2)
    for odds in seeded_db.query(OddsSnapshot).filter(OddsSnapshot.match_id == "match-upcoming"):
        odds.scraped_at = stale_time
    seeded_db.commit()

    response = client.get("/api/matches/match-upcoming")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "live"
    assert payload["odds"] == []


def test_best_odds_returns_top_price_per_selection(client, seeded_db):
    response = client.get("/api/matches/match-upcoming/best-odds", params={"market": "1x2"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    best_market = payload[0]
    assert best_market["market"] == "1x2"
    assert {selection["selection"]: selection["bookmaker"] for selection in best_market["selections"]} == {
        "away": "fortuna",
        "draw": "nike",
        "home": "nike",
    }
    assert {selection["url"] for selection in best_market["selections"]} == {
        "https://www.nike.sk/tipovanie/zapas/1010917852",
        "https://fortuna.example/away",
    }
    assert best_market["combined_margin"] < 0


def test_best_odds_match_list_returns_merged_matches_only(client, seeded_db):
    response = client.get("/api/matches/best-odds", params={"market": "1x2"})

    assert response.status_code == 200
    payload = response.json()
    assert [match["id"] for match in payload] == ["match-upcoming"]

    best_match = payload[0]
    assert best_match["bookmakers"] == ["fortuna", "nike"]
    assert best_match["market"] == "1x2"
    assert {selection["selection"]: selection["bookmaker"] for selection in best_match["selections"]} == {
        "away": "fortuna",
        "draw": "nike",
        "home": "nike",
    }
    assert best_match["combined_margin"] < 0


def test_best_odds_match_list_excludes_stale_live_matches(client, seeded_db):
    match = seeded_db.get(Match, "match-upcoming")
    assert match is not None
    match.status = "live"

    stale_time = seeded_db.info["seed_now"] - timedelta(hours=2)
    for odds in seeded_db.query(OddsSnapshot).filter(OddsSnapshot.match_id == "match-upcoming"):
        odds.scraped_at = stale_time
    seeded_db.commit()

    response = client.get("/api/matches/best-odds", params={"market": "1x2"})

    assert response.status_code == 200
    assert response.json() == []


def test_best_odds_match_list_can_filter_by_league_and_min_bookmakers(client, seeded_db):
    response = client.get(
        "/api/matches/best-odds",
        params={"market": "1x2", "league_id": "sk-tipos-extraliga", "min_bookmakers": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [match["id"] for match in payload] == ["match-hockey"]
    assert payload[0]["bookmakers"] == ["nike"]


def test_get_league_returns_metadata(client, seeded_db):
    response = client.get("/api/leagues/sk-fortuna-liga")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "id": "sk-fortuna-liga",
        "sport_id": "football",
        "name": "Nike Liga",
        "country": "SK",
    }


def test_surebets_can_filter_by_market_and_sport(client, seeded_db):
    match = seeded_db.get(Match, "match-upcoming")
    assert match is not None
    match.start_time = datetime.now(UTC).replace(tzinfo=None, microsecond=0) + timedelta(hours=2)
    seeded_db.commit()

    response = client.get("/api/surebets", params={"sport": "football", "market": "1x2"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["match_id"] == "match-upcoming"
    assert payload[0]["profit_percent"] > 0
    assert {selection["url"] for selection in payload[0]["selections"]} == {
        "https://www.nike.sk/tipovanie/zapas/1010917852",
        "https://fortuna.example/away",
    }


def test_history_can_filter_by_bookmaker(client, seeded_db):
    response = client.get(
        "/api/matches/match-upcoming/history",
        params={"market": "1x2", "bookmakers": "fortuna"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 3
    for market_history in payload:
        assert market_history["market"] == "1x2"
        assert {point["bookmaker"] for point in market_history["history"]} == {"fortuna"}


def test_search_returns_upcoming_matches_only(client, seeded_db):
    response = client.get("/api/search", params={"q": "Slovan"})

    assert response.status_code == 200
    payload = response.json()
    assert [match["id"] for match in payload] == ["match-upcoming"]


def test_ws_odds_feed_pushes_update_for_match_scope(client, seeded_db):
    previous_interval = settings.live_feed_poll_seconds
    settings.live_feed_poll_seconds = 0.01
    update_time = seeded_db.info["seed_now"] + timedelta(minutes=5)
    try:
        with client.websocket_connect("/ws/odds-feed?match_id=match-upcoming") as websocket:
            snapshot = websocket.receive_json()
            assert snapshot["type"] == "snapshot"
            assert snapshot["match_ids"] == ["match-upcoming"]
            assert snapshot["snapshot_count"] == 9

            seeded_db.add(
                OddsSnapshot(
                    match_id="match-upcoming",
                    bookmaker="fortuna",
                    market="1x2",
                    selection="home",
                    odds=2.6,
                    url="https://fortuna.example/home-new",
                    scraped_at=update_time,
                )
            )
            seeded_db.commit()

            update = websocket.receive_json()
            assert update["type"] == "odds_update"
            assert update["match_ids"] == ["match-upcoming"]
            assert update["snapshot_count"] == 10
            assert update["latest_scraped_at"] == update_time.isoformat()
    finally:
        settings.live_feed_poll_seconds = previous_interval


def test_health_returns_enriched_scraper_statuses(client, seeded_db):
    now = seeded_db.info["seed_now"]
    last_failure = now - timedelta(minutes=25)
    last_success = now - timedelta(minutes=10)
    doxxbet_failure = now - timedelta(minutes=4)

    seeded_db.add_all(
        [
            ScrapeRun(
                bookmaker="fortuna",
                source="round_robin",
                started_at=last_failure - timedelta(minutes=1),
                finished_at=last_failure,
                status="failed",
                matches_found=0,
                odds_saved=0,
                error_message="RuntimeError: temporary outage",
            ),
            ScrapeRun(
                bookmaker="fortuna",
                source="round_robin",
                started_at=last_success - timedelta(minutes=2),
                finished_at=last_success,
                status="success",
                matches_found=3,
                odds_saved=9,
                error_message=None,
            ),
            ScrapeRun(
                bookmaker="doxxbet",
                source="round_robin",
                started_at=doxxbet_failure - timedelta(minutes=1),
                finished_at=doxxbet_failure,
                status="failed",
                matches_found=0,
                odds_saved=0,
                error_message="RuntimeError: timeout",
            ),
        ]
    )
    seeded_db.commit()

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["db"] == "connected"

    scrapers = payload["scrapers"]
    assert set(scrapers) >= {"fortuna", "nike", "doxxbet", "tipsport", "tipos", "polymarket"}

    assert scrapers["fortuna"] == {
        "last_scraped_at": (now - timedelta(minutes=2)).isoformat(),
        "last_run_at": (last_success - timedelta(minutes=2)).isoformat(),
        "last_success_at": last_success.isoformat(),
        "last_failure_at": last_failure.isoformat(),
        "last_status": "success",
        "matches_found": 3,
        "odds_saved": 9,
        "last_error": None,
    }
    assert scrapers["doxxbet"]["last_status"] == "failed"
    assert scrapers["doxxbet"]["last_failure_at"] == doxxbet_failure.isoformat()
    assert scrapers["doxxbet"]["last_error"] == "RuntimeError: timeout"
    assert scrapers["tipsport"] == {
        "last_scraped_at": None,
        "last_run_at": None,
        "last_success_at": None,
        "last_failure_at": None,
        "last_status": None,
        "matches_found": 0,
        "odds_saved": 0,
        "last_error": None,
    }
