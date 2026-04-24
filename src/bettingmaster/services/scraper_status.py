from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from bettingmaster.database import SessionLocal
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.models.scrape_run import ScrapeRun

_SUCCESS_STATUSES = ("success", "partial")
_FAILURE_STATUSES = ("failed", "partial")


def _default_scraper_status() -> dict[str, object]:
    return {
        "last_scraped_at": None,
        "last_run_at": None,
        "last_success_at": None,
        "last_failure_at": None,
        "last_status": None,
        "matches_found": 0,
        "odds_saved": 0,
        "last_error": None,
    }


def persist_scrape_run(
    *,
    bookmaker: str,
    trigger: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    matches_found: int = 0,
    odds_saved: int = 0,
    last_error: str | None = None,
    session_factory: sessionmaker | None = None,
) -> None:
    db = (session_factory or SessionLocal)()
    try:
        db.add(
            ScrapeRun(
                bookmaker=bookmaker,
                trigger=trigger,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                matches_found=matches_found,
                odds_saved=odds_saved,
                error_message=last_error,
            )
        )
        db.commit()
    finally:
        db.close()


def build_scraper_statuses(db: Session, configured_bookmakers: list[str]) -> dict[str, dict[str, object]]:
    statuses = {
        bookmaker: _default_scraper_status()
        for bookmaker in configured_bookmakers
    }

    odds_rows = (
        db.query(
            OddsSnapshot.bookmaker,
            func.max(func.coalesce(OddsSnapshot.checked_at, OddsSnapshot.scraped_at)),
        )
        .group_by(OddsSnapshot.bookmaker)
        .all()
    )
    for bookmaker, last_ts in odds_rows:
        statuses.setdefault(bookmaker, _default_scraper_status())
        statuses[bookmaker]["last_scraped_at"] = last_ts

    latest_run_ranks = (
        select(
            ScrapeRun.id.label("id"),
            func.row_number()
            .over(
                partition_by=ScrapeRun.bookmaker,
                order_by=[ScrapeRun.started_at.desc(), ScrapeRun.id.desc()],
            )
            .label("row_number"),
        )
        .subquery()
    )
    latest_runs = (
        db.query(ScrapeRun)
        .join(latest_run_ranks, ScrapeRun.id == latest_run_ranks.c.id)
        .filter(latest_run_ranks.c.row_number == 1)
        .all()
    )
    for run in latest_runs:
        statuses.setdefault(run.bookmaker, _default_scraper_status())
        statuses[run.bookmaker].update(
            {
                "last_run_at": run.started_at,
                "last_status": run.status,
                "matches_found": run.matches_found,
                "odds_saved": run.odds_saved,
                "last_error": run.error_message,
            }
        )

    success_rows = (
        db.query(ScrapeRun.bookmaker, func.max(ScrapeRun.finished_at))
        .filter(ScrapeRun.status.in_(_SUCCESS_STATUSES))
        .group_by(ScrapeRun.bookmaker)
        .all()
    )
    for bookmaker, last_ts in success_rows:
        statuses.setdefault(bookmaker, _default_scraper_status())
        statuses[bookmaker]["last_success_at"] = last_ts

    failure_rows = (
        db.query(ScrapeRun.bookmaker, func.max(ScrapeRun.finished_at))
        .filter(ScrapeRun.status.in_(_FAILURE_STATUSES))
        .group_by(ScrapeRun.bookmaker)
        .all()
    )
    for bookmaker, last_ts in failure_rows:
        statuses.setdefault(bookmaker, _default_scraper_status())
        statuses[bookmaker]["last_failure_at"] = last_ts

    return statuses
