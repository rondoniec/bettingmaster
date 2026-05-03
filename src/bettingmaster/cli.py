"""CLI for BettingMaster."""

import json
import logging
import signal
import threading

import click

from bettingmaster.config import DATA_DIR, settings


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging + API response dumps")
def main(debug: bool):
    """BettingMaster CLI."""
    level = logging.DEBUG if debug else getattr(logging, settings.log_level.upper())
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    if debug:
        settings.debug_dump = True


@main.group()
def db():
    """Database commands."""
    pass


@db.command()
def init():
    """Initialize the database schema using Alembic migrations."""
    from bettingmaster.migrations import upgrade_database

    upgrade_database()
    click.echo("Database initialized at head revision.")


@db.command()
def upgrade():
    """Upgrade the database schema to the latest Alembic revision."""
    from bettingmaster.migrations import upgrade_database

    upgrade_database()
    click.echo("Database upgraded to head revision.")


@db.command()
def current():
    """Show the current Alembic revision."""
    from bettingmaster.migrations import current_revision

    current_revision(verbose=True)


@db.command()
def seed():
    """Seed the database with sports, leagues, and team aliases."""
    from bettingmaster.database import SessionLocal, init_db
    from bettingmaster.models.sport import Sport
    from bettingmaster.models.league import League
    from bettingmaster.models.team_alias import TeamAlias

    init_db()
    db_session = SessionLocal()

    # Seed sports
    sports = [
        ("football", "Futbal"),
        ("hockey", "Hokej"),
        ("tennis", "Tenis"),
        ("basketball", "Basketbal"),
    ]
    for sid, name in sports:
        if not db_session.get(Sport, sid):
            db_session.add(Sport(id=sid, name=name))

    # Seed leagues with bookmaker external IDs
    leagues = [
        ("sk-fortuna-liga", "football", "Niké Liga", "SK",
         {"nike": "30", "fortuna": "ufo:tour:00-062", "doxxbet": "919",
          "tipsport": "33", "tipos": "150", "polymarket": "fortuna liga"}),
        ("en-premier-league", "football", "Premier League", "EN",
         {"nike": "1", "fortuna": "ufo:tour:00-03m", "doxxbet": "653",
          "tipsport": "118", "tipos": "318", "polymarket": "premier league"}),
        ("de-bundesliga", "football", "Bundesliga", "DE",
         {"nike": "12", "fortuna": "ufo:tour:00-0c6",
          "tipsport": "10", "tipos": "149", "polymarket": "bundesliga"}),
        ("es-la-liga", "football", "La Liga", "ES",
         {"nike": "24", "fortuna": "ufo:tour:00-0h7", "doxxbet": "928",
          "tipsport": "140", "tipos": "158", "polymarket": "la liga"}),
        ("it-serie-a", "football", "Serie A", "IT",
         {"nike": "26", "fortuna": "ufo:tour:00-06t",
          "tipsport": "25", "tipos": "160", "polymarket": "serie a"}),
        ("sk-tipos-extraliga", "hockey", "Tipos Extraliga", "SK",
         {"nike": "285", "tipos": "410"}),
        ("ucl", "football", "UEFA Champions League", "EU",
         {"nike": "953", "fortuna": "ufo:tour:00-0fy", "doxxbet": "607245",
          "tipsport": "329", "tipos": "200", "polymarket": "champions league"}),
    ]
    for lid, sport_id, name, country, ext_ids in leagues:
        existing_league = db_session.get(League, lid)
        if not existing_league:
            db_session.add(
                League(
                    id=lid,
                    sport_id=sport_id,
                    name=name,
                    country=country,
                    external_ids=ext_ids,
                )
            )
        else:
            merged_external_ids = dict(existing_league.external_ids or {})
            merged_external_ids.update(ext_ids)
            existing_league.sport_id = sport_id
            existing_league.name = name
            existing_league.country = country
            existing_league.external_ids = merged_external_ids

    # Seed team aliases from JSON
    alias_files = sorted(DATA_DIR.glob("team_aliases*.json"))
    count = 0
    for aliases_path in alias_files:
        with open(aliases_path, "r", encoding="utf-8") as f:
            aliases_data = json.load(f)

        for canonical, bookmakers in aliases_data.items():
            for bookmaker, alias_list in bookmakers.items():
                for alias in alias_list:
                    existing = (
                        db_session.query(TeamAlias)
                        .filter_by(alias=alias, bookmaker=bookmaker)
                        .first()
                    )
                    if not existing:
                        db_session.add(
                            TeamAlias(
                                canonical_name=canonical,
                                alias=alias,
                                bookmaker=bookmaker,
                            )
                        )
                        count += 1

    click.echo(f"Seeded {count} team aliases.")

    db_session.commit()
    db_session.close()
    click.echo("Database seeded.")


@db.command("reconcile-matches")
def reconcile_matches_command():
    """Reconcile stored matches using the latest team alias mapping."""
    from bettingmaster.database import SessionLocal
    from bettingmaster.reconciliation import reconcile_matches

    db_session = SessionLocal()
    try:
        summary = reconcile_matches(db_session)
    finally:
        db_session.close()

    click.echo(
        "Reconciled matches: "
        f"renamed={summary.renamed}, merged={summary.merged}, unchanged={summary.unchanged}"
    )


