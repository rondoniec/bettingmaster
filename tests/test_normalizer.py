from __future__ import annotations

from bettingmaster.normalizer import TeamNormalizer


def test_normalizer_matches_cross_book_aliases_from_json():
    normalizer = TeamNormalizer()

    assert normalizer.normalize("Man.City", "fortuna") == "Manchester City"
    assert normalizer.normalize("Manchester City", "nike") == "Manchester City"
    assert normalizer.normalize("Bayern M\u00fcnchen", "nike") == "Bayern Munich"
    assert normalizer.normalize("Atl.Madrid", "fortuna") == "Atletico Madrid"
    assert normalizer.normalize("Sporting L.", "fortuna") == "Sporting CP"
    assert normalizer.normalize("Atl. Madrid", "doxxbet") == "Atletico Madrid"
    assert normalizer.normalize("PSG", "doxxbet") == "Paris Saint-Germain"
    assert normalizer.normalize("Dun. Streda", "doxxbet") == "DAC Dunajska Streda"


def test_normalizer_uses_normalized_keys_for_small_formatting_differences():
    normalizer = TeamNormalizer()

    assert normalizer.normalize("1 FC K\u00f6ln", "fortuna") == "1. FC Koln"
    assert normalizer.normalize("Alaves", "fortuna") == "Alaves"
