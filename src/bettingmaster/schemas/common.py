"""Pydantic response schemas for the API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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


class MatchOut(BaseModel):
    id: str
    league_id: str
    home_team: str
    away_team: str
    start_time: datetime
    status: str

    model_config = {"from_attributes": True}


class MatchDetailOut(MatchOut):
    odds: list[OddsOut] = Field(default_factory=list)


class BestOddsSelection(BaseModel):
    selection: str
    odds: float
    bookmaker: str
    url: Optional[str] = None
    scraped_at: datetime
    checked_at: Optional[datetime] = None


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


class OddsHistoryPoint(BaseModel):
    bookmaker: str
    odds: float
    scraped_at: datetime

    model_config = {"from_attributes": True}


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
