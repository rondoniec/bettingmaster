"""Periodic scraping scheduler using APScheduler."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from bettingmaster.config import settings
from bettingmaster.database import SessionLocal

logger = logging.getLogger(__name__)

# Registry of implemented scrapers
SCRAPER_CLASSES = {}


def _register_scrapers():
    """Import and register all scraper classes."""
    from bettingmaster.scrapers.nike import NikeScraper
    from bettingmaster.scrapers.fortuna import FortunaScraper
    from bettingmaster.scrapers.doxxbet import DoxxbetScraper
    from bettingmaster.scrapers.tipsport import TipsportScraper
    from bettingmaster.scrapers.tipos import TiposScraper
    from bettingmaster.scrapers.polymarket import PolymarketScraper

    SCRAPER_CLASSES["nike"] = NikeScraper
    SCRAPER_CLASSES["fortuna"] = FortunaScraper
    SCRAPER_CLASSES["doxxbet"] = DoxxbetScraper
    SCRAPER_CLASSES["tipsport"] = TipsportScraper
    SCRAPER_CLASSES["tipos"] = TiposScraper
    SCRAPER_CLASSES["polymarket"] = PolymarketScraper


_LEAGUELESS_BOOKMAKERS = {"polymarket"}


def run_scraper(bookmaker: str):
    """Run a single scraper by bookmaker name."""
    if not SCRAPER_CLASSES:
        _register_scrapers()

    cls = SCRAPER_CLASSES.get(bookmaker)
    if not cls:
        logger.error(f"Unknown bookmaker: {bookmaker}")
        return

    db = SessionLocal()
    try:
        scraper = cls(db_session=db)

        # Polymarket and other global scrapers don't need per-league external IDs
        if bookmaker in _LEAGUELESS_BOOKMAKERS:
            from bettingmaster.normalizer import TeamNormalizer
            normalizer = TeamNormalizer(db_session=db)
            scraper.run(league_ids=None, normalizer=normalizer)
            return

        # Get leagues that have external IDs for this bookmaker
        from bettingmaster.models.league import League

        leagues = db.query(League).all()
        league_map = {}
        for league in leagues:
            ext_ids = league.external_ids or {}
            if bookmaker in ext_ids:
                league_map[league.id] = ext_ids[bookmaker]

        if not league_map:
            logger.debug(f"[{bookmaker}] No leagues configured with external IDs")
            return

        from bettingmaster.normalizer import TeamNormalizer

        normalizer = TeamNormalizer(db_session=db)
        scraper.run(league_map, normalizer=normalizer)

    except NotImplementedError as e:
        logger.debug(f"[{bookmaker}] {e}")
    except Exception:
        logger.exception(f"[{bookmaker}] Scraper failed")
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    _register_scrapers()
    scheduler = BackgroundScheduler()

    for bm, interval_attr in [
        ("nike", "scrape_interval_nike"),
        ("fortuna", "scrape_interval_fortuna"),
        ("doxxbet", "scrape_interval_doxxbet"),
        ("tipsport", "scrape_interval_tipsport"),
        ("tipos", "scrape_interval_tipos"),
        ("polymarket", "scrape_interval_polymarket"),
    ]:
        scheduler.add_job(
            run_scraper,
            "interval",
            seconds=getattr(settings, interval_attr),
            args=[bm],
            id=f"{bm}_scraper",
            max_instances=1,
            misfire_grace_time=30,
        )

    return scheduler
