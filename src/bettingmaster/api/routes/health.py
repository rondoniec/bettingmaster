from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from bettingmaster.database import get_db
from bettingmaster.scheduler import BOOKMAKER_INTERVAL_ATTRS
from bettingmaster.schemas.health import HealthOut
from bettingmaster.services.scraper_status import build_scraper_statuses

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    scrapers = build_scraper_statuses(
        db,
        [bookmaker for bookmaker, _ in BOOKMAKER_INTERVAL_ATTRS],
    )

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "db": db_status,
        "scrapers": scrapers,
    }
