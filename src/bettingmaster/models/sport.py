from typing import List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bettingmaster.database import Base


class Sport(Base):
    __tablename__ = "sports"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    leagues: Mapped[List["League"]] = relationship(back_populates="sport")  # noqa: F821
