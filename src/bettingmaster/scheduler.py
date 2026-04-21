"""Periodic scraping scheduler using APScheduler."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from bettingmaster.config import settings
from bettingmaster.database import SessionLocal
from bettingmaster.match_identity import MATCH_SCORE_THRESHOLD, match_similarity, find_similar_match
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.scrapers.base import RawMatch, generate_match_id

logger = logging.getLogger(__name__)

# Registry of implemented scrapers
SCRAPER_CLASSES = {}

BOOKMAKER_INTERVAL_ATTRS = [
    ("nike", "scrape_interval_nike"),
    ("fortuna", "scrape_interval_fortuna"),
    ("doxxbet", "scrape_interval_doxxbet"),
    ("tipsport", "scrape_interval_tipsport"),
    ("tipos", "scrape_interval_tipos"),
    ("polymarket", "scrape_interval_polymarket"),
]


@dataclass
class RoundRobinWorkItem:
    bookmaker: str
    league_id: str
    match_id: str
    home_team: str
    away_team: str
    start_time: datetime
    status: str
    raw_match: RawMatch


_last_round_robin_run: dict[str, datetime] = {}


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


def _bookmaker_priority(bookmaker: str) -> int:
    order = [name for name, _ in BOOKMAKER_INTERVAL_ATTRS]
    try:
        return order.index(bookmaker)
    except ValueError:
        return len(order)


def _configured_league_map(db, bookmaker: str) -> dict[str, str]:
    from bettingmaster.models.league import League

    leagues = db.query(League).all()
    league_map: dict[str, str] = {}
    for league in leagues:
        ext_ids = league.external_ids or {}
        if bookmaker in ext_ids:
            league_map[league.id] = ext_ids[bookmaker]
    return league_map


def _build_round_robin_work_items(
    discovered_matches: list[RoundRobinWorkItem],
) -> list[RoundRobinWorkItem]:
    discovered_matches = _coalesce_discovered_matches(discovered_matches)
    grouped: dict[str, list[RoundRobinWorkItem]] = {}
    for item in discovered_matches:
        grouped.setdefault(item.match_id, []).append(item)

    ordered: list[RoundRobinWorkItem] = []
    for _, items in sorted(
        grouped.items(),
        key=lambda pair: (
            min(item.start_time for item in pair[1]),
            min(item.home_team for item in pair[1]),
            min(item.away_team for item in pair[1]),
            pair[0],
        ),
    ):
        ordered.extend(
            sorted(
                items,
                key=lambda item: (
                    _bookmaker_priority(item.bookmaker),
                    item.bookmaker,
                ),
            )
        )

    return ordered


def _coalesce_discovered_matches(
    discovered_matches: list[RoundRobinWorkItem],
) -> list[RoundRobinWorkItem]:
    representatives: list[RoundRobinWorkItem] = []
    ordered = sorted(
        discovered_matches,
        key=lambda item: (
            item.start_time,
            item.league_id,
            _bookmaker_priority(item.bookmaker),
            item.home_team,
            item.away_team,
        ),
    )

    for item in ordered:
        representative = _find_discovered_representative(item, representatives)
        if representative is None:
            representatives.append(item)
            continue

        item.match_id = representative.match_id
        item.home_team = representative.home_team
        item.away_team = representative.away_team
        item.start_time = representative.start_time

    return discovered_matches


def _find_discovered_representative(
    item: RoundRobinWorkItem,
    representatives: list[RoundRobinWorkItem],
) -> RoundRobinWorkItem | None:
    best: tuple[float, RoundRobinWorkItem] | None = None
    for candidate in representatives:
        if candidate.league_id != item.league_id:
            continue
        if abs(candidate.start_time - item.start_time).total_seconds() > 3 * 60 * 60:
            continue

        score, swapped = match_similarity(
            item.home_team,
            item.away_team,
            candidate.home_team,
            candidate.away_team,
        )
        if swapped:
            continue
        if score < MATCH_SCORE_THRESHOLD:
            continue
        if best is None or score > best[0]:
            best = (score, candidate)

    return best[1] if best else None


def _upsert_match_record(db, item: RoundRobinWorkItem) -> Match:
    match = db.get(Match, item.match_id)
    if match is None:
        match = Match(
            id=item.match_id,
            league_id=item.league_id,
            home_team=item.home_team,
            away_team=item.away_team,
            start_time=item.start_time,
            status=item.status,
            external_ids={item.bookmaker: item.raw_match.external_id},
        )
        db.add(match)
    else:
        ext = dict(match.external_ids or {})
        ext[item.bookmaker] = item.raw_match.external_id
        match.external_ids = ext
        match.start_time = item.start_time
        if item.status == "live" or match.status != "live":
            match.status = item.status

    db.flush()
    return match


def _persist_odds_snapshots(db, item: RoundRobinWorkItem, odds_rows):
    now = datetime.now(UTC).replace(tzinfo=None)
    for raw_odds in odds_rows:
        db.add(
            OddsSnapshot(
                match_id=item.match_id,
                bookmaker=item.bookmaker,
                market=raw_odds.market,
                selection=raw_odds.selection,
                odds=raw_odds.odds,
                url=raw_odds.url,
                scraped_at=now,
            )
        )


def _discover_round_robin_matches(
    db,
    bookmaker: str,
    scraper,
    league_map: dict[str, str],
    normalizer,
) -> list[RoundRobinWorkItem]:
    discovered: list[RoundRobinWorkItem] = []

    for league_id, ext_id in league_map.items():
        try:
            raw_matches = scraper.scrape_matches(ext_id)
        except Exception:
            logger.exception(f"[{bookmaker}] Failed to discover matches in {league_id}")
            continue

        logger.info(f"[{bookmaker}] Discovered {len(raw_matches)} matches in {league_id}")
        for raw_match in raw_matches:
            try:
                home = normalizer.normalize(raw_match.home_team, bookmaker) or raw_match.home_team
                away = normalizer.normalize(raw_match.away_team, bookmaker) or raw_match.away_team
                match_id = generate_match_id(
                    league_id,
                    home,
                    away,
                    raw_match.start_time.strftime("%Y-%m-%d"),
                )
                existing_match = find_similar_match(
                    db,
                    league_id,
                    home,
                    away,
                    raw_match.start_time,
                )
                if existing_match is not None:
                    match_id = existing_match.id
                    home = existing_match.home_team
                    away = existing_match.away_team
                discovered.append(
                    RoundRobinWorkItem(
                        bookmaker=bookmaker,
                        league_id=league_id,
                        match_id=match_id,
                        home_team=home,
                        away_team=away,
                        start_time=raw_match.start_time,
                        status=raw_match.status,
                        raw_match=raw_match,
                    )
                )
            except Exception:
                logger.exception(
                    f"[{bookmaker}] Failed to prepare discovered match "
                    f"{raw_match.home_team} vs {raw_match.away_team}"
                )

    return discovered


def _due_bookmakers(now: datetime) -> list[str]:
    due: list[str] = []
    for bookmaker, interval_attr in BOOKMAKER_INTERVAL_ATTRS:
        interval_seconds = getattr(settings, interval_attr)
        last_run = _last_round_robin_run.get(bookmaker)
        if last_run is None or (now - last_run).total_seconds() >= interval_seconds:
            due.append(bookmaker)
    return due


def _round_robin_tick_seconds() -> int:
    min_interval = min(getattr(settings, attr) for _, attr in BOOKMAKER_INTERVAL_ATTRS)
    return max(15, min(60, max(1, min_interval // 4)))


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

        if bookmaker in _LEAGUELESS_BOOKMAKERS:
            from bettingmaster.normalizer import TeamNormalizer

            normalizer = TeamNormalizer(db_session=db)
            scraper.run(league_ids=None, normalizer=normalizer)
            return

        league_map = _configured_league_map(db, bookmaker)
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


def run_round_robin_cycle(force_bookmakers: list[str] | None = None):
    """Run one round-robin scrape cycle across due bookmakers."""
    if not SCRAPER_CLASSES:
        _register_scrapers()

    now = datetime.now(UTC)
    due_bookmakers = force_bookmakers or _due_bookmakers(now)
    if not due_bookmakers:
        logger.debug("No bookmakers due for round-robin scrape")
        return

    db = SessionLocal()
    scrapers = {}
    try:
        from bettingmaster.normalizer import TeamNormalizer

        normalizer = TeamNormalizer(db_session=db)
        discovered: list[RoundRobinWorkItem] = []

        for bookmaker in due_bookmakers:
            cls = SCRAPER_CLASSES.get(bookmaker)
            if not cls:
                logger.error(f"Unknown bookmaker: {bookmaker}")
                continue

            scraper = cls(db_session=db)
            scrapers[bookmaker] = scraper

            if bookmaker in _LEAGUELESS_BOOKMAKERS:
                continue

            league_map = _configured_league_map(db, bookmaker)
            if not league_map:
                logger.debug(f"[{bookmaker}] No leagues configured with external IDs")
                _last_round_robin_run[bookmaker] = now
                continue

            discovered.extend(
                _discover_round_robin_matches(db, bookmaker, scraper, league_map, normalizer)
            )

        work_items = _build_round_robin_work_items(discovered)
        logger.info(
            "Round-robin scrape cycle: %s bookmakers due, %s discovered entries, %s work items",
            len(due_bookmakers),
            len(discovered),
            len(work_items),
        )

        for item in work_items:
            scraper = scrapers.get(item.bookmaker)
            if scraper is None:
                continue

            try:
                _upsert_match_record(db, item)
                odds_rows = scraper.scrape_odds_for_raw_match(item.raw_match)
                _persist_odds_snapshots(db, item, odds_rows)
                db.commit()
                logger.info(
                    "[%s] Round-robin saved %s odds for %s vs %s",
                    item.bookmaker,
                    len(odds_rows),
                    item.home_team,
                    item.away_team,
                )
            except Exception:
                db.rollback()
                logger.exception(
                    "[%s] Round-robin failed for %s vs %s",
                    item.bookmaker,
                    item.home_team,
                    item.away_team,
                )

        for bookmaker in due_bookmakers:
            if bookmaker in _LEAGUELESS_BOOKMAKERS:
                continue
            _last_round_robin_run[bookmaker] = now

        for bookmaker in due_bookmakers:
            if bookmaker not in _LEAGUELESS_BOOKMAKERS:
                continue
            scraper = scrapers.get(bookmaker)
            if scraper is None:
                continue
            try:
                scraper.run(league_ids=None, normalizer=normalizer)
                _last_round_robin_run[bookmaker] = now
            except Exception:
                logger.exception(f"[{bookmaker}] Round-robin global scrape failed")

    finally:
        for scraper in scrapers.values():
            try:
                scraper.close()
            except Exception:
                logger.exception("Failed to close scraper cleanly")
        db.close()


def create_scheduler() -> BackgroundScheduler:
    _register_scrapers()
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        run_round_robin_cycle,
        "interval",
        seconds=_round_robin_tick_seconds(),
        id="round_robin_scraper",
        max_instances=1,
        misfire_grace_time=30,
    )

    return scheduler
