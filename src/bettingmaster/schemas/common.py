"""Pydantic response schemas for the API."""

from datetime import UTC, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_serializer


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Naive datetimes from the DB are UTC; tag them so JSON gets a 'Z' suffix."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SportOut(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class LeagueOut(BaseModel):
    id: str
    sport_id: str
    name: str
    country: str

    model_config = {"from_attributes": True}


class OddsOut(BaseModel):
    bookmaker: str
    market: str
    selection: str
    odds: float
    url: Optional[str] = None
    scraped_at: datetime
    checked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_serializer("scraped_at", "checked_at")
    def _utc_ts(self, v):
        return _ensure_utc(v)


class MatchOut(BaseModel):
    id: str
    league_id: str
    home_team: str
    away_team: str
    start_time: datetime
    status: str

    model_config = {"from_attributes": True}

    @field_serializer("start_time")
    def _utc_ts(self, v):
        return _ensure_utc(v)


class MatchDetailOut(MatchOut):
    odds: list[OddsOut] = Field(default_factory=list)


class BestOddsSelection(BaseModel):
    selection: str
    odds: float
    bookmaker: str
    url: Optional[str] = None
    scraped_at: datetime
    checked_at: Optional[datetime] = None

    @field_serializer("scraped_at", "checked_at")
    def _utc_ts(self, v):
        return _ensure_utc(v)


class BestOddsOut(BaseModel):
    match_id: str
    market: str
    selections: list[BestOddsSelection]
    combined_margin: float


class MatchBestOddsOut(MatchOut):
    market: str
    selections: list[BestOddsSelection]
    combined_margin: float
    bookmakers: list[str] = Field(default_factory=list)


class SurebetSelection(BaseModel):
    selection: str
    odds: float
    bookmaker: str
    url: Optional[str] = None
    scraped_at: datetime
    checked_at: Optional[datetime] = None

    @field_serializer("scraped_at", "checked_at")
    def _utc_ts(self, v):
        return _ensure_utc(v)


class SurebetOut(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league_id: str
    start_time: datetime
    market: str
    selections: list[SurebetSelection]
    margin: float  # negative = guaranteed profit, e.g. -2.3 means 2.3% profit
    profit_percent: float  # abs(margin) when margin < 0

    @field_serializer("start_time")
    def _utc_ts(self, v):
        return _ensure_utc(v)


class OddsHistoryPoint(BaseModel):
    bookmaker: str
    odds: float
    scraped_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("scraped_at")
    def _utc_ts(self, v):
        return _ensure_utc(v)


class OddsHistoryOut(BaseModel):
    market: str
    selection: str
    history: list[OddsHistoryPoint]


class MatchSearchResult(BaseModel):
    id: str
    home_team: str
    away_team: str
    league_id: str
    start_time: datetime
    status: str

    model_config = {"from_attributes": True}

    @field_serializer("start_time")
    def _utc_ts(self, v):
        return _ensure_utc(v)


class ScraperHealthOut(BaseModel):
    last_scraped_at: Optional[datetime] = None
    interval_seconds: int
    age_seconds: Optional[int] = None
    freshness: str

    @field_serializer("last_scraped_at")
    def _utc_ts(self, v):
        return _ensure_utc(v)


class HealthOut(BaseModel):
    status: str
    db: str
    scrapers: dict[str, ScraperHealthOut]
