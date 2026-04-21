"""Unit tests for HeuristicAnalyzer."""

from __future__ import annotations

from vidscope.adapters.heuristic import HeuristicAnalyzer, StubAnalyzer
from vidscope.domain import (
    Analysis,
    Language,
    Transcript,
    TranscriptSegment,
    VideoId,
)


def _transcript(
    text: str,
    *,
    language: Language = Language.ENGLISH,
    segment_count: int = 1,
) -> Transcript:
    """Build a Transcript with N segments evenly dividing the text."""
    if not text or segment_count == 0:
        segments: tuple[TranscriptSegment, ...] = ()
    else:
        chunk = max(1, len(text) // segment_count)
        segments = tuple(
            TranscriptSegment(
                start=float(i * 2),
                end=float((i + 1) * 2),
                text=text[i * chunk : (i + 1) * chunk] or text,
            )
            for i in range(segment_count)
        )
    return Transcript(
        video_id=VideoId(1),
        language=language,
        full_text=text,
        segments=segments,
    )


# ---------------------------------------------------------------------------
# HeuristicAnalyzer
# ---------------------------------------------------------------------------


class TestHeuristicAnalyzerEmptyTranscript:
    def test_empty_text_returns_zero_score_summary_no_speech(self) -> None:
        analyzer = HeuristicAnalyzer()
        result = analyzer.analyze(_transcript(""))
        assert isinstance(result, Analysis)
        assert result.provider == "heuristic"
        assert result.score == 0.0
        assert result.summary == "no speech detected"
        assert result.keywords == ()
        assert result.topics == ()

    def test_whitespace_only_text_returns_no_speech(self) -> None:
        result = HeuristicAnalyzer().analyze(_transcript("   \n\t"))
        assert result.score == 0.0
        assert result.summary == "no speech detected"


class TestHeuristicAnalyzerEnglishContent:
    def test_extracts_keywords(self) -> None:
        text = (
            "Python programming is wonderful. Python makes data analysis easy. "
            "I love Python and data science. Programming with Python is fun."
        )
        result = HeuristicAnalyzer().analyze(
            _transcript(text, language=Language.ENGLISH, segment_count=4)
        )
        # 'python' should be the top keyword (4 occurrences, >= 4 chars)
        assert "python" in result.keywords
        assert result.score > 0
        assert result.score <= 100
        assert result.summary  # non-empty
        assert result.language is Language.ENGLISH

    def test_topics_are_subset_of_keywords(self) -> None:
        text = "data analysis machine learning python statistics analysis data"
        result = HeuristicAnalyzer().analyze(_transcript(text))
        assert all(topic in result.keywords for topic in result.topics)
        assert len(result.topics) <= 3

    def test_stopwords_excluded_from_keywords(self) -> None:
        text = "the quick brown fox jumps over the lazy dog the dog runs"
        result = HeuristicAnalyzer().analyze(_transcript(text))
        # 'the' is a stopword and shouldn't appear
        assert "the" not in result.keywords
        # But 'quick', 'brown', 'jumps', etc. (>= 4 chars, non-stopword) might
        assert all(len(kw) >= 4 for kw in result.keywords)


class TestHeuristicAnalyzerFrenchContent:
    def test_french_keywords_extracted(self) -> None:
        text = (
            "Aujourd'hui nous parlons de cuisine italienne. Les pâtes "
            "fraîches sont délicieuses. La cuisine italienne est riche."
        )
        result = HeuristicAnalyzer().analyze(
            _transcript(text, language=Language.FRENCH, segment_count=3)
        )
        assert result.language is Language.FRENCH
        # 'cuisine' and 'italienne' should appear
        assert any("cuisine" in kw for kw in result.keywords)
        assert result.score > 0

    def test_french_stopwords_excluded(self) -> None:
        text = "le chat et le chien dans la maison avec les enfants"
        result = HeuristicAnalyzer().analyze(
            _transcript(text, language=Language.FRENCH)
        )
        for stopword in ("le", "la", "les", "et", "dans", "avec"):
            assert stopword not in result.keywords


class TestHeuristicAnalyzerScoring:
    def test_score_in_zero_to_one_hundred(self) -> None:
        # Long text with many distinct words
        text = " ".join(f"word{i}" for i in range(100))
        result = HeuristicAnalyzer().analyze(
            _transcript(text, segment_count=10)
        )
        assert 0.0 <= result.score <= 100.0

    def test_longer_transcript_scores_higher_than_shorter(self) -> None:
        short = HeuristicAnalyzer().analyze(_transcript("hi"))
        longer = HeuristicAnalyzer().analyze(
            _transcript("the cat sat on the mat", segment_count=2)
        )
        assert longer.score > short.score


class TestHeuristicAnalyzerSummary:
    def test_short_text_returned_as_is(self) -> None:
        text = "this is a short transcript."
        result = HeuristicAnalyzer().analyze(_transcript(text))
        assert result.summary == text

    def test_long_text_truncated_with_ellipsis(self) -> None:
        text = " ".join("word" for _ in range(100))  # 499 chars
        result = HeuristicAnalyzer().analyze(_transcript(text))
        assert result.summary.endswith("...")
        assert len(result.summary) <= 210  # 200 + ellipsis margin


class TestHeuristicAnalyzerProviderName:
    def test_provider_name_is_heuristic(self) -> None:
        assert HeuristicAnalyzer().provider_name == "heuristic"


# ---------------------------------------------------------------------------
# StubAnalyzer
# ---------------------------------------------------------------------------


class TestStubAnalyzer:
    def test_provider_name_is_stub(self) -> None:
        assert StubAnalyzer().provider_name == "stub"

    def test_returns_placeholder_analysis(self) -> None:
        result = StubAnalyzer().analyze(
            _transcript("any text here", language=Language.ENGLISH)
        )
        assert result.provider == "stub"
        assert result.keywords == ()
        assert result.topics == ()
        assert result.score is None
        assert "stub" in result.summary.lower() if result.summary else False

    def test_preserves_transcript_video_id(self) -> None:
        transcript = _transcript("hello")
        result = StubAnalyzer().analyze(transcript)
        assert result.video_id == transcript.video_id


# ---------------------------------------------------------------------------
# R063 — French contractions and conjugated verbs filtered
# ---------------------------------------------------------------------------


class TestHeuristicAnalyzerFrenchStopwordsR063:
    """R063 — French contractions and conjugated verbs are filtered."""

    def test_french_contractions_excluded_from_keywords(self) -> None:
        text = (
            "c'est vraiment intéressant j'ai pensé d'un nouveau concept "
            "qu'il faut montrer n'est pas évident s'il existe une solution"
        )
        result = HeuristicAnalyzer().analyze(
            _transcript(text, language=Language.FRENCH)
        )
        for contracted in ("c'est", "j'ai", "d'un", "qu'il", "n'est", "s'il"):
            assert contracted not in result.keywords, (
                f"contracted form {contracted!r} leaked into keywords: "
                f"{result.keywords}"
            )

    def test_french_conjugated_verbs_excluded_from_keywords(self) -> None:
        text = (
            "je veux vous montrer comment vous peux créer avec ça "
            "pouvez prendre ce que j'ai pris et mis dans le projet montré"
        )
        result = HeuristicAnalyzer().analyze(
            _transcript(text, language=Language.FRENCH)
        )
        for verb in ("veux", "peux", "pouvez", "montrer", "montré", "pris", "mis"):
            assert verb not in result.keywords, (
                f"common conjugated verb {verb!r} leaked into keywords: "
                f"{result.keywords}"
            )

    def test_claude_skills_carousel_keeps_domain_tokens(self) -> None:
        """R063 — real-world carousel FR+EN mix yields domain topics only."""
        text = (
            "je veux vous montrer c'est un outil puissant pour créer "
            "des skills Claude dans le terminal avec un agent workflow"
        )
        result = HeuristicAnalyzer().analyze(
            _transcript(text, language=Language.FRENCH)
        )
        # Domain tokens retained (lowercase by tokenizer)
        assert "claude" in result.keywords
        assert "skills" in result.keywords or "terminal" in result.keywords
        # Grammar noise excluded
        for noise in ("veux", "montrer", "c'est", "pour", "des", "dans"):
            assert noise not in result.keywords, (
                f"noise {noise!r} leaked into keywords: {result.keywords}"
            )
