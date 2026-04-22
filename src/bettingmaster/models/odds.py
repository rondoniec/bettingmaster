from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, Index, String, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bettingmaster.database import Base

if TYPE_CHECKING:
    from bettingmaster.models.match import Match


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"))
    bookmaker: Mapped[str] = mapped_column(String(50))
    market: Mapped[str] = mapped_column(String(50))
    selection: Mapped[str] = mapped_column(String(50))
    odds: Mapped[float] = mapped_column(Float)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    match: Mapped["Match"] = relationship(back_populates="odds_snapshots")

    __table_args__ = (
        Index(
            "ix_odds_lookup",
            "match_id",
            "bookmaker",
            "market",
            "selection",
        ),
        Index("ix_odds_scraped_at", "scraped_at"),
        Index("ix_odds_checked_at", "checked_at"),
    )
