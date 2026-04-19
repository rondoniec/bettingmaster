from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bettingmaster.database import Base

if TYPE_CHECKING:
    from bettingmaster.models.sport import Sport


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"))
    name: Mapped[str] = mapped_column(String(200))
    country: Mapped[str] = mapped_column(String(10))
    external_ids: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    sport: Mapped["Sport"] = relationship(back_populates="leagues")
    matches: Mapped[List["Match"]] = relationship(back_populates="league")  # noqa: F821
