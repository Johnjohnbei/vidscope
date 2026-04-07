"""Heuristic analyzer adapter package.

Provides the default zero-cost, zero-network Analyzer implementation
plus a stub second analyzer to prove the pluggable provider seam (R010).
"""

from __future__ import annotations

from vidscope.adapters.heuristic.analyzer import HeuristicAnalyzer
from vidscope.adapters.heuristic.stub import StubAnalyzer

__all__ = ["HeuristicAnalyzer", "StubAnalyzer"]
