"""Utilities for reconciling existing matches after alias improvements."""

from __future__ import annotations

from dataclasses import dataclass

from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.normalizer import TeamNormalizer
from bettingmaster.scrapers.base import generate_match_id

BOOKMAKER_PRIORITY = ("fortuna", "nike", "doxxbet", "tipsport", "tipos")


@dataclass
class ReconcileSummary:
    renamed: int = 0
    merged: int = 0
    unchanged: int = 0


def reconcile_matches(db_session) -> ReconcileSummary:
    normalizer = TeamNormalizer(db_session=db_session)
    summary = ReconcileSummary()

    matches = (
        db_session.query(Match)
        .order_by(Match.league_id, Match.start_time, Match.id)
        .all()
    )

    for match in matches:
        ext_ids = dict(match.external_ids or {})
        bookmaker = _primary_bookmaker(ext_ids)
        if not bookmaker:
            summary.unchanged += 1
            continue

        normalized_home = normalizer.normalize(match.home_team, bookmaker) or match.home_team
        normalized_away = normalizer.normalize(match.away_team, bookmaker) or match.away_team
        target_id = generate_match_id(
            match.league_id,
            normalized_home,
            normalized_away,
            match.start_time.strftime("%Y-%m-%d"),
        )

        if target_id == match.id:
            changed = False
            if match.home_team != normalized_home:
                match.home_team = normalized_home
                changed = True
            if match.away_team != normalized_away:
                match.away_team = normalized_away
                changed = True
            summary.renamed += 1 if changed else 0
            summary.unchanged += 0 if changed else 1
            continue

        existing_target = db_session.get(Match, target_id)
        if existing_target is None:
            replacement = Match(
                id=target_id,
                league_id=match.league_id,
                home_team=normalized_home,
                away_team=normalized_away,
                start_time=match.start_time,
                status=match.status,
                external_ids=ext_ids,
            )
            db_session.add(replacement)
            db_session.flush()
            db_session.query(OddsSnapshot).filter_by(match_id=match.id).update(
                {OddsSnapshot.match_id: target_id},
                synchronize_session=False,
            )
            db_session.delete(match)
            summary.renamed += 1
            continue

        merged_external_ids = dict(existing_target.external_ids or {})
        merged_external_ids.update(ext_ids)
        existing_target.external_ids = merged_external_ids
        existing_target.home_team = normalized_home
        existing_target.away_team = normalized_away
        if match.status == "live":
            existing_target.status = "live"
        db_session.query(OddsSnapshot).filter_by(match_id=match.id).update(
            {OddsSnapshot.match_id: target_id},
            synchronize_session=False,
        )
        db_session.delete(match)
        summary.merged += 1

    db_session.commit()
    return summary


def _primary_bookmaker(external_ids: dict[str, str]) -> str | None:
    for bookmaker in BOOKMAKER_PRIORITY:
        if bookmaker in external_ids:
            return bookmaker
    return next(iter(external_ids), None)
