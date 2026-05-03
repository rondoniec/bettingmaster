"""Authoritative match-status sync via external football APIs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from bettingmaster.config import settings
from bettingmaster.models.match import Match

logger = logging.getLogger(__name__)


PROVIDER_LEAGUE_CODES = {
    "football_data": {
        "en-premier-league": "PL",
        "es-la-liga": "PD",
    },
    "api_football": {
        "en-premier-league": 39,
        "es-la-liga": 140,
    },
}


@dataclass
class ExternalMatchStatus:
    home_team: str
    away_team: str
    start_time: datetime
    status: str  # internal: prematch / live / concluded / cancelled


class MatchStatusProvider:
    name: str = ""

    def fetch_statuses(self, league_id: str) -> list[ExternalMatchStatus]:
        raise NotImplementedError


class FootballDataProvider(MatchStatusProvider):
    name = "football_data"
    BASE = "https://api.football-data.org/v4"

    _STATUS_MAP = {
        "SCHEDULED": "prematch",
        "TIMED": "prematch",
        "LIVE": "live",
        "IN_PLAY": "live",
        "PAUSED": "live",
        "FINISHED": "concluded",
        "POSTPONED": "prematch",
        "CANCELLED": "cancelled",
        "AWARDED": "concluded",
        "SUSPENDED": "live",
    }

    def __init__(self, token: str):
        self._token = token

    def fetch_statuses(self, league_id: str) -> list[ExternalMatchStatus]:
        code = PROVIDER_LEAGUE_CODES["football_data"].get(league_id)
        if not code:
            return []
        date_from = (datetime.now(UTC) - timedelta(hours=6)).strftime("%Y-%m-%d")
        date_to = (datetime.now(UTC) + timedelta(hours=48)).strftime("%Y-%m-%d")
        url = f"{self.BASE}/competitions/{code}/matches"
        resp = httpx.get(
            url,
            headers={"X-Auth-Token": self._token},
            params={"dateFrom": date_from, "dateTo": date_to},
            timeout=15.0,
        )
        if resp.status_code == 429:
            raise QuotaExhausted(self.name)
        resp.raise_for_status()
        data = resp.json()
        out: list[ExternalMatchStatus] = []
        for m in data.get("matches", []):
            home = (m.get("homeTeam") or {}).get("name") or ""
            away = (m.get("awayTeam") or {}).get("name") or ""
            utc_str = m.get("utcDate")
            if not utc_str:
                continue
            try:
                start = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            status = self._STATUS_MAP.get(m.get("status", ""), "prematch")
            out.append(
                ExternalMatchStatus(
                    home_team=home,
                    away_team=away,
                    start_time=start.astimezone(UTC).replace(tzinfo=None),
                    status=status,
                )
            )
        return out


class ApiFootballProvider(MatchStatusProvider):
    name = "api_football"
    BASE = "https://v3.football.api-sports.io"

    _STATUS_MAP = {
        "TBD": "prematch",
        "NS": "prematch",
        "1H": "live",
        "HT": "live",
        "2H": "live",
        "ET": "live",
        "BT": "live",
        "P": "live",
        "SUSP": "live",
        "INT": "live",
        "LIVE": "live",
        "FT": "concluded",
        "AET": "concluded",
        "PEN": "concluded",
        "PST": "prematch",
        "CANC": "cancelled",
        "ABD": "cancelled",
        "AWD": "concluded",
        "WO": "concluded",
    }

    def __init__(self, token: str):
        self._token = token

    def fetch_statuses(self, league_id: str) -> list[ExternalMatchStatus]:
        code = PROVIDER_LEAGUE_CODES["api_football"].get(league_id)
        if not code:
            return []
        season = datetime.now(UTC).year
        url = f"{self.BASE}/fixtures"
        resp = httpx.get(
            url,
            headers={"x-apisports-key": self._token},
            params={"league": code, "season": season, "next": 50},
            timeout=15.0,
        )
        if resp.status_code == 429:
            raise QuotaExhausted(self.name)
        resp.raise_for_status()
        data = resp.json()
        out: list[ExternalMatchStatus] = []
        for f in data.get("response", []):
            fixture = f.get("fixture", {}) or {}
            teams = f.get("teams", {}) or {}
            home = (teams.get("home") or {}).get("name") or ""
            away = (teams.get("away") or {}).get("name") or ""
            utc_str = fixture.get("date")
            if not utc_str:
                continue
            try:
                start = datetime.fromisoformat(utc_str)
            except ValueError:
                continue
            short = ((fixture.get("status") or {}).get("short") or "").upper()
            status = self._STATUS_MAP.get(short, "prematch")
            out.append(
                ExternalMatchStatus(
                    home_team=home,
                    away_team=away,
                    start_time=start.astimezone(UTC).replace(tzinfo=None),
                    status=status,
                )
            )
        return out


class QuotaExhausted(RuntimeError):
    def __init__(self, provider: str):
        super().__init__(f"{provider} quota exhausted")
        self.provider = provider


def _normalize(name: str) -> str:
    import re
    s = name.lower()
    s = re.sub(r"\b(fc|cf|sc|afc|cd|ud|sd|ac|club|deportivo)\b", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _match_lookup_key(home: str, away: str, start: datetime) -> str:
    return f"{_normalize(home)}|{_normalize(away)}|{start.date().isoformat()}"


def _match_name_key(home: str, away: str) -> str:
    return f"{_normalize(home)}|{_normalize(away)}"


def _heuristic_status(match: Match) -> str | None:
    """Fallback when no external provider returns a status."""
    if not match.start_time:
        return None
    delta = datetime.now(UTC).replace(tzinfo=None) - match.start_time
    if delta > timedelta(hours=4):
        return "concluded"
    if delta >= timedelta(0):
        return "live"
    return None


def sync_match_statuses(db: Session) -> dict[str, int]:
    """Fetch authoritative statuses and update local matches."""
    from bettingmaster.scope import active_league_ids

    providers: list[MatchStatusProvider] = []
    if settings.football_data_token:
        providers.append(FootballDataProvider(settings.football_data_token))
    if settings.api_football_token:
        providers.append(ApiFootballProvider(settings.api_football_token))

    league_ids = list(active_league_ids())

    by_key: dict[str, ExternalMatchStatus] = {}
    by_name: dict[str, ExternalMatchStatus] = {}
    used_provider: str | None = None
    for provider in providers:
        try:
            for league_id in league_ids:
                for ext in provider.fetch_statuses(league_id):
                    by_key[_match_lookup_key(
                        ext.home_team, ext.away_team, ext.start_time
                    )] = ext
                    by_name[_match_name_key(ext.home_team, ext.away_team)] = ext
            used_provider = provider.name
            break
        except QuotaExhausted:
            logger.warning("[status_sync] %s quota exhausted, trying fallback", provider.name)
            continue
        except Exception:
            logger.exception("[status_sync] %s provider failed", provider.name)
            continue

    matches = db.query(Match).all()
    updated = 0
    fallback = 0
    start_time_fixed = 0
    for m in matches:
        if not m.start_time:
            continue
        new_status = None
        key = _match_lookup_key(m.home_team, m.away_team, m.start_time)
        ext = by_key.get(key)
        if ext is None:
            # Date mismatch (e.g. placeholder time from Tipsport) — try name-only
            ext = by_name.get(_match_name_key(m.home_team, m.away_team))
            if ext is not None and ext.start_time != m.start_time:
                m.start_time = ext.start_time
                start_time_fixed += 1
        if ext:
            new_status = ext.status
        else:
            new_status = _heuristic_status(m)
            if new_status:
                fallback += 1
        if new_status and new_status != m.status:
            m.status = new_status
            updated += 1
    if updated or start_time_fixed:
        db.commit()
    logger.info(
        "[status_sync] provider=%s updated=%s heuristic=%s start_time_fixed=%s",
        used_provider or "none",
        updated,
        fallback,
        start_time_fixed,
    )
    return {"updated": updated, "heuristic": fallback}


def _clean_team_name(name: str) -> str:
    """Strip common suffixes so football-data.org names become canonical."""
    import re
    s = name.strip()
    s = re.sub(r"\s+(FC|CF|SC|AFC|CD|UD|SD|AC|Club|Deportivo)\s*$", "", s, flags=re.IGNORECASE)
    return s.strip()


def sync_upcoming_fixtures(db: Session, days_ahead: int = 14) -> dict[str, int]:
    """Fetch upcoming fixtures from football-data.org and create/correct match records.

    Runs once per hour. Creates match rows with authoritative start_times so that
    scrapers without reliable timestamps (e.g. Tipsport) can attach odds to them.
    """
    from bettingmaster.scrapers.base import generate_match_id
    from bettingmaster.scope import active_league_ids

    if not settings.football_data_token:
        return {"created": 0, "corrected": 0}

    provider = FootballDataProvider(settings.football_data_token)
    league_ids = list(active_league_ids())

    created = 0
    corrected = 0

    for league_id in league_ids:
        code = PROVIDER_LEAGUE_CODES["football_data"].get(league_id)
        if not code:
            continue
        date_from = datetime.now(UTC).strftime("%Y-%m-%d")
        date_to = (datetime.now(UTC) + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        url = f"{provider.BASE}/competitions/{code}/matches"
        try:
            resp = httpx.get(
                url,
                headers={"X-Auth-Token": settings.football_data_token},
                params={"dateFrom": date_from, "dateTo": date_to},
                timeout=15.0,
            )
            if resp.status_code == 429:
                logger.warning("[fixture_sync] football_data quota exhausted")
                break
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception("[fixture_sync] failed to fetch %s", league_id)
            continue

        for m in data.get("matches", []):
            home_raw = (m.get("homeTeam") or {}).get("name") or ""
            away_raw = (m.get("awayTeam") or {}).get("name") or ""
            utc_str = m.get("utcDate")
            if not home_raw or not away_raw or not utc_str:
                continue
            try:
                start = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
                start_utc = start.astimezone(UTC).replace(tzinfo=None)
            except ValueError:
                continue

            home = _clean_team_name(home_raw)
            away = _clean_team_name(away_raw)

            # Find existing match by fuzzy name (handles short vs long variants,
            # e.g. "Nottingham" ≈ "Nottingham Forest", ignoring date/time).
            from bettingmaster.match_identity import match_similarity, MATCH_SCORE_THRESHOLD
            existing: Match | None = None
            best_score = 0.0
            for candidate in db.query(Match).filter(Match.league_id == league_id).all():
                score, swapped = match_similarity(
                    home, away, candidate.home_team, candidate.away_team
                )
                if not swapped and score >= MATCH_SCORE_THRESHOLD and score > best_score:
                    best_score = score
                    existing = candidate

            if existing is not None:
                if existing.start_time != start_utc:
                    existing.start_time = start_utc
                    corrected += 1
            else:
                match_id = generate_match_id(league_id, home, away, start_utc.strftime("%Y-%m-%d"))
                if db.get(Match, match_id) is None:
                    db.add(Match(
                        id=match_id,
                        league_id=league_id,
                        home_team=home,
                        away_team=away,
                        start_time=start_utc,
                        status="prematch",
                        external_ids={},
                    ))
                    created += 1

    if created or corrected:
        db.commit()

    logger.info("[fixture_sync] created=%s corrected=%s", created, corrected)
    return {"created": created, "corrected": corrected}
