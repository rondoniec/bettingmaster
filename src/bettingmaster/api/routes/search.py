"""Full-text search endpoint for matches and leagues.

SQLite does not support ILIKE natively; SQLAlchemy's .ilike() compiles to
LIKE on SQLite (case-insensitive for ASCII by default) and to ILIKE on
PostgreSQL, so it works correctly on both backends.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from bettingmaster.database import get_db
from bettingmaster.models.league import League
from bettingmaster.models.match import Match
from bettingmaster.scope import apply_active_match_scope
from bettingmaster.schemas.common import MatchSearchResult

router = APIRouter()


@router.get("/search", response_model=list[MatchSearchResult])
def search(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(20, ge=1, le=200, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """Search for upcoming/live matches by team name or league name.

    Searches:
    - home_team ILIKE %q%
    - away_team ILIKE %q%
    - league.name ILIKE %q% (via JOIN)

    Only returns prematch/live matches with start_time > yesterday.
    Results are ordered by start_time ascending.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=422, detail="Query parameter 'q' must not be blank")

    pattern = f"%{q.strip()}%"
    matches = (
        apply_active_match_scope(db.query(Match))
        .join(League, Match.league_id == League.id)
        .filter(
            (
                Match.home_team.ilike(pattern)
                | Match.away_team.ilike(pattern)
                | League.name.ilike(pattern)
            ),
        )
        .order_by(Match.start_time)
        .limit(limit)
        .all()
    )

    return [MatchSearchResult.model_validate(m) for m in matches]
