"""Periodic DB cleanup: prune snapshots and matches we no longer need."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def prune_concluded_snapshots(db: Session, *, hours_after_kickoff: int = 6) -> dict[str, int]:
    """Delete odds snapshots for matches whose kickoff is more than N hours ago.

    Matches considered concluded by either:
      - status in ('concluded', 'finished', 'cancelled')   -- authoritative
      - start_time < now() - hours_after_kickoff           -- safety net for
        matches the status sync didn't reach (e.g. football-data.org gap)

    Match rows themselves stay in place; only the bulky odds_snapshots are
    removed. Run nightly so the DB stays small even when status sync misses
    games.
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=hours_after_kickoff)

    deleted = db.execute(
        text(
            """
            DELETE FROM odds_snapshots
            WHERE match_id IN (
                SELECT id FROM matches
                WHERE status IN ('concluded', 'finished', 'cancelled')
                   OR start_time < :cutoff
            )
            """
        ),
        {"cutoff": cutoff},
    ).rowcount
    db.commit()

    logger.info(
        "[cleanup] pruned %s odds_snapshots (cutoff=%s, status in concluded/finished/cancelled)",
        deleted,
        cutoff.isoformat(),
    )
    return {"deleted_snapshots": deleted}
