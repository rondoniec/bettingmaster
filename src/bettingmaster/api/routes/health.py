from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from bettingmaster.database import get_db
from bettingmaster.scheduler import BOOKMAKER_INTERVAL_ATTRS
from bettingmaster.schemas.health import HealthOut
from bettingmaster.services.scraper_status import empty_scraper_status, get_scraper_status_map

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health_check(db: Session = Depends(get_db)):
    configured_bookmakers = [bookmaker for bookmaker, _ in BOOKMAKER_INTERVAL_ATTRS]
    scrapers = {
        bookmaker: empty_scraper_status()
        for bookmaker in configured_bookmakers
    }

    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
        scrapers = get_scraper_status_map(db, configured_bookmakers)
    except Exception:
        db_status = "error"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "db": db_status,
        "scrapers": scrapers,
    }
