"""StubAnalyzer — minimal second analyzer to prove the pluggable seam.

Returns a placeholder Analysis without doing any real work. The
purpose is purely to demonstrate that the analyzer registry can
swap providers via VIDSCOPE_ANALYZER without touching any caller.
This satisfies R010 (pluggable provider interface) by proving the
seam works with at least two implementations.

A future M004 milestone will replace this stub with real LLM-backed
analyzers (NVIDIA Build, Groq, OpenRouter, OpenAI, Anthropic).
"""

from __future__ import annotations

from vidscope.domain import Analysis, Transcript

__all__ = ["StubAnalyzer"]


class StubAnalyzer:
    """Placeholder Analyzer that returns an empty analysis.

    Exists solely to prove that the analyzer registry can pick
    between multiple Analyzer implementations. Not useful in
    production — set ``VIDSCOPE_ANALYZER=stub`` only when testing
    the registry itself.
    """

    @property
    def provider_name(self) -> str:
        return "stub"

    def analyze(self, transcript: Transcript) -> Analysis:
        return Analysis(
            video_id=transcript.video_id,
            provider=self.provider_name,
            language=transcript.language,
            keywords=(),
            topics=(),
            score=None,
            summary=(
                "stub analyzer — set VIDSCOPE_ANALYZER=heuristic for "
                "the real default analyzer"
            ),
        )
