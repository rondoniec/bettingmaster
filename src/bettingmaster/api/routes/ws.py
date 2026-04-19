import asyncio
from collections.abc import Callable
from datetime import date as calendar_date

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from bettingmaster.config import settings
from bettingmaster.services.odds import live_feed_snapshot, resolve_date_filter

router = APIRouter()


def _session_factory(websocket: WebSocket) -> Callable[[], Session]:
    return websocket.app.state.session_factory


@router.websocket("/ws/odds-feed")
async def odds_feed(
    websocket: WebSocket,
    match_id: str | None = None,
    league_id: str | None = None,
    sport: str | None = None,
    date: str | None = None,
):
    if not any([match_id, league_id, sport, date]):
        await websocket.close(code=1008, reason="Provide at least one subscription filter.")
        return

    try:
        target_date: calendar_date | None = resolve_date_filter(date) if date else None
    except ValueError:
        await websocket.close(code=1008, reason="Invalid date filter.")
        return

    await websocket.accept()

    session_factory = _session_factory(websocket)
    scope = {
        "match_id": match_id,
        "league_id": league_id,
        "sport": sport,
        "date": target_date.isoformat() if target_date else None,
    }
    last_signature: tuple[object, ...] | None = None
    heartbeat_every = 5
    heartbeat_counter = 0

    try:
        while True:
            db = session_factory()
            try:
                snapshot = live_feed_snapshot(
                    db,
                    match_id=match_id,
                    league_id=league_id,
                    sport=sport,
                    target_date=target_date,
                )
            finally:
                db.close()

            signature = (
                snapshot["latest_scraped_at"],
                snapshot["match_count"],
                snapshot["bookmaker_count"],
                snapshot["snapshot_count"],
            )
            message_type = "snapshot" if last_signature is None else "odds_update"
            if signature != last_signature:
                await websocket.send_json({"type": message_type, "scope": scope, **snapshot})
                last_signature = signature
                heartbeat_counter = 0
            else:
                heartbeat_counter += 1
                if heartbeat_counter >= heartbeat_every:
                    await websocket.send_json({"type": "heartbeat", "scope": scope, **snapshot})
                    heartbeat_counter = 0

            await asyncio.sleep(settings.live_feed_poll_seconds)
    except (WebSocketDisconnect, RuntimeError):
        return
