from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScraperHealthOut(BaseModel):
    last_scraped_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_status: Optional[str] = None
    matches_found: int = 0
    odds_saved: int = 0
    last_error: Optional[str] = None


class HealthOut(BaseModel):
    status: str
    db: str
    scrapers: dict[str, ScraperHealthOut] = Field(default_factory=dict)
