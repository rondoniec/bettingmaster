"""Team name normalizer using exact + fuzzy matching."""

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process

from bettingmaster.config import DATA_DIR

logger = logging.getLogger(__name__)


class TeamNormalizer:
    def __init__(self, aliases_path: Path | None = None, db_session=None):
        self._exact_map: dict[tuple[str, str], str] = {}  # (alias_lower, bookmaker) -> canonical
        self._normalized_exact_map: dict[tuple[str, str], str] = {}
        self._all_canonical: list[str] = []
        self._normalized_canonical: dict[str, str] = {}
        self._db = db_session

        alias_paths = [aliases_path] if aliases_path else sorted(DATA_DIR.glob("team_aliases*.json"))
        for path in alias_paths:
            if path.exists():
                self._load_json_aliases(path)
        if db_session:
            self._load_db_aliases()

    def _load_json_aliases(self, path: Path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for canonical, bookmakers in data.items():
            self._register_canonical(canonical)
            for bookmaker, aliases in bookmakers.items():
                for alias in aliases:
                    self._register_alias(alias, bookmaker, canonical)

    def _load_db_aliases(self):
        from bettingmaster.models.team_alias import TeamAlias

        for ta in self._db.query(TeamAlias).all():
            self._register_canonical(ta.canonical_name)
            self._register_alias(ta.alias, ta.bookmaker, ta.canonical_name)

    def _register_canonical(self, canonical: str):
        if canonical not in self._all_canonical:
            self._all_canonical.append(canonical)
        self._normalized_canonical[self._normalized_key(canonical)] = canonical

    def _register_alias(self, alias: str, bookmaker: str, canonical: str):
        raw_key = (alias.lower().strip(), bookmaker)
        normalized_key = (self._normalized_key(alias), bookmaker)
        self._exact_map[raw_key] = canonical
        self._normalized_exact_map[normalized_key] = canonical

    def _normalized_key(self, name: str) -> str:
        normalized = unicodedata.normalize("NFKD", name.casefold())
        asciiish = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        asciiish = asciiish.replace("&", " and ")
        asciiish = re.sub(r"[^\w\s]", " ", asciiish)
        asciiish = re.sub(r"\b(fc|cf|ac|as|fk|mfk|sk|hc|ud)\b", " ", asciiish)
        asciiish = re.sub(r"\butd\b", "united", asciiish)
        asciiish = re.sub(r"\s+", " ", asciiish).strip()
        return asciiish

    def normalize(self, raw_name: str, bookmaker: str) -> Optional[str]:
        """Returns canonical name or None if no match found."""
        key = (raw_name.lower().strip(), bookmaker)
        if key in self._exact_map:
            return self._exact_map[key]

        normalized_key = (self._normalized_key(raw_name), bookmaker)
        if normalized_key in self._normalized_exact_map:
            canonical = self._normalized_exact_map[normalized_key]
            self._exact_map[key] = canonical
            return canonical

        # Fuzzy match against all canonical names
        if not self._normalized_canonical:
            return None

        normalized_raw = self._normalized_key(raw_name)
        result = process.extractOne(
            normalized_raw,
            list(self._normalized_canonical.keys()),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=88,
        )
        if result:
            normalized_canonical, score, _ = result
            canonical = self._normalized_canonical[normalized_canonical]
            logger.info(
                f"Fuzzy matched '{raw_name}' ({bookmaker}) -> '{canonical}' "
                f"(score: {score})"
            )
            # Cache for future exact matches
            self._exact_map[key] = canonical
            self._normalized_exact_map[normalized_key] = canonical
            self._save_new_alias(raw_name, bookmaker, canonical)
            return canonical

        logger.warning(f"Unmatched team: '{raw_name}' from {bookmaker}")
        return None

    def _save_new_alias(self, alias: str, bookmaker: str, canonical: str):
        if not self._db:
            return
        from bettingmaster.models.team_alias import TeamAlias

        existing = (
            self._db.query(TeamAlias)
            .filter_by(alias=alias, bookmaker=bookmaker)
            .first()
        )
        if not existing:
            self._db.add(
                TeamAlias(canonical_name=canonical, alias=alias, bookmaker=bookmaker)
            )
            self._db.commit()
