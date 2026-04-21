from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from bettingmaster.database import get_db
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.scheduler import BOOKMAKER_INTERVAL_ATTRS

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    # Check DB connection
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    # Last saved odds per bookmaker. Include configured scrapers even before
    # they save data so health output does not hide failing/empty scrapers.
    scrapers = {
        bookmaker: {"last_scraped_at": None}
        for bookmaker, _ in BOOKMAKER_INTERVAL_ATTRS
    }
    rows = (
        db.query(OddsSnapshot.bookmaker, func.max(OddsSnapshot.scraped_at))
        .group_by(OddsSnapshot.bookmaker)
        .all()
    )
    for bookmaker, last_ts in rows:
        scrapers.setdefault(bookmaker, {"last_scraped_at": None})
        scrapers[bookmaker]["last_scraped_at"] = str(last_ts) if last_ts else None

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "db": db_status,
        "scrapers": scrapers,
    }
