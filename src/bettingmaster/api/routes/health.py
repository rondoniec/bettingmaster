from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from bettingmaster.config import settings
from bettingmaster.database import get_db
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.schemas.common import HealthOut
from bettingmaster.scheduler import BOOKMAKER_INTERVAL_ATTRS

router = APIRouter()


def _freshness_from_age(age_seconds: int | None, interval_seconds: int) -> str:
    if age_seconds is None:
        return "idle"

    fresh_threshold = max(interval_seconds * 2, 120)
    aging_threshold = max(interval_seconds * 6, 600)
    if age_seconds <= fresh_threshold:
        return "fresh"
    if age_seconds <= aging_threshold:
        return "aging"
    return "stale"


@router.get("/health", response_model=HealthOut)
def health_check(db: Session = Depends(get_db)):
    # Check DB connection
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    # Last saved odds per bookmaker. Include configured scrapers even before
    # they save data so health output does not hide failing/empty scrapers.
    now = datetime.now(UTC).replace(tzinfo=None)
    scrapers = {}
    interval_lookup = {
        bookmaker: getattr(settings, interval_attr)
        for bookmaker, interval_attr in BOOKMAKER_INTERVAL_ATTRS
    }
    for bookmaker, interval_seconds in interval_lookup.items():
        scrapers[bookmaker] = {
            "last_scraped_at": None,
            "interval_seconds": interval_seconds,
            "age_seconds": None,
            "freshness": "idle",
        }

    rows = (
        db.query(
            OddsSnapshot.bookmaker,
            func.max(func.coalesce(OddsSnapshot.checked_at, OddsSnapshot.scraped_at)),
        )
        .group_by(OddsSnapshot.bookmaker)
        .all()
    )
    for bookmaker, last_ts in rows:
        interval_seconds = interval_lookup.get(bookmaker, settings.scrape_interval_default)
        age_seconds = (
            max(0, int((now - last_ts).total_seconds()))
            if last_ts is not None
            else None
        )
        scrapers[bookmaker] = {
            "last_scraped_at": last_ts,
            "interval_seconds": interval_seconds,
            "age_seconds": age_seconds,
            "freshness": _freshness_from_age(age_seconds, interval_seconds),
        }

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "db": db_status,
        "scrapers": scrapers,
    }
