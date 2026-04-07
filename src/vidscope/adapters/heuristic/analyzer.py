"""HeuristicAnalyzer — pure-Python zero-cost default analyzer.

Implements the :class:`~vidscope.ports.pipeline.Analyzer` port
without any network call, model download, or paid API. Suitable as
the default analyzer for every video the user ingests.

Strategy
--------

- **Language**: copied from the transcript (already detected by
  faster-whisper in S03)
- **Keywords**: top 8 most frequent non-stopword tokens >= 4 chars,
  case-insensitive, basic punctuation stripping
- **Topics**: top 3 keywords as a quick proxy — a real topic model
  would need clustering, which is out of scope for the heuristic
  baseline (R024 will provide LLM-backed topic extraction in M004)
- **Score**: composite of (text length, vocabulary diversity,
  segment count) normalized to 0-100. Empty transcript → 0.
- **Summary**: first 200 chars of full_text, truncated at the last
  space, with "..." appended. Empty transcript → "no speech detected".

Pure stdlib: re, collections.Counter. No third-party imports.
"""

from __future__ import annotations

import re
from collections import Counter

from vidscope.adapters.heuristic.stopwords import ALL_STOPWORDS
from vidscope.domain import Analysis, Transcript

__all__ = ["HeuristicAnalyzer"]


_WORD_PATTERN = re.compile(r"[a-zàâäéèêëïîôöùûüÿçœæ']+", re.IGNORECASE)
_MIN_KEYWORD_LENGTH = 4
_KEYWORDS_TOP_N = 8
_TOPICS_TOP_N = 3
_SUMMARY_MAX_CHARS = 200
_EMPTY_SUMMARY = "no speech detected"


class HeuristicAnalyzer:
    """Pure-Python Analyzer producing zero-cost analyses.

    The provider name ``'heuristic'`` is the default selected by
    :class:`vidscope.infrastructure.config.Config.analyzer_name`.
    """

    @property
    def provider_name(self) -> str:
        return "heuristic"

    def analyze(self, transcript: Transcript) -> Analysis:
        """Produce an :class:`Analysis` from a :class:`Transcript`.

        Empty transcripts (no speech detected) still return a valid
        Analysis row with score=0 and summary='no speech detected'
        so the row exists for the search index in S06.
        """
        text = transcript.full_text or ""
        if not text.strip():
            return Analysis(
                video_id=transcript.video_id,
                provider=self.provider_name,
                language=transcript.language,
                keywords=(),
                topics=(),
                score=0.0,
                summary=_EMPTY_SUMMARY,
            )

        tokens = _tokenize(text)
        meaningful = [t for t in tokens if _is_meaningful_word(t)]

        keywords = _top_n(meaningful, _KEYWORDS_TOP_N)
        topics = tuple(keywords[:_TOPICS_TOP_N])
        score = _compute_score(
            text=text,
            tokens=tokens,
            meaningful=meaningful,
            segment_count=len(transcript.segments),
        )
        summary = _build_summary(text)

        return Analysis(
            video_id=transcript.video_id,
            provider=self.provider_name,
            language=transcript.language,
            keywords=tuple(keywords),
            topics=topics,
            score=score,
            summary=summary,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Split ``text`` into lowercase word tokens."""
    return [m.group(0).lower() for m in _WORD_PATTERN.finditer(text)]


def _is_meaningful_word(token: str) -> bool:
    """Return True for tokens worth counting as keyword candidates.

    Excludes stopwords and tokens shorter than 4 characters.
    """
    return len(token) >= _MIN_KEYWORD_LENGTH and token not in ALL_STOPWORDS


def _top_n(tokens: list[str], n: int) -> list[str]:
    """Return the ``n`` most frequent tokens, ties broken by first
    appearance order (Counter preserves insertion order in 3.12)."""
    if not tokens:
        return []
    counts = Counter(tokens)
    return [word for word, _ in counts.most_common(n)]


def _compute_score(
    *,
    text: str,
    tokens: list[str],
    meaningful: list[str],
    segment_count: int,
) -> float:
    """Composite score in [0, 100].

    Three sub-signals, each capped at the dimension's max contribution:

    - **Text length** (max 40 points): 1 point per 25 chars, capped
    - **Vocabulary diversity** (max 30 points): unique meaningful
      tokens / total meaningful tokens, scaled to [0, 30]
    - **Segment density** (max 30 points): 5 points per segment,
      capped at 30 (so any video with >=6 segments hits the cap)
    """
    if not text.strip():
        return 0.0

    length_score = min(40.0, len(text) / 25.0)

    if meaningful:
        diversity = len(set(meaningful)) / len(meaningful)
        diversity_score = diversity * 30.0
    else:
        diversity_score = 0.0

    segment_score = min(30.0, segment_count * 5.0)

    return round(length_score + diversity_score + segment_score, 2)


def _build_summary(text: str) -> str:
    """Return the first ~200 chars of ``text``, truncated at the last
    space, with ``...`` appended when truncation actually happened."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= _SUMMARY_MAX_CHARS:
        return cleaned
    truncated = cleaned[:_SUMMARY_MAX_CHARS]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."
