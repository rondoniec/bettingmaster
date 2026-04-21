"""Utilities for reconciling existing matches after alias improvements."""

from __future__ import annotations

from dataclasses import dataclass

from bettingmaster.match_identity import MATCH_SCORE_THRESHOLD, match_similarity
from bettingmaster.models.match import Match
from bettingmaster.models.odds import OddsSnapshot
from bettingmaster.normalizer import TeamNormalizer
from bettingmaster.scrapers.base import generate_match_id

BOOKMAKER_PRIORITY = ("fortuna", "nike", "doxxbet", "tipsport", "tipos", "polymarket")


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

    _merge_similar_matches(db_session, summary)
    db_session.commit()
    return summary


def _primary_bookmaker(external_ids: dict[str, str]) -> str | None:
    for bookmaker in BOOKMAKER_PRIORITY:
        if bookmaker in external_ids:
            return bookmaker
    return next(iter(external_ids), None)


def _merge_similar_matches(db_session, summary: ReconcileSummary):
    while True:
        match_pair = _find_similar_match_pair(db_session)
        if match_pair is None:
            return

        target, duplicate = match_pair
        _merge_match_rows(db_session, target, duplicate)
        summary.merged += 1
        db_session.flush()


def _find_similar_match_pair(db_session) -> tuple[Match, Match] | None:
    matches = (
        db_session.query(Match)
        .order_by(Match.league_id, Match.start_time, Match.id)
        .all()
    )

    for index, left in enumerate(matches):
        for right in matches[index + 1:]:
            if left.league_id != right.league_id:
                continue
            if abs(left.start_time - right.start_time).total_seconds() > 3 * 60 * 60:
                continue

            score, swapped = match_similarity(
                left.home_team,
                left.away_team,
                right.home_team,
                right.away_team,
            )
            if swapped or score < MATCH_SCORE_THRESHOLD:
                continue
            return _choose_canonical_match(left, right)

    return None


def _choose_canonical_match(left: Match, right: Match) -> tuple[Match, Match]:
    left_rank = _match_rank(left)
    right_rank = _match_rank(right)
    if right_rank < left_rank:
        return right, left
    return left, right


def _match_rank(match: Match) -> tuple[int, int, str]:
    external_ids = match.external_ids or {}
    priorities = [
        BOOKMAKER_PRIORITY.index(bookmaker)
        for bookmaker in external_ids
        if bookmaker in BOOKMAKER_PRIORITY
    ]
    priority = min(priorities) if priorities else len(BOOKMAKER_PRIORITY)
    return (priority, -len(external_ids), match.id)


def _merge_match_rows(db_session, target: Match, duplicate: Match):
    merged_external_ids = dict(target.external_ids or {})
    merged_external_ids.update(duplicate.external_ids or {})
    target.external_ids = merged_external_ids
    if duplicate.status == "live":
        target.status = "live"
    db_session.query(OddsSnapshot).filter_by(match_id=duplicate.id).update(
        {OddsSnapshot.match_id: target.id},
        synchronize_session=False,
    )
    db_session.delete(duplicate)
