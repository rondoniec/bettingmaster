"""Helpers for keeping bookmaker variants attached to one canonical match."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta

from rapidfuzz import fuzz

from bettingmaster.models.match import Match

MATCH_TIME_WINDOW = timedelta(hours=3)
MATCH_SCORE_THRESHOLD = 86.0


def normalize_team_key(value: str) -> str:
    """Return a comparison-friendly team name."""
    folded = unicodedata.normalize("NFKD", value or "")
    ascii_text = folded.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    lowered = re.sub(r"\b(fc|cf|fk|sk|ac|sc|ss|afc|1909)\b", " ", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def team_similarity(left: str, right: str) -> float:
    left_key = normalize_team_key(left)
    right_key = normalize_team_key(right)
    if not left_key or not right_key:
        return 0.0
    return float(fuzz.WRatio(left_key, right_key))


def match_similarity(
    home: str,
    away: str,
    candidate_home: str,
    candidate_away: str,
) -> tuple[float, bool]:
    """Score whether two home/away pairs describe the same match.

    Returns the best average team-name score and whether the best match is
    swapped relative to the candidate.
    """
    normal = (
        team_similarity(home, candidate_home)
        + team_similarity(away, candidate_away)
    ) / 2
    swapped = (
        team_similarity(home, candidate_away)
        + team_similarity(away, candidate_home)
    ) / 2
    if swapped > normal:
        return swapped, True
    return normal, False


def find_similar_match(
    db_session,
    league_id: str,
    home: str,
    away: str,
    start_time: datetime,
    *,
    min_score: float = MATCH_SCORE_THRESHOLD,
    time_window: timedelta = MATCH_TIME_WINDOW,
) -> Match | None:
    """Find an existing match row that likely represents this bookmaker match."""
    window_start = start_time - time_window
    window_end = start_time + time_window
    candidates = (
        db_session.query(Match)
        .filter(Match.league_id == league_id)
        .filter(Match.start_time >= window_start)
        .filter(Match.start_time <= window_end)
        .all()
    )

    best: tuple[float, Match] | None = None
    for candidate in candidates:
        score, swapped = match_similarity(
            home,
            away,
            candidate.home_team,
            candidate.away_team,
        )
        if swapped:
            continue
        if score < min_score:
            continue
        if best is None or score > best[0]:
            best = (score, candidate)

    return best[1] if best else None
