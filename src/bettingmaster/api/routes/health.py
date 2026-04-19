from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from bettingmaster.database import get_db
from bettingmaster.models.odds import OddsSnapshot

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    # Check DB connection
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    # Last scrape per bookmaker
    scrapers = {}
    rows = (
        db.query(OddsSnapshot.bookmaker, func.max(OddsSnapshot.scraped_at))
        .group_by(OddsSnapshot.bookmaker)
        .all()
    )
    for bookmaker, last_ts in rows:
        scrapers[bookmaker] = str(last_ts) if last_ts else None

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "db": db_status,
        "scrapers": scrapers,
    }
