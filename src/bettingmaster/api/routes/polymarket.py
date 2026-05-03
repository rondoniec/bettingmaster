"""Polymarket discovery endpoints."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bettingmaster.config import settings
from bettingmaster.database import get_db
from bettingmaster.match_identity import find_similar_match
from bettingmaster.models.match import Match
from bettingmaster.services.odds import latest_odds_for_match

router = APIRouter()

GAMMA_API = "https://gamma-api.polymarket.com"


class NewPolymarketSubMarketOut(BaseModel):
    name: str
    slug: str
    url: str
    market_count: int


class CrossRefSelectionOut(BaseModel):
    selection: str
    polymarket_odds: float | None = None
    sportsbook_odds: float | None = None
    sportsbook_name: str | None = None
    edge_percent: float | None = None  # +ve = polymarket pays better than the best sportsbook


class CrossRefOut(BaseModel):
    match_id: str
    match_home: str
    match_away: str
    match_start_time: datetime | None = None
    selections: list[CrossRefSelectionOut] = []
    polymarket_better_count: int = 0  # how many outcomes polymarket beats sportsbooks on


class NewPolymarketMarketOut(BaseModel):
    title: str
    slug: str
    url: str
    start_time: datetime | None = None
    created_at: datetime | None = None
    market_count: int
    league_hint: str | None = None
    markets: list[NewPolymarketSubMarketOut] = []
    crossref: CrossRefOut | None = None


_LEAGUE_HINT_TO_DB_ID: dict[str, str] = {
    "Premier League": "en-premier-league",
    "La Liga": "es-la-liga",
}


_CACHE: dict[str, tuple[float, list["NewPolymarketMarketOut"]]] = {}
_CACHE_TTL_SECONDS = 600  # 10 min


@router.get("/polymarket/new-football-markets", response_model=list[NewPolymarketMarketOut])
def list_new_football_markets(
    days: int = Query(1, ge=1, le=60, description="How many recently created days to show"),
    limit: int = Query(60, ge=1, le=200, description="Maximum number of markets"),
    only_with_sportsbook: bool = Query(
        True,
        description="Only return events that match a Slovak sportsbook match in our DB",
    ),
    db: Session = Depends(get_db),
):
    import time as _time

    # Cross-ref data depends on DB state; bypass cache when joining sportsbook.
    cache_key = f"{days}:{limit}:{int(only_with_sportsbook)}"
    now_mono = _time.monotonic()
    if not only_with_sportsbook:
        cached = _CACHE.get(cache_key)
        if cached and cached[0] > now_mono:
            return cached[1]

    # Pull both the broad soccer firehose AND targeted league tags so we
    # don't lose PL/LaLiga events behind the MLS/Segunda flood at the top
    # of /events/pagination?tag_slug=soccer.
    events: list[dict] = []
    seen_slugs: set[str] = set()
    for fetcher_args in [
        {"tag_slug": "soccer", "pages": 3},
        {"tag_slug": "epl", "pages": 2},
        {"tag_slug": "premier-league", "pages": 2},
        {"tag_slug": "la-liga", "pages": 2},
    ]:
        for ev in _fetch_events_for_tag(fetcher_args["tag_slug"], pages=fetcher_args["pages"]):
            slug = str(ev.get("slug") or "")
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            events.append(ev)
    now = datetime.now(UTC).replace(tzinfo=None)
    created_after = now - timedelta(days=days)

    # Bucket sub-events by their underlying matchup so 10 markets for the
    # same Nashville vs DC game collapse into a single card with a dropdown.
    groups: dict[str, dict] = {}
    for event in events:
        title = str(event.get("title") or event.get("question") or "").strip()
        slug = str(event.get("slug") or "").strip()
        if not title or not slug:
            continue

        start_time = _parse_dt(event.get("startDate") or event.get("endDate"))
        created_at = _parse_dt(event.get("createdAt") or event.get("created_at"))
        # Skip already-finished events but allow anything starting in the future
        # (don't apply the same 48h "near-term" cutoff as the main board — these
        # are explicitly intended to surface newly opened far + near markets).
        if start_time and start_time < now - timedelta(hours=2):
            continue
        if created_at and created_at < created_after:
            continue

        league_hint = _league_hint(f"{title} {slug}")
        if league_hint is None:
            continue

        matchup_title, sub_market_name = _split_event_title(title)
        bucket_key = (matchup_title, _matchup_slug_root(slug))

        bucket = groups.get(bucket_key)
        sub = NewPolymarketSubMarketOut(
            name=sub_market_name or "Hlavný trh",
            slug=slug,
            url=f"https://polymarket.com/event/{slug}",
            market_count=len(event.get("markets", []) or []),
        )

        if bucket is None:
            groups[bucket_key] = {
                "title": matchup_title,
                "slug": slug,
                "url": f"https://polymarket.com/event/{slug}",
                "start_time": start_time,
                "created_at": created_at,
                "league_hint": league_hint,
                "markets": [sub],
            }
        else:
            bucket["markets"].append(sub)
            # Keep the freshest created_at and earliest start_time
            if created_at and (bucket["created_at"] is None or created_at > bucket["created_at"]):
                bucket["created_at"] = created_at
            if start_time and (bucket["start_time"] is None or start_time < bucket["start_time"]):
                bucket["start_time"] = start_time

    results: list[NewPolymarketMarketOut] = []
    for g in groups.values():
        crossref = _build_crossref(db, g["title"], g["league_hint"], g["start_time"])
        if only_with_sportsbook and crossref is None:
            continue
        results.append(
            NewPolymarketMarketOut(
                title=g["title"],
                slug=g["slug"],
                url=g["url"],
                start_time=g["start_time"],
                created_at=g["created_at"],
                market_count=sum(m.market_count or 1 for m in g["markets"]),
                league_hint=g["league_hint"],
                markets=g["markets"],
                crossref=crossref,
            )
        )

    sorted_results = sorted(
        results,
        key=lambda item: (
            item.crossref.polymarket_better_count if item.crossref else 0,
            item.created_at or datetime.min,
            item.start_time or datetime.max,
        ),
        reverse=True,
    )[:limit]
    if not only_with_sportsbook:
        _CACHE[cache_key] = (now_mono + _CACHE_TTL_SECONDS, sorted_results)
    return sorted_results


_VS_SPLIT = re.compile(r"\s+vs\.?\s+|\s+v\s+", re.IGNORECASE)


def _split_teams(matchup_title: str) -> tuple[str, str] | None:
    parts = _VS_SPLIT.split(matchup_title, maxsplit=1)
    if len(parts) != 2:
        return None
    home = parts[0].strip().rstrip(".")
    away = parts[1].strip().rstrip(".")
    if not home or not away:
        return None
    return home, away


def _build_crossref(
    db: Session,
    matchup_title: str,
    league_hint: str | None,
    start_time: datetime | None,
) -> CrossRefOut | None:
    """Look up our DB match and compute Polymarket-vs-sportsbook edge per outcome."""
    if not start_time or not league_hint:
        return None
    league_id = _LEAGUE_HINT_TO_DB_ID.get(league_hint)
    if not league_id:
        return None
    teams = _split_teams(matchup_title)
    if not teams:
        return None
    home, away = teams
    naive_start = (
        start_time.astimezone(UTC).replace(tzinfo=None) if start_time.tzinfo else start_time
    )
    match: Optional[Match] = find_similar_match(db, league_id, home, away, naive_start)
    if match is None:
        return None

    odds_rows = latest_odds_for_match(db, match.id, market="1x2")
    by_selection_book: dict[tuple[str, str], float] = {}
    for row in odds_rows:
        by_selection_book[(row.selection, row.bookmaker)] = float(row.odds)

    selections_out: list[CrossRefSelectionOut] = []
    polymarket_better = 0
    for sel in ("home", "draw", "away"):
        poly = by_selection_book.get((sel, "polymarket"))
        sportsbook_pairs = [
            (book, odds)
            for (s, book), odds in by_selection_book.items()
            if s == sel and book != "polymarket"
        ]
        sportsbook_pairs.sort(key=lambda p: p[1], reverse=True)
        best_book, best_odds = (sportsbook_pairs[0] if sportsbook_pairs else (None, None))
        edge = None
        if poly is not None and best_odds:
            # Edge = how much more (in %) polymarket pays vs the best sportsbook.
            edge = round((poly / best_odds - 1) * 100, 2)
            if edge > 0:
                polymarket_better += 1
        selections_out.append(
            CrossRefSelectionOut(
                selection=sel,
                polymarket_odds=poly,
                sportsbook_odds=best_odds,
                sportsbook_name=best_book,
                edge_percent=edge,
            )
        )

    return CrossRefOut(
        match_id=match.id,
        match_home=match.home_team,
        match_away=match.away_team,
        match_start_time=match.start_time,
        selections=selections_out,
        polymarket_better_count=polymarket_better,
    )


def _split_event_title(title: str) -> tuple[str, str]:
    """Pull the matchup prefix off a Polymarket event title.

    'Nashville SC vs. D.C. United SC - Halftime Result'
       → ('Nashville SC vs. D.C. United SC', 'Halftime Result')
    'Real Madrid vs Barcelona'
       → ('Real Madrid vs Barcelona', '')
    """
    for sep in (" - ", " — ", ": "):
        if sep in title:
            head, _, tail = title.partition(sep)
            return head.strip(), tail.strip()
    return title.strip(), ""


@router.get("/polymarket/non-sports", response_model=list[NewPolymarketMarketOut])
def list_non_sports_markets(
    days: int = Query(30, ge=1, le=180, description="How many recently created days to show"),
    limit: int = Query(80, ge=1, le=200, description="Maximum number of events"),
    require_sportsbook: bool = Query(
        True,
        description="Only return events also bettable on a Slovak sportsbook (currently none — empties the page)",
    ),
):
    """Surface Polymarket politics/world/election markets, grouped per event.

    By default returns [] because we don't yet scrape Niké/Fortuna for
    non-sports markets. Pass require_sportsbook=false to see all
    Polymarket-only events.
    """
    if require_sportsbook:
        # No Slovak non-sports scraper yet — there's nothing to cross-ref against.
        return []
    import time as _time

    cache_key = f"nonsports:{days}:{limit}"
    now_mono = _time.monotonic()
    cached = _CACHE.get(cache_key)
    if cached and cached[0] > now_mono:
        return cached[1]

    tag_buckets = [
        ("politics", "Politika"),
        ("elections", "Voľby"),
        ("geopolitics", "Geopolitika"),
        ("world", "Svet"),
        ("trump", "USA"),
        ("middle-east", "Stredný východ"),
        ("crypto", "Krypto"),
    ]

    seen_slugs: set[str] = set()
    events: list[tuple[dict, str]] = []
    for tag, label in tag_buckets:
        for ev in _fetch_events_for_tag(tag, pages=2):
            slug = str(ev.get("slug") or "").strip()
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            events.append((ev, label))

    now = datetime.now(UTC).replace(tzinfo=None)
    # Politics + geopolitical events live for months — don't apply the
    # newly-opened filter here, just ensure the event hasn't already ended.

    # Cap per-bucket to keep variety (e.g. crypto floods otherwise).
    per_bucket_cap = max(8, limit // max(1, len({lbl for _, lbl in events})))
    counts: dict[str, int] = {}

    out: list[NewPolymarketMarketOut] = []
    for event, label in events:
        title = str(event.get("title") or event.get("question") or "").strip()
        slug = str(event.get("slug") or "").strip()
        if not title:
            continue
        # For prediction markets the meaningful timestamp is `endDate`
        # (resolution); `startDate` is when Polymarket listed the question
        # and is usually in the past for politics. Display endDate.
        start_time = _parse_dt(event.get("endDate") or event.get("startDate"))
        created_at = _parse_dt(event.get("createdAt") or event.get("created_at"))
        end_time = _parse_dt(event.get("endDate"))
        if end_time and end_time < now - timedelta(hours=2):
            continue
        if counts.get(label, 0) >= per_bucket_cap:
            continue
        counts[label] = counts.get(label, 0) + 1
        out.append(
            NewPolymarketMarketOut(
                title=title,
                slug=slug,
                url=f"https://polymarket.com/event/{slug}",
                start_time=start_time,
                created_at=created_at,
                market_count=len(event.get("markets", []) or []),
                league_hint=label,
                markets=[],  # non-sports events: each is its own card already
            )
        )

    sorted_out = sorted(
        out,
        key=lambda item: (
            item.created_at or datetime.min,
            item.start_time or datetime.max,
        ),
        reverse=True,
    )[:limit]
    _CACHE[cache_key] = (now_mono + _CACHE_TTL_SECONDS, sorted_out)
    return sorted_out


def _fetch_events_for_tag(tag: str, *, pages: int = 2) -> list[dict]:
    out: list[dict] = []
    offset = 0
    page_size = 100
    with httpx.Client(timeout=8.0, follow_redirects=True) as client:
        for _ in range(pages):
            try:
                r = client.get(
                    f"{GAMMA_API}/events/pagination",
                    params={
                        "tag_slug": tag,
                        "active": "true",
                        "closed": "false",
                        "limit": page_size,
                        "order": "createdAt",
                        "ascending": "false",
                        "offset": offset,
                    },
                )
                r.raise_for_status()
            except httpx.HTTPError:
                break
            batch = r.json().get("data", []) if isinstance(r.json(), dict) else []
            if not batch:
                break
            out.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
    return out


def _matchup_slug_root(slug: str) -> str:
    """Take the part of the slug before the market-type suffix.

    Polymarket slugs commonly look like:
        'mls-nas-dc-2026-05-04-halftime-result'
        'mls-nas-dc-2026-05-04-exact-score'
    Trimming trailing '-<word>...' chunks tends to align them.
    """
    parts = slug.split("-")
    # Date stamps come in the middle (YYYY-MM-DD); keep up to and including
    # the date so per-match suffixes (halftime / exact-score / total-goals)
    # are dropped while the matchup identity stays.
    for i in range(len(parts) - 2, -1, -1):
        if (
            len(parts[i]) == 4
            and parts[i].isdigit()
            and i + 2 < len(parts)
            and len(parts[i + 1]) == 2
            and len(parts[i + 2]) == 2
        ):
            return "-".join(parts[: i + 3])
    return slug


def _fetch_soccer_events() -> list[dict]:
    events: list[dict] = []
    offset = 0
    page_size = 100
    # Cap at 3 pages (300 events) — we order by createdAt desc, so the freshest
    # ones are first. Going deeper just adds latency without surfacing newer
    # markets.
    with httpx.Client(timeout=8.0, follow_redirects=True) as client:
        for _ in range(3):
            try:
                response = client.get(
                    f"{GAMMA_API}/events/pagination",
                    params={
                        "tag_slug": "soccer",
                        "active": "true",
                        "closed": "false",
                        "limit": page_size,
                        "order": "createdAt",
                        "ascending": "false",
                        "offset": offset,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError:
                break
            payload = response.json()
            batch = payload.get("data", []) if isinstance(payload, dict) else []
            if not batch:
                break
            events.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
    return events


_LEAGUE_PATTERNS = [
    ("Premier League", ("premier-league", "premier league", "epl-")),
    ("La Liga",        ("la-liga", "la liga", "laliga", "lal-")),
    ("Champions League", ("champions-league", "champions league", "ucl-", "uefa-champions")),
    ("Bundesliga",     ("bundesliga", "bun-")),
    ("Serie A",        ("serie-a", "serie a", "ser-")),
    ("Ligue 1",        ("ligue-1", "ligue 1", "lig-")),
    ("Europa League",  ("europa-league", "europa league", "uel-")),
    ("MLS",            ("mls", "major-league-soccer")),
    ("Liga MX",        ("liga-mx", "liga mx")),
    ("World Cup",      ("world-cup", "world cup", "fifa-world-cup")),
    ("Euro",           ("euro-202", "euros-202", "uefa-euro")),
    ("Copa America",   ("copa-america", "copa america")),
]


def _league_hint(value: str) -> str | None:
    normalized = value.lower()
    for label, patterns in _LEAGUE_PATTERNS:
        if any(p in normalized for p in patterns):
            return label
    return None


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    raw = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    except ValueError:
        return None
