"""Polymarket discovery endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from bettingmaster.config import settings

router = APIRouter()

GAMMA_API = "https://gamma-api.polymarket.com"


class NewPolymarketMarketOut(BaseModel):
    title: str
    slug: str
    url: str
    start_time: datetime | None = None
    created_at: datetime | None = None
    market_count: int
    league_hint: str | None = None


@router.get("/polymarket/new-football-markets", response_model=list[NewPolymarketMarketOut])
def list_new_football_markets(
    days: int = Query(14, ge=1, le=60, description="How many recently created days to show"),
    limit: int = Query(60, ge=1, le=200, description="Maximum number of markets"),
):
    events = _fetch_soccer_events()
    now = datetime.now(UTC).replace(tzinfo=None)
    starts_after = now + timedelta(hours=settings.active_match_window_hours)
    created_after = now - timedelta(days=days)

    results: list[NewPolymarketMarketOut] = []
    for event in events:
        title = str(event.get("title") or event.get("question") or "").strip()
        slug = str(event.get("slug") or "").strip()
        if not title or not slug:
            continue

        start_time = _parse_dt(event.get("startDate") or event.get("endDate"))
        created_at = _parse_dt(event.get("createdAt") or event.get("created_at"))
        if start_time and start_time <= starts_after:
            continue
        if created_at and created_at < created_after:
            continue

        league_hint = _league_hint(f"{title} {slug}")
        if league_hint is None:
            continue

        results.append(
            NewPolymarketMarketOut(
                title=title,
                slug=slug,
                url=f"https://polymarket.com/event/{slug}",
                start_time=start_time,
                created_at=created_at,
                market_count=len(event.get("markets", []) or []),
                league_hint=league_hint,
            )
        )

    return sorted(
        results,
        key=lambda item: (
            item.created_at or datetime.min,
            item.start_time or datetime.max,
        ),
        reverse=True,
    )[:limit]


def _fetch_soccer_events() -> list[dict]:
    events: list[dict] = []
    offset = 0
    limit = 100
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for _ in range(10):
            response = client.get(
                f"{GAMMA_API}/events/pagination",
                params={
                    "tag_slug": "soccer",
                    "active": "true",
                    "closed": "false",
                    "limit": limit,
                    "order": "createdAt",
                    "ascending": "false",
                    "offset": offset,
                },
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("data", []) if isinstance(payload, dict) else []
            if not batch:
                break
            events.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
    return events


def _league_hint(value: str) -> str | None:
    normalized = value.lower()
    if "premier-league" in normalized or "premier league" in normalized:
        return "Premier League"
    if "la-liga" in normalized or "la liga" in normalized:
        return "La Liga"
    if "champions-league" in normalized or "champions league" in normalized:
        return "Champions League"
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
