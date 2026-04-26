from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from bettingmaster.api.app import create_app
from bettingmaster.config import settings
from bettingmaster.database import Base, get_db
from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.models.sport import Sport


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.info["session_factory"] = TestingSessionLocal
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def _disable_active_scope_for_tests():
    previous_leagues = settings.active_league_ids
    previous_window = settings.active_match_window_hours
    previous_lookback = settings.active_match_lookback_hours
    previous_auto_upgrade = settings.auto_upgrade_db_on_startup
    previous_enable_scheduler = settings.enable_scheduler
    settings.active_league_ids = ""
    settings.active_match_window_hours = 24 * 365
    settings.active_match_lookback_hours = 24 * 365
    settings.auto_upgrade_db_on_startup = False
    settings.enable_scheduler = False
    try:
        yield
    finally:
        settings.active_league_ids = previous_leagues
        settings.active_match_window_hours = previous_window
        settings.active_match_lookback_hours = previous_lookback
        settings.auto_upgrade_db_on_startup = previous_auto_upgrade
        settings.enable_scheduler = previous_enable_scheduler


@pytest.fixture()
def client(db_session: Session):
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.state.session_factory = db_session.info["session_factory"]
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def seeded_db(db_session: Session) -> Session:
    real_local_now = datetime.now(ZoneInfo(settings.timezone)).replace(second=0, microsecond=0)
    now = real_local_now.astimezone(UTC).replace(tzinfo=None)
    db_session.info["seed_now"] = now

    # Pin match schedules to local midday so date-based API tests do not drift
    # when the suite runs close to midnight in the configured timezone.
    schedule_local_now = real_local_now.replace(
        hour=12,
        minute=0,
        second=0,
        microsecond=0,
    )
    schedule_now = schedule_local_now.astimezone(UTC).replace(tzinfo=None)

    db_session.add_all([
        Sport(id="football", name="Football"),
        Sport(id="hockey", name="Hockey"),
        League(id="sk-fortuna-liga", sport_id="football", name="Nike Liga", country="SK"),
        League(id="sk-tipos-extraliga", sport_id="hockey", name="Tipos Extraliga", country="SK"),
    ])

    upcoming_match = Match(
        id="match-upcoming",
        league_id="sk-fortuna-liga",
        home_team="Slovan Bratislava",
        away_team="Spartak Trnava",
        start_time=schedule_now + timedelta(hours=6),
        status="prematch",
        external_ids={"nike": "1010917852", "fortuna": "ufo:match:1"},
    )
    tomorrow_match = Match(
        id="match-tomorrow",
        league_id="sk-fortuna-liga",
        home_team="MSK Zilina",
        away_team="DAC 1904",
        start_time=schedule_now + timedelta(days=1, hours=3),
        status="prematch",
    )
    finished_match = Match(
        id="match-finished",
        league_id="sk-fortuna-liga",
        home_team="Kosice",
        away_team="Trencin",
        start_time=schedule_now - timedelta(days=2),
        status="finished",
    )
    hockey_match = Match(
        id="match-hockey",
        league_id="sk-tipos-extraliga",
        home_team="Kosice HC",
        away_team="Nitra HC",
        start_time=schedule_now + timedelta(hours=8),
        status="prematch",
        external_ids={"nike": "1010917999"},
    )
    db_session.add_all([upcoming_match, tomorrow_match, finished_match, hockey_match])

    db_session.add_all([
        OddsSnapshot(
            match_id="match-upcoming",
            bookmaker="fortuna",
            market="1x2",
            selection="home",
            odds=2.4,
            url="https://fortuna.example/home",
            scraped_at=now - timedelta(minutes=5),
        ),
        OddsSnapshot(
            match_id="match-upcoming",
            bookmaker="fortuna",
            market="1x2",
            selection="draw",
            odds=3.3,
            url="https://fortuna.example/draw",
            scraped_at=now - timedelta(minutes=5),
        ),
        OddsSnapshot(
            match_id="match-upcoming",
            bookmaker="fortuna",
            market="1x2",
            selection="away",
            odds=3.5,
            url="https://fortuna.example/away",
            scraped_at=now - timedelta(minutes=5),
        ),
        OddsSnapshot(
            match_id="match-upcoming",
            bookmaker="nike",
            market="1x2",
            selection="home",
            odds=2.55,
            url="https://nike.example/home",
            scraped_at=now - timedelta(minutes=2),
        ),
        OddsSnapshot(
            match_id="match-upcoming",
            bookmaker="nike",
            market="1x2",
            selection="draw",
            odds=3.6,
            url="https://nike.example/draw",
            scraped_at=now - timedelta(minutes=2),
        ),
        OddsSnapshot(
            match_id="match-upcoming",
            bookmaker="nike",
            market="1x2",
            selection="away",
            odds=3.4,
            url="https://nike.example/away",
            scraped_at=now - timedelta(minutes=2),
        ),
        OddsSnapshot(
            match_id="match-upcoming",
            bookmaker="fortuna",
            market="1x2",
            selection="home",
            odds=2.2,
            url="https://fortuna.example/home-old",
            scraped_at=now - timedelta(hours=1),
        ),
        OddsSnapshot(
            match_id="match-upcoming",
            bookmaker="fortuna",
            market="btts",
            selection="yes",
            odds=1.85,
            url="https://fortuna.example/btts-yes",
            scraped_at=now - timedelta(minutes=2),
        ),
        OddsSnapshot(
            match_id="match-upcoming",
            bookmaker="fortuna",
            market="btts",
            selection="no",
            odds=1.95,
            url="https://fortuna.example/btts-no",
            scraped_at=now - timedelta(minutes=2),
        ),
        OddsSnapshot(
            match_id="match-hockey",
            bookmaker="nike",
            market="1x2",
            selection="home",
            odds=1.9,
            url="https://nike.example/h-home",
            scraped_at=now - timedelta(minutes=1),
        ),
        OddsSnapshot(
            match_id="match-hockey",
            bookmaker="nike",
            market="1x2",
            selection="away",
            odds=2.1,
            url="https://nike.example/h-away",
            scraped_at=now - timedelta(minutes=1),
        ),
    ])
    db_session.commit()
    return db_session
