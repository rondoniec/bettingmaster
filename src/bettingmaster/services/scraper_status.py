from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.models.scrape_run import ScrapeRun

logger = logging.getLogger(__name__)

SUCCESS_STATUSES = ("success", "partial")
FAILURE_STATUSES = ("failed", "partial")


@dataclass
class ScrapeRunSummary:
    bookmaker: str
    source: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    finished_at: datetime | None = None
    matches_found: int = 0
    odds_saved: int = 0
    success_events: int = 0
    failure_events: int = 0
    error_message: str | None = None

    @property
    def status(self) -> str:
        if self.failure_events and self.success_events:
            return "partial"
        if self.failure_events:
            return "failed"
        return "success"

    def mark_success(self, count: int = 1) -> None:
        self.success_events += count

    def mark_failure(self, error: BaseException | str, count: int = 1) -> None:
        self.failure_events += count
        self.error_message = summarize_error(error)

    def finalize(self) -> "ScrapeRunSummary":
        if self.finished_at is None:
            self.finished_at = datetime.now(UTC).replace(tzinfo=None)
        return self


SessionFactory = Callable[[], Session]


def summarize_error(error: BaseException | str | None) -> str | None:
    if error is None:
        return None
    if isinstance(error, str):
        message = error.strip()
    else:
        detail = str(error).strip()
        message = f"{error.__class__.__name__}: {detail}" if detail else error.__class__.__name__
    if not message:
        return None
    return message[:500]


def persist_scrape_run_summary(session_factory: SessionFactory, summary: ScrapeRunSummary) -> None:
    db = session_factory()
    try:
        summary.finalize()
        db.add(
            ScrapeRun(
                bookmaker=summary.bookmaker,
                source=summary.source,
                started_at=summary.started_at,
                finished_at=summary.finished_at,
                status=summary.status,
                matches_found=summary.matches_found,
                odds_saved=summary.odds_saved,
                error_message=summary.error_message,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("[%s] Failed to persist scrape run summary", summary.bookmaker)
    finally:
        db.close()


def empty_scraper_status() -> dict[str, datetime | str | int | None]:
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


def get_scraper_status_map(
    db: Session,
    bookmakers: Sequence[str],
) -> dict[str, dict[str, datetime | str | int | None]]:
    statuses = {bookmaker: empty_scraper_status() for bookmaker in bookmakers}

    odds_rows = (
        db.query(
            OddsSnapshot.bookmaker.label("bookmaker"),
            func.max(func.coalesce(OddsSnapshot.checked_at, OddsSnapshot.scraped_at)).label(
                "last_scraped_at"
            ),
        )
        .group_by(OddsSnapshot.bookmaker)
        .all()
    )
    for row in odds_rows:
        statuses.setdefault(row.bookmaker, empty_scraper_status())
        statuses[row.bookmaker]["last_scraped_at"] = row.last_scraped_at

    latest_runs = (
        db.query(
            ScrapeRun.bookmaker.label("bookmaker"),
            ScrapeRun.started_at.label("started_at"),
            ScrapeRun.status.label("status"),
            ScrapeRun.matches_found.label("matches_found"),
            ScrapeRun.odds_saved.label("odds_saved"),
            ScrapeRun.error_message.label("error_message"),
            func.row_number()
            .over(
                partition_by=ScrapeRun.bookmaker,
                order_by=(ScrapeRun.started_at.desc(), ScrapeRun.id.desc()),
            )
            .label("position"),
        )
        .subquery()
    )
    latest_rows = (
        db.query(
            latest_runs.c.bookmaker,
            latest_runs.c.started_at,
            latest_runs.c.status,
            latest_runs.c.matches_found,
            latest_runs.c.odds_saved,
            latest_runs.c.error_message,
        )
        .filter(latest_runs.c.position == 1)
        .all()
    )
    for row in latest_rows:
        statuses.setdefault(row.bookmaker, empty_scraper_status())
        statuses[row.bookmaker].update(
            {
                "last_run_at": row.started_at,
                "last_status": row.status,
                "matches_found": row.matches_found,
                "odds_saved": row.odds_saved,
                "last_error": row.error_message,
            }
        )

    success_rows = (
        db.query(
            ScrapeRun.bookmaker.label("bookmaker"),
            func.max(ScrapeRun.finished_at).label("last_success_at"),
        )
        .filter(ScrapeRun.status.in_(SUCCESS_STATUSES))
        .group_by(ScrapeRun.bookmaker)
        .all()
    )
    for row in success_rows:
        statuses.setdefault(row.bookmaker, empty_scraper_status())
        statuses[row.bookmaker]["last_success_at"] = row.last_success_at

    failure_rows = (
        db.query(
            ScrapeRun.bookmaker.label("bookmaker"),
            func.max(ScrapeRun.finished_at).label("last_failure_at"),
        )
        .filter(ScrapeRun.status.in_(FAILURE_STATUSES))
        .group_by(ScrapeRun.bookmaker)
        .all()
    )
    for row in failure_rows:
        statuses.setdefault(row.bookmaker, empty_scraper_status())
        statuses[row.bookmaker]["last_failure_at"] = row.last_failure_at

    return statuses
