"""Unit tests for HeuristicAnalyzerV2 — M010 9-field output."""

from __future__ import annotations

import pytest

from vidscope.adapters.heuristic.heuristic_v2 import HeuristicAnalyzerV2
from vidscope.adapters.heuristic.sentiment_lexicon import SentimentLexicon
from vidscope.adapters.heuristic.sponsor_detector import SponsorDetector
from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    SentimentLabel,
    Transcript,
    TranscriptSegment,
    VideoId,
)


class _StubTaxonomy:
    """Minimal TaxonomyCatalog stub for unit tests."""

    def __init__(self, mapping: dict[str, frozenset[str]] | None = None) -> None:
        self._data = mapping or {
            "tech": frozenset({"python", "code", "pip"}),
            "fitness": frozenset({"workout", "squat", "reps"}),
        }

    def verticals(self) -> list[str]:
        return sorted(self._data.keys())

    def keywords_for_vertical(self, vertical: str) -> frozenset[str]:
        return self._data.get(vertical, frozenset())

    def match(self, tokens: list[str]) -> list[str]:
        lowered = {t.lower() for t in tokens}
        scored: list[tuple[int, str]] = []
        for slug, kws in self._data.items():
            hits = len(lowered & kws)
            if hits:
                scored.append((hits, slug))
        scored.sort(key=lambda p: (-p[0], p[1]))
        return [s for _, s in scored]


def _make_transcript(
    text: str, *, language: Language = Language.ENGLISH, segments: int = 3,
) -> Transcript:
    if not text or segments == 0:
        segs: tuple[TranscriptSegment, ...] = ()
    else:
        chunk = max(1, len(text) // segments)
        segs = tuple(
            TranscriptSegment(start=float(i * 2), end=float((i + 1) * 2),
                              text=text[i * chunk:(i + 1) * chunk] or text)
            for i in range(segments)
        )
    return Transcript(video_id=VideoId(1), language=language, full_text=text, segments=segs)


class TestProviderName:
    def test_provider_name_is_heuristic(self) -> None:
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        assert a.provider_name == "heuristic"


class TestConstructor:
    def test_requires_taxonomy_kwarg(self) -> None:
        with pytest.raises(TypeError):
            HeuristicAnalyzerV2()  # type: ignore[call-arg]

    def test_injects_defaults_for_optional_deps(self) -> None:
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        # construction succeeds — no error
        assert a is not None

    def test_accepts_custom_sentiment_and_sponsor(self) -> None:
        custom_lex = SentimentLexicon(
            positive=frozenset({"xyz"}), negative=frozenset({"abc"}),
        )
        custom_det = SponsorDetector(markers=frozenset({"xyzbrand"}))
        a = HeuristicAnalyzerV2(
            taxonomy=_StubTaxonomy(),
            sentiment_lexicon=custom_lex,
            sponsor_detector=custom_det,
        )
        t = _make_transcript("xyz is great, xyzbrand in bio")
        r = a.analyze(t)
        assert r.sentiment is SentimentLabel.POSITIVE
        assert r.is_sponsored is True


class TestEmptyTranscript:
    def test_empty_transcript_has_sensible_defaults(self) -> None:
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript("", segments=0))
        assert isinstance(r, Analysis)
        assert r.score == 0.0
        assert r.summary == "no speech detected"
        assert r.sentiment is SentimentLabel.NEUTRAL
        assert r.is_sponsored is False
        assert r.content_type is ContentType.UNKNOWN
        assert r.verticals == ()
        assert r.information_density == 0.0
        assert r.actionability == 0.0
        assert r.reasoning is not None and len(r.reasoning) > 0


class TestAllNineFieldsPopulated:
    def test_tutorial_transcript_fills_every_m010_field(self) -> None:
        text = (
            "Today I will show you how to install Python. "
            "First, open your terminal and type pip install. "
            "Then, run your first program. This is a great tutorial, "
            "perfect for beginners learning to code."
        )
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript(text, segments=4))

        # Every M010 field is non-None (or non-empty)
        assert r.content_type is not None
        assert r.sentiment is not None
        assert r.is_sponsored is not None
        assert r.information_density is not None and 0.0 <= r.information_density <= 100.0
        assert r.actionability is not None and 0.0 <= r.actionability <= 100.0
        assert r.novelty is not None and 0.0 <= r.novelty <= 100.0
        assert r.production_quality is not None and 0.0 <= r.production_quality <= 100.0
        assert r.reasoning is not None and len(r.reasoning) > 20

    def test_tutorial_classified_as_tutorial(self) -> None:
        text = "Open the terminal. Install Python. Run pip. Type the code."
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript(text))
        assert r.content_type is ContentType.TUTORIAL

    def test_review_classified_as_review(self) -> None:
        text = "A full review of the product. Pros and cons, compared versus others. Verdict: better."
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript(text))
        assert r.content_type is ContentType.REVIEW


class TestSentimentIntegration:
    def test_positive_transcript_positive_sentiment(self) -> None:
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript("This is amazing, I love it, fantastic tutorial"))
        assert r.sentiment is SentimentLabel.POSITIVE


class TestSponsorIntegration:
    def test_sponsored_transcript_detected(self) -> None:
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript("This video is sponsored by BrandX, great tutorial"))
        assert r.is_sponsored is True

    def test_non_sponsored_transcript_false(self) -> None:
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript("Regular tutorial about Python"))
        assert r.is_sponsored is False


class TestVerticalsIntegration:
    def test_tech_tokens_map_to_tech_vertical(self) -> None:
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript("Install Python pip and write code"))
        assert "tech" in r.verticals

    def test_fitness_tokens_map_to_fitness(self) -> None:
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript("Workout, squat, ten reps, workout"))
        assert "fitness" in r.verticals


class TestReasoning:
    def test_reasoning_mentions_content_type_and_sentiment(self) -> None:
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript("Open terminal, install Python, great tutorial"))
        assert r.reasoning is not None
        lowered = r.reasoning.lower()
        assert r.content_type.value in lowered
        assert r.sentiment.value in lowered

    def test_reasoning_flags_sponsored(self) -> None:
        a = HeuristicAnalyzerV2(taxonomy=_StubTaxonomy())
        r = a.analyze(_make_transcript("Sponsored by BrandX, today I cook pasta"))
        assert r.reasoning is not None
        assert "sponsored" in r.reasoning.lower()
