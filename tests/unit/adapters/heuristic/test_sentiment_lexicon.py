"""Unit tests for SentimentLexicon — FR+EN coverage."""

from __future__ import annotations

import pytest

from vidscope.adapters.heuristic.sentiment_lexicon import (
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    SentimentLexicon,
)
from vidscope.domain import SentimentLabel


@pytest.fixture
def lex() -> SentimentLexicon:
    return SentimentLexicon()


class TestPositiveEnglish:
    @pytest.mark.parametrize("text", [
        "I love this tutorial",
        "This is amazing content",
        "Awesome recommendations",
        "Great work, fantastic production",
        "Excellent tips, really enjoyed it",
        "Perfect for beginners, beautiful design",
        "Best video I have seen today",
        "Brilliant and wonderful explanation",
    ])
    def test_positive_en_classifies_positive(self, lex: SentimentLexicon, text: str) -> None:
        assert lex.classify(text) is SentimentLabel.POSITIVE


class TestNegativeEnglish:
    @pytest.mark.parametrize("text", [
        "I hate this",
        "Terrible quality, worst video",
        "Awful experience, very boring",
        "This is garbage and useless",
        "Disappointed, sucks completely",
        "Horrible audio, broken editing",
        "Total failure, waste of time",
        "Nasty editing, ugly thumbnail",
    ])
    def test_negative_en_classifies_negative(self, lex: SentimentLexicon, text: str) -> None:
        assert lex.classify(text) is SentimentLabel.NEGATIVE


class TestPositiveFrench:
    @pytest.mark.parametrize("text", [
        "J'adore cette vidéo",
        "C'est génial et super utile",
        "Excellent travail, magnifique production",
        "Parfait pour débuter, je recommande",
        "Je suis ravi du résultat, bravo",
    ])
    def test_positive_fr_classifies_positive(self, lex: SentimentLexicon, text: str) -> None:
        assert lex.classify(text) is SentimentLabel.POSITIVE


class TestNegativeFrench:
    @pytest.mark.parametrize("text", [
        "C'est nul et décevant",
        "Horrible, vraiment ennuyeux",
        "Je déteste, affreux",
        "Mauvaise qualité, catastrophe",
        "Inutile et décevant, échec total",
    ])
    def test_negative_fr_classifies_negative(self, lex: SentimentLexicon, text: str) -> None:
        assert lex.classify(text) is SentimentLabel.NEGATIVE


class TestNeutral:
    @pytest.mark.parametrize("text", [
        "Today I will show you how to install Python",
        "The temperature outside is 22 degrees",
    ])
    def test_neutral_text_classifies_neutral(self, lex: SentimentLexicon, text: str) -> None:
        assert lex.classify(text) is SentimentLabel.NEUTRAL


class TestMixed:
    @pytest.mark.parametrize("text", [
        "I love the design but hate the price, awful value",
        "Great content, horrible audio quality",
    ])
    def test_balanced_pos_neg_classifies_mixed(self, lex: SentimentLexicon, text: str) -> None:
        assert lex.classify(text) is SentimentLabel.MIXED


class TestEdgeCases:
    def test_empty_string_is_neutral(self, lex: SentimentLexicon) -> None:
        assert lex.classify("") is SentimentLabel.NEUTRAL

    def test_whitespace_only_is_neutral(self, lex: SentimentLexicon) -> None:
        assert lex.classify("   \n\t") is SentimentLabel.NEUTRAL

    def test_case_insensitive(self, lex: SentimentLexicon) -> None:
        assert lex.classify("AMAZING AWESOME great") is SentimentLabel.POSITIVE

    def test_custom_lexicon_overrides_default(self) -> None:
        lex = SentimentLexicon(
            positive=frozenset({"fuzzyword"}),
            negative=frozenset({"crashword"}),
        )
        assert lex.classify("fuzzyword is the best") is SentimentLabel.POSITIVE
        assert lex.classify("crashword ruined it") is SentimentLabel.NEGATIVE

    def test_clear_dominance_despite_small_opposite_hits(self, lex: SentimentLexicon) -> None:
        """Many positives + 1 negative → positive (not mixed)."""
        text = "love amazing great excellent perfect fantastic — only one bad part"
        assert lex.classify(text) is SentimentLabel.POSITIVE


class TestLexiconSize:
    def test_positive_lexicon_not_empty(self) -> None:
        assert len(POSITIVE_WORDS) >= 30

    def test_negative_lexicon_not_empty(self) -> None:
        assert len(NEGATIVE_WORDS) >= 30

    def test_positive_and_negative_are_disjoint(self) -> None:
        assert POSITIVE_WORDS.isdisjoint(NEGATIVE_WORDS)
