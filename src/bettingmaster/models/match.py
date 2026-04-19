from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bettingmaster.database import Base

if TYPE_CHECKING:
    from bettingmaster.models.league import League


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.id"))
    home_team: Mapped[str] = mapped_column(String(200))
    away_team: Mapped[str] = mapped_column(String(200))
    start_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="prematch")
    external_ids: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSON),
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    league: Mapped["League"] = relationship(back_populates="matches")
    odds_snapshots: Mapped[List["OddsSnapshot"]] = relationship(  # noqa: F821
        back_populates="match"
    )
