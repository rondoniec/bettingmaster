"""Polymarket discovery endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from bettingmaster.config import settings

router = APIRouter()

GAMMA_API = "https://gamma-api.polymarket.com"


class NewPolymarketSubMarketOut(BaseModel):
    name: str
    slug: str
    url: str
    market_count: int


class NewPolymarketMarketOut(BaseModel):
    title: str
    slug: str
    url: str
    start_time: datetime | None = None
    created_at: datetime | None = None
    market_count: int
    league_hint: str | None = None
    markets: list[NewPolymarketSubMarketOut] = []


_CACHE: dict[str, tuple[float, list["NewPolymarketMarketOut"]]] = {}
_CACHE_TTL_SECONDS = 600  # 10 min


@router.get("/polymarket/new-football-markets", response_model=list[NewPolymarketMarketOut])
def list_new_football_markets(
    days: int = Query(14, ge=1, le=60, description="How many recently created days to show"),
    limit: int = Query(60, ge=1, le=200, description="Maximum number of markets"),
):
    import time as _time

    cache_key = f"{days}:{limit}"
    now_mono = _time.monotonic()
    cached = _CACHE.get(cache_key)
    if cached and cached[0] > now_mono:
        return cached[1]

    events = _fetch_soccer_events()
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

    results = [
        NewPolymarketMarketOut(
            title=g["title"],
            slug=g["slug"],
            url=g["url"],
            start_time=g["start_time"],
            created_at=g["created_at"],
            market_count=sum(m.market_count or 1 for m in g["markets"]),
            league_hint=g["league_hint"],
            markets=g["markets"],
        )
        for g in groups.values()
    ]

    sorted_results = sorted(
        results,
        key=lambda item: (
            item.created_at or datetime.min,
            item.start_time or datetime.max,
        ),
        reverse=True,
    )[:limit]
    _CACHE[cache_key] = (now_mono + _CACHE_TTL_SECONDS, sorted_results)
    return sorted_results


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
):
    """Surface Polymarket politics/world/election markets, grouped per event."""
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
        start_time = _parse_dt(event.get("startDate") or event.get("endDate"))
        created_at = _parse_dt(event.get("createdAt") or event.get("created_at"))
        if start_time and start_time < now - timedelta(hours=2):
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
