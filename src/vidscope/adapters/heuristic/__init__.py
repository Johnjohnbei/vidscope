"""Heuristic analyzer adapter package.

Provides the default zero-cost, zero-network Analyzer implementation
plus a stub second analyzer to prove the pluggable provider seam (R010).
"""

from __future__ import annotations

from vidscope.adapters.heuristic.analyzer import HeuristicAnalyzer
from vidscope.adapters.heuristic.sentiment_lexicon import (
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    SentimentLexicon,
)
from vidscope.adapters.heuristic.sponsor_detector import (
    SPONSOR_MARKERS,
    SponsorDetector,
)
from vidscope.adapters.heuristic.stub import StubAnalyzer

__all__ = [
    "NEGATIVE_WORDS",
    "POSITIVE_WORDS",
    "SPONSOR_MARKERS",
    "HeuristicAnalyzer",
    "SentimentLexicon",
    "SponsorDetector",
    "StubAnalyzer",
]