@main.command()
@click.argument("bookmaker")
@click.option("--discover", is_flag=True, help="Run in discovery mode (dump raw API responses)")
def scrape(bookmaker: str, discover: bool):
    """Run a scraper manually."""
    if discover:
        settings.debug_dump = True

    if discover and bookmaker == "tipsport":
        _discover_tipsport()
        return

    if discover and bookmaker == "tipos":
        _discover_tipos()
        return

    if discover and bookmaker == "polymarket":
        _discover_polymarket()
        return

    from bettingmaster.scheduler import run_scraper

    click.echo(f"Running {bookmaker} scraper...")
    run_scraper(bookmaker)
    click.echo("Done.")


@main.command("scrape-cycle")
@click.option(
    "--bookmaker",
    "bookmakers",
    multiple=True,
    help="Limit the round-robin cycle to one bookmaker. Can be used more than once.",
)
def scrape_cycle(bookmakers: tuple[str, ...]):
    """Run one match-first scrape cycle manually."""
    from bettingmaster.scheduler import run_round_robin_cycle

    selected = list(bookmakers) or None
    click.echo("Running match-first scrape cycle...")
    run_round_robin_cycle(force_bookmakers=selected)
    click.echo("Done.")


def _discover_tipsport():
    """Run Tipsport scraper in discovery mode — dumps raw API responses."""
    from bettingmaster.database import SessionLocal
    from bettingmaster.scrapers.tipsport import TipsportScraper

    db_session = SessionLocal()
    scraper = TipsportScraper(db_session=db_session)

    click.echo("Fetching sports tree...")
    try:
        sports = scraper.discover_sports()
        click.echo(f"  Got {len(sports) if isinstance(sports, list) else 'dict'} response")
        click.echo(f"  Keys: {list(sports.keys()) if isinstance(sports, dict) else 'list'}")
    except Exception as e:
        click.echo(f"  Failed: {e}")

    click.echo("\nFetching top competitions...")
    try:
        comps = scraper.discover_top_competitions()
        click.echo(f"  Got {len(comps) if isinstance(comps, list) else 'dict'} response")
    except Exception as e:
        click.echo(f"  Failed: {e}")

    click.echo("\nSearching for 'futbal'...")
    try:
        results = scraper.search("futbal")
        click.echo(f"  Got {len(results) if isinstance(results, list) else 'dict'} response")
    except Exception as e:
        click.echo(f"  Failed: {e}")

    click.echo(f"\nDebug dumps saved to: {DATA_DIR / 'debug'}")
    scraper.close()
    db_session.close()


def _discover_tipos():
    """Run Tipos scraper in discovery mode — dumps raw API responses."""
    from bettingmaster.database import SessionLocal
    from bettingmaster.scrapers.tipos import TiposScraper

    db_session = SessionLocal()
    scraper = TiposScraper(db_session=db_session)

    click.echo("Fetching categories (sports/leagues)...")
    try:
        cats = scraper.discover_categories()
        parsed = scraper._decode_return_value(cats)
        strings = [s for _, s in parsed["strings"] if len(s) >= 3]
        click.echo(f"  Strings: {strings[:30]}")
    except Exception as e:
        click.echo(f"  Failed: {e}")

    click.echo("\nFetching top bets...")
    try:
        top = scraper.discover_top_bets()
        parsed = scraper._decode_return_value(top)
        click.echo(f"  Floats (odds): {[v for _, v in parsed['floats']][:20]}")
    except Exception as e:
        click.echo(f"  Failed: {e}")

    click.echo("\nFetching sample event (2489894)...")
    try:
        ev = scraper.discover_event(2489894)
        parsed = scraper._decode_return_value(ev)
        strings = [s for _, s in parsed["strings"] if len(s) >= 3]
        floats = [v for _, v in parsed["floats"] if 1.01 <= v <= 50]
        click.echo(f"  Strings: {strings[:20]}")
        click.echo(f"  Odds-range floats: {floats[:15]}")
    except Exception as e:
        click.echo(f"  Failed: {e}")

    click.echo(f"\nDebug dumps saved to: {DATA_DIR / 'debug'}")
    scraper.close()
    db_session.close()


def _discover_polymarket():
    """Run Polymarket scraper in discovery mode — show live markets and parsed odds."""
    from bettingmaster.database import SessionLocal
    from bettingmaster.scrapers.polymarket import PolymarketScraper

    db_session = SessionLocal()
    scraper = PolymarketScraper(db_session=db_session)

    for query in ["premier league", "champions league", "bundesliga"]:
        click.echo(f"\nSearching Polymarket for: '{query}'...")
        try:
            events = scraper.discover_soccer_events(q=query)
            click.echo(f"  Found {len(events)} events")
            for event in events[:3]:
                title = event.get("title", "?")
                eid = event.get("id", "?")
                click.echo(f"    [{eid}] {title}")
                # Parse odds
                odds = scraper._extract_1x2_from_event(event, str(eid))
                if odds:
                    for o in odds:
                        click.echo(f"      {o.selection}: {o.odds:.3f}")
                else:
                    click.echo("      (no 1x2 odds parsed)")
        except Exception as e:
            click.echo(f"  Failed: {e}")

    scraper.close()
    db_session.close()


@main.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8000, type=int)
def serve(host: str, port: int):
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run(
        "bettingmaster.api.app:app",
        host=host,
        port=port,
        reload=True,
    )


@main.command()
def worker():
    """Run the scraper scheduler as a dedicated long-lived worker."""
    from bettingmaster.scheduler import create_scheduler

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    scheduler = create_scheduler()
    stop_event = threading.Event()
    logger = logging.getLogger(__name__)

    def _shutdown(signum, frame):
        logger.info("Stopping scraper worker")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _shutdown)

    try:
        scheduler.start()
        logger.info("Scraper worker started")
        stop_event.wait()
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
