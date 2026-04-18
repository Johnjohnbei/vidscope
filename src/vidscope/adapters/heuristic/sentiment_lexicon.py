"""Sentiment classifier based on a static FR+EN lexicon — zero deps.

Strategy
--------

Count positive and negative word hits in the lowercased transcript.
The winner wins; ties (both >0 and |pos-neg| small) → MIXED; both zero
→ NEUTRAL. The lexicon is explicit so reviewers can audit it; it is
deliberately small (<200 entries total) to keep runtime under a
millisecond.

Known limitations (documented, not bugs)
----------------------------------------
- No negation parsing: "not good" counts as one positive hit. A real
  negation parser is future work — M010 ROADMAP explicitly defers
  per-sentence sentiment.
- No intensifier weights: "very good" scores the same as "good".
- No sarcasm detection.

Good-enough for zero-cost short-form content. LLM analyzers in S03
will do better.
"""

from __future__ import annotations

import re
from typing import Final

from vidscope.domain import SentimentLabel

__all__ = ["NEGATIVE_WORDS", "POSITIVE_WORDS", "SentimentLexicon"]


_TOKEN_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)


# English positive vocabulary
_POSITIVE_EN: Final[frozenset[str]] = frozenset({
    "love", "loved", "loving", "amazing", "awesome", "great", "excellent",
    "perfect", "beautiful", "fantastic", "wonderful", "brilliant", "best",
    "incredible", "outstanding", "superb", "delighted", "happy", "glad",
    "enjoy", "enjoyed", "enjoying", "recommend", "recommended", "fabulous",
    "terrific", "stellar", "impressive", "favorite", "favourite", "stunning",
    "good", "nice", "cool", "fun",
    # Comedy / humour positive signals
    "funny", "hilarious", "lol", "haha", "amusing", "entertaining", "gold",
})

# French positive vocabulary
_POSITIVE_FR: Final[frozenset[str]] = frozenset({
    "adore", "adorer", "adoré", "génial", "géniale", "super", "excellent",
    "excellente", "parfait", "parfaite", "magnifique", "fantastique",
    "merveilleux", "merveilleuse", "recommande", "content", "contente",
    "heureux", "heureuse", "ravi", "ravie", "kiffe", "kiffer",
    "utile", "incroyable", "top", "bien", "bravo", "magique",
    # Comedy / humour positive signals
    "drôle", "hilarant", "hilarante", "amusant", "amusante",
})

# English negative vocabulary
_NEGATIVE_EN: Final[frozenset[str]] = frozenset({
    "hate", "hated", "hating", "awful", "terrible", "horrible", "worst",
    "bad", "boring", "disappointing", "disappointed", "useless", "sucks",
    "sucked", "ugly", "broken", "wrong", "nasty", "annoying", "painful",
    "regret", "regretted", "scam", "fail", "failed", "failure", "garbage",
    "trash", "crap", "waste",
})

# French negative vocabulary
_NEGATIVE_FR: Final[frozenset[str]] = frozenset({
    "déteste", "détesté", "horrible", "nul", "nulle", "affreux", "affreuse",
    "décevant", "décevante", "déçu", "déçue", "mauvais", "mauvaise",
    "ennuyeux", "ennuyeuse", "inutile", "moche", "moches", "raté",
    "ratée", "catastrophe", "arnaque", "échec", "pire", "triste",
    "fâché", "fâchée",
})

POSITIVE_WORDS: Final[frozenset[str]] = _POSITIVE_EN | _POSITIVE_FR
NEGATIVE_WORDS: Final[frozenset[str]] = _NEGATIVE_EN | _NEGATIVE_FR


# Threshold for MIXED: when both sides have hits AND |pos-neg| <= this,
# the signal is too ambiguous → mixed.
_MIXED_DIFF_THRESHOLD: Final[int] = 1


class SentimentLexicon:
    """Classify a transcript's overall sentiment from a static lexicon.

    The default instance uses the module-level ``POSITIVE_WORDS`` and
    ``NEGATIVE_WORDS`` frozensets. Tests inject custom lexicons by
    passing ``positive`` / ``negative`` arguments.
    """

    def __init__(
        self,
        *,
        positive: frozenset[str] | None = None,
        negative: frozenset[str] | None = None,
    ) -> None:
        self._positive = positive if positive is not None else POSITIVE_WORDS
        self._negative = negative if negative is not None else NEGATIVE_WORDS

    def classify(self, text: str) -> SentimentLabel:
        """Classify ``text`` as POSITIVE/NEGATIVE/NEUTRAL/MIXED.

        Empty or whitespace-only input is NEUTRAL (not None — callers
        get a deterministic value).
        """
        if not text or not text.strip():
            return SentimentLabel.NEUTRAL

        tokens = {m.group(0).lower() for m in _TOKEN_PATTERN.finditer(text)}
        if not tokens:
            return SentimentLabel.NEUTRAL

        pos_hits = len(tokens & self._positive)
        neg_hits = len(tokens & self._negative)

        if pos_hits == 0 and neg_hits == 0:
            return SentimentLabel.NEUTRAL
        if pos_hits > 0 and neg_hits > 0:
            # Both signals present → MIXED unless one dominates clearly.
            if abs(pos_hits - neg_hits) <= _MIXED_DIFF_THRESHOLD:
                return SentimentLabel.MIXED
            return SentimentLabel.POSITIVE if pos_hits > neg_hits else SentimentLabel.NEGATIVE
        return SentimentLabel.POSITIVE if pos_hits > 0 else SentimentLabel.NEGATIVE
