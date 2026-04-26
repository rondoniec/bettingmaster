"""Helpers for invoking Alembic migrations from application code."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from bettingmaster.config import PROJECT_ROOT, settings

EXPECTED_TABLES = {
    "sports",
    "leagues",
    "matches",
    "odds_snapshots",
    "team_aliases",
}


def get_alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(Path(PROJECT_ROOT) / "alembic.ini"))
    config.set_main_option("script_location", str(Path(PROJECT_ROOT) / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url or settings.database_url)
    return config


def _bootstrap_legacy_database(database_url: str) -> bool:
    """Stamp head when a legacy create_all database already matches our schema."""
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        if not table_names or "alembic_version" in table_names:
            return False
        if not EXPECTED_TABLES.issubset(table_names):
            return False
    finally:
        engine.dispose()

    command.stamp(get_alembic_config(database_url), "head")
    return True


def upgrade_database(revision: str = "head", *, database_url: str | None = None) -> None:
    resolved_url = database_url or settings.database_url
    if revision == "head":
        _bootstrap_legacy_database(resolved_url)
    command.upgrade(get_alembic_config(resolved_url), revision)


def current_revision(*, database_url: str | None = None, verbose: bool = False) -> None:
    command.current(get_alembic_config(database_url), verbose=verbose)
