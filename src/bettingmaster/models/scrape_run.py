from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bettingmaster.database import Base


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bookmaker: Mapped[str] = mapped_column(String(50))
    trigger: Mapped[str] = mapped_column(String(50), default="round_robin")
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20))
    matches_found: Mapped[int] = mapped_column(Integer, default=0)
    odds_saved: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_scrape_runs_bookmaker_started_at", "bookmaker", "started_at"),
        Index("ix_scrape_runs_bookmaker_finished_at", "bookmaker", "finished_at"),
        Index(
            "ix_scrape_runs_bookmaker_status_finished_at",
            "bookmaker",
            "status",
            "finished_at",
        ),
    )
