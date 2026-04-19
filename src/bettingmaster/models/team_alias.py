from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bettingmaster.database import Base


class TeamAlias(Base):
    __tablename__ = "team_aliases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(String(200))
    alias: Mapped[str] = mapped_column(String(200))
    bookmaker: Mapped[str] = mapped_column(String(50))

    __table_args__ = (
        UniqueConstraint("alias", "bookmaker", name="uq_alias_bookmaker"),
    )
