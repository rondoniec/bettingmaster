"""Validation helpers for bookmaker URLs and rows."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot

_PROTECTED_EXTRA_TOKENS = {"sc", "sporting"}


def is_valid_bookmaker_odds(match: Match, odds_row: OddsSnapshot) -> bool:
    if odds_row.bookmaker != "polymarket":
        return True
    return is_valid_polymarket_url(match, odds_row.url)


def is_valid_polymarket_url(match: Match, url: str | None) -> bool:
    slug = _polymarket_slug(url)
    if not slug:
        return True

    protected_phrases = _protected_team_phrases(slug)
    if not protected_phrases:
        return True

    match_teams = {
        _normalize_team(match.home_team),
        _normalize_team(match.away_team),
    }
    for phrase in protected_phrases:
        base = " ".join(token for token in phrase.split() if token not in _PROTECTED_EXTRA_TOKENS)
        if base in match_teams and phrase not in match_teams:
            return False
    return True


def _polymarket_slug(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if "polymarket.com" not in parsed.netloc:
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "event":
        return parts[1].lower()
    return ""


def _protected_team_phrases(slug: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", slug.lower())
    tokens = normalized.split()
    phrases: set[str] = set()
    for index, token in enumerate(tokens[:-1]):
        next_token = tokens[index + 1]
        if next_token in _PROTECTED_EXTRA_TOKENS:
            phrases.add(f"{token} {next_token}")
    return phrases


def _normalize_team(value: str) -> str:
    normalized = value.lower()
    normalized = re.sub(r"\b(fc|cf|afc)\b", " ", normalized)
    normalized = re.sub(r"\b(18|19|20)\d{2}\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())
