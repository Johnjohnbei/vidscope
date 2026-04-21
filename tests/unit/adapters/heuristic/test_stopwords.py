"""Tests for stopword set coverage (R063).

R063 requires FRENCH_STOPWORDS and ENGLISH_STOPWORDS to each contain at
least 100 entries. This module also pins the canonical French contractions
and conjugated verbs added in M012/S02 so accidental removals are caught.
"""

from __future__ import annotations

from vidscope.adapters.heuristic.stopwords import (
    ALL_STOPWORDS,
    ENGLISH_STOPWORDS,
    FRENCH_STOPWORDS,
)


class TestStopwordSetSizes:
    def test_french_stopwords_meet_minimum_size(self) -> None:
        """R063 — FRENCH_STOPWORDS must have at least 100 entries."""
        assert len(FRENCH_STOPWORDS) >= 100, (
            f"FRENCH_STOPWORDS has only {len(FRENCH_STOPWORDS)} entries, "
            f"R063 requires >= 100"
        )

    def test_english_stopwords_meet_minimum_size(self) -> None:
        """R063 — ENGLISH_STOPWORDS must have at least 100 entries."""
        assert len(ENGLISH_STOPWORDS) >= 100, (
            f"ENGLISH_STOPWORDS has only {len(ENGLISH_STOPWORDS)} entries, "
            f"R063 requires >= 100"
        )

    def test_all_stopwords_is_union(self) -> None:
        assert ALL_STOPWORDS == (ENGLISH_STOPWORDS | FRENCH_STOPWORDS)


class TestFrenchContractions:
    """R063 — canonical contracted forms must be part of FRENCH_STOPWORDS."""

    def test_common_contractions_present(self) -> None:
        canonical = [
            "c'est", "j'ai", "d'un", "d'une",
            "qu'il", "qu'elle", "n'est", "n'a",
            "s'il", "s'est", "l'autre", "l'un",
        ]
        missing = [c for c in canonical if c not in FRENCH_STOPWORDS]
        assert not missing, f"missing contractions: {missing}"


class TestFrenchConjugatedVerbs:
    """R063 — common conjugated verb forms must be part of FRENCH_STOPWORDS."""

    def test_common_conjugated_verbs_present(self) -> None:
        canonical = [
            "veux", "veut", "peux", "peut", "pouvez", "peuvent",
            "dois", "doit", "sais", "sait",
            "vois", "voit", "viens", "vient",
            "dit", "fait", "montrer", "montré",
            "pris", "mis", "passé",
        ]
        missing = [v for v in canonical if v not in FRENCH_STOPWORDS]
        assert not missing, f"missing conjugated verbs: {missing}"

    def test_private_sets_are_importable(self) -> None:
        """The two new private frozensets must exist as module attributes."""
        from vidscope.adapters.heuristic import stopwords as sw

        assert hasattr(sw, "_FRENCH_CONTRACTIONS"), (
            "_FRENCH_CONTRACTIONS frozenset missing from stopwords module"
        )
        assert hasattr(sw, "_FRENCH_COMMON_VERBS"), (
            "_FRENCH_COMMON_VERBS frozenset missing from stopwords module"
        )
        assert isinstance(sw._FRENCH_CONTRACTIONS, frozenset)
        assert isinstance(sw._FRENCH_COMMON_VERBS, frozenset)
        # Size sanity
        assert len(sw._FRENCH_CONTRACTIONS) >= 30
        assert len(sw._FRENCH_COMMON_VERBS) >= 40
