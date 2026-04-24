from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect

from bettingmaster.database import Base
import bettingmaster.models  # noqa: F401
from bettingmaster.migrations import upgrade_database


def test_alembic_upgrade_creates_schema(tmp_path):
    database_path = tmp_path / "migration-test.db"
    database_url = f"sqlite:///{Path(database_path).as_posix()}"

    upgrade_database(database_url=database_url)

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert sorted(inspector.get_table_names()) == [
        "alembic_version",
        "leagues",
        "matches",
        "odds_snapshots",
        "scrape_runs",
        "sports",
        "team_aliases",
    ]

    odds_indexes = {index["name"] for index in inspector.get_indexes("odds_snapshots")}
    assert {"ix_odds_lookup", "ix_odds_scraped_at", "ix_odds_checked_at"} <= odds_indexes

    scrape_run_indexes = {index["name"] for index in inspector.get_indexes("scrape_runs")}
    assert {
        "ix_scrape_runs_bookmaker_started_at",
        "ix_scrape_runs_bookmaker_finished_at",
        "ix_scrape_runs_bookmaker_status_finished_at",
    } <= scrape_run_indexes
    engine.dispose()


def test_alembic_upgrade_bootstraps_legacy_create_all_database(tmp_path):
    database_path = tmp_path / "legacy-test.db"
    database_url = f"sqlite:///{Path(database_path).as_posix()}"

    engine = create_engine(database_url)
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    upgrade_database(database_url=database_url)

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "alembic_version" in inspector.get_table_names()
    engine.dispose()
