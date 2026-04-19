from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from bettingmaster.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, echo=False)


# Enable WAL mode for SQLite (allows concurrent reads)
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    if dbapi_conn.__class__.__module__ != "sqlite3":
        return
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    import bettingmaster.models  # noqa: F401 — registers models with Base
    Base.metadata.create_all(bind=engine)
