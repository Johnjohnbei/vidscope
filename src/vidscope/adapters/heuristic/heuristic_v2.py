"""HeuristicAnalyzerV2 — multi-dimensional scoring + controlled taxonomy.

Produces the 9 M010 Analysis fields (information_density, actionability,
novelty, production_quality, sentiment, is_sponsored, content_type,
verticals, reasoning) from a transcript alone — zero network.

Dimension strategies (cheap heuristics, documented limitations):

- ``information_density`` — meaningful-token density × length factor.
- ``actionability`` — imperative-verb + CTA-phrase hit count.
- ``novelty`` — inverse of very-common-word density + specialised-term
  density (via ``TaxonomyCatalog`` match count).
- ``production_quality`` — segment-density proxy (transcripts with more
  segments-per-second indicate clearer delivery).
- ``sentiment`` — delegated to ``SentimentLexicon``.
- ``is_sponsored`` — delegated to ``SponsorDetector``.
- ``content_type`` — structural rules (imperatives → TUTORIAL,
  first-person narration → VLOG, comparatives → REVIEW, etc).
- ``verticals`` — delegated to ``TaxonomyCatalog.match(tokens)``.
- ``reasoning`` — single-paragraph template citing the detected
  content_type + sentiment + top vertical.

The implementation reuses V1 helpers (``_tokenize`` etc.) for keywords /
score / summary so downstream tests that assert V1-compat outputs keep
working.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Final

from vidscope.adapters.heuristic.analyzer import (
    _build_summary,
    _compute_score,
    _is_meaningful_word,
    _tokenize,
)
from vidscope.adapters.heuristic.sentiment_lexicon import SentimentLexicon
from vidscope.adapters.heuristic.sponsor_detector import SponsorDetector
from vidscope.domain import (
    Analysis,
    ContentType,
    SentimentLabel,
    Transcript,
)
from vidscope.ports.taxonomy_catalog import TaxonomyCatalog

__all__ = ["HeuristicAnalyzerV2"]


_PROVIDER_NAME: Final[str] = "heuristic"
_EMPTY_SUMMARY: Final[str] = "no speech detected"


# --- Dimension-specific lexicons ---

# Imperatives + CTA phrases (EN + FR) — indicate actionability / tutorial content
_ACTION_MARKERS: Final[frozenset[str]] = frozenset({
    # imperatives EN
    "do", "try", "open", "click", "install", "run", "use", "type",
    "press", "write", "create", "make", "build", "copy", "paste",
    "save", "check", "set", "change", "update", "download", "upload",
    "follow", "subscribe", "watch", "learn",
    # imperatives FR
    "faites", "essayez", "ouvrez", "installez", "lancez", "utilisez",
    "tapez", "appuyez", "écrivez", "créez", "construisez", "copiez",
    "collez", "enregistrez", "vérifiez", "changez", "mettez",
    "téléchargez", "suivez", "regardez", "apprenez",
})

# Review / comparative markers
_REVIEW_MARKERS: Final[frozenset[str]] = frozenset({
    "review", "compared", "versus", "vs", "better", "worse", "rating",
    "pros", "cons", "verdict", "test", "tested", "comparaison", "avis",
    "meilleur", "pire", "note", "testé",
})

# Vlog / first-person narrative markers
_VLOG_MARKERS: Final[frozenset[str]] = frozenset({
    "my", "today", "yesterday", "morning", "day", "life", "routine",
    "vlog", "feelings", "aujourd", "hier", "matin", "journée",
    "vie", "quotidien",
})

# News / current-events markers
_NEWS_MARKERS: Final[frozenset[str]] = frozenset({
    "news", "announced", "breaking", "report", "official", "launched",
    "released", "statement", "actualité", "annoncé", "rapport",
    "officiel", "sorti",
})

# Comedy / humor markers
_COMEDY_MARKERS: Final[frozenset[str]] = frozenset({
    "joke", "funny", "lol", "haha", "comedy", "prank", "skit",
    "blague", "drôle", "hilarant", "humour",
})

# Promo / product showcase markers
_PROMO_MARKERS: Final[frozenset[str]] = frozenset({
    "buy", "sale", "discount", "deal", "offer", "shop", "product",
    "collection", "launch", "achat", "solde", "promo", "offre",
    "boutique", "lancement",
})

_WORD_PATTERN: Final[re.Pattern[str]] = re.compile(r"[^\W\d_]+", re.UNICODE)


# --- HeuristicAnalyzerV2 ---


class HeuristicAnalyzerV2:
    """Pure-Python multi-dimensional analyzer — M010 default."""

    def __init__(
        self,
        *,
        taxonomy: TaxonomyCatalog,
        sentiment_lexicon: SentimentLexicon | None = None,
        sponsor_detector: SponsorDetector | None = None,
    ) -> None:
        self._taxonomy = taxonomy
        self._sentiment = sentiment_lexicon or SentimentLexicon()
        self._sponsor = sponsor_detector or SponsorDetector()

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    def analyze(self, transcript: Transcript) -> Analysis:
        text = transcript.full_text or ""
        if not text.strip():
            return self._empty_analysis(transcript)

        tokens = _tokenize(text)
        meaningful = [t for t in tokens if _is_meaningful_word(t)]
        lowered = text.lower()

        # ---- Keywords / topics / score / summary (V1-compat) ----
        counts = Counter(meaningful)
        keywords = tuple(w for w, _ in counts.most_common(8))
        topics = keywords[:3]
        score = _compute_score(
            text=text,
            tokens=tokens,
            meaningful=meaningful,
            segment_count=len(transcript.segments),
        )
        summary = _build_summary(text)

        # ---- M010 fields ----
        verticals = tuple(self._taxonomy.match(list(tokens)))[:5]
        information_density = _information_density(tokens, meaningful, text)
        actionability = _actionability_score(lowered, tokens)
        novelty = _novelty_score(meaningful, verticals)
        production_quality = _production_quality(
            segments=len(transcript.segments),
            duration=_estimate_duration(transcript),
        )
        sentiment = self._sentiment.classify(text)
        is_sponsored = self._sponsor.detect(text)
        content_type = _detect_content_type(lowered, tokens)
        reasoning = _build_reasoning(
            content_type=content_type,
            sentiment=sentiment,
            is_sponsored=is_sponsored,
            verticals=verticals,
            information_density=information_density,
            actionability=actionability,
        )

        return Analysis(
            video_id=transcript.video_id,
            provider=_PROVIDER_NAME,
            language=transcript.language,
            keywords=keywords,
            topics=topics,
            score=score,
            summary=summary,
            verticals=verticals,
            information_density=information_density,
            actionability=actionability,
            novelty=novelty,
            production_quality=production_quality,
            sentiment=sentiment,
            is_sponsored=is_sponsored,
            content_type=content_type,
            reasoning=reasoning,
        )

    def _empty_analysis(self, transcript: Transcript) -> Analysis:
        return Analysis(
            video_id=transcript.video_id,
            provider=_PROVIDER_NAME,
            language=transcript.language,
            keywords=(),
            topics=(),
            score=0.0,
            summary=_EMPTY_SUMMARY,
            verticals=(),
            information_density=0.0,
            actionability=0.0,
            novelty=0.0,
            production_quality=0.0,
            sentiment=SentimentLabel.NEUTRAL,
            is_sponsored=False,
            content_type=ContentType.UNKNOWN,
            reasoning="No speech detected — heuristic analyzer could not derive signals.",
        )


# --- Dimension helpers ---


def _information_density(tokens: list[str], meaningful: list[str], text: str) -> float:
    if not tokens:
        return 0.0
    ratio = len(meaningful) / len(tokens)
    length_factor = min(1.0, len(text) / 400.0)
    return round(min(100.0, ratio * 100.0 * (0.5 + 0.5 * length_factor)), 2)


def _actionability_score(lowered: str, tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    token_set = set(tokens)
    hits = len(token_set & _ACTION_MARKERS)
    # Bonus for CTA phrases (substring-based)
    phrase_bonus = 0
    for phrase in ("how to", "step by step", "comment faire", "pas à pas"):
        if phrase in lowered:
            phrase_bonus += 1
    raw = hits * 10.0 + phrase_bonus * 15.0
    return round(min(100.0, raw), 2)


def _novelty_score(meaningful: list[str], verticals: tuple[str, ...]) -> float:
    if not meaningful:
        return 0.0
    unique_ratio = len(set(meaningful)) / max(1, len(meaningful))
    vertical_bonus = min(20.0, len(verticals) * 10.0)
    return round(min(100.0, unique_ratio * 80.0 + vertical_bonus), 2)


def _production_quality(*, segments: int, duration: float) -> float:
    if duration <= 0 or segments <= 0:
        return 0.0
    segments_per_minute = (segments / duration) * 60.0
    # 10 segments/min = good pacing → ~70 points; 20+/min → max
    score = min(100.0, segments_per_minute * 5.0)
    return round(score, 2)


def _estimate_duration(transcript: Transcript) -> float:
    if not transcript.segments:
        return 0.0
    last = transcript.segments[-1]
    return max(1.0, float(last.end))


def _detect_content_type(lowered: str, tokens: list[str]) -> ContentType:
    token_set = set(tokens)
    if token_set & _ACTION_MARKERS or "how to" in lowered or "comment faire" in lowered:
        return ContentType.TUTORIAL
    if token_set & _REVIEW_MARKERS:
        return ContentType.REVIEW
    if token_set & _NEWS_MARKERS:
        return ContentType.NEWS
    if token_set & _VLOG_MARKERS:
        return ContentType.VLOG
    if token_set & _COMEDY_MARKERS:
        return ContentType.COMEDY
    if token_set & _PROMO_MARKERS:
        return ContentType.PROMO
    # Educational fallback for content-heavy but not instructional videos
    if len(tokens) > 50:
        return ContentType.EDUCATIONAL
    return ContentType.UNKNOWN


def _build_reasoning(
    *,
    content_type: ContentType,
    sentiment: SentimentLabel,
    is_sponsored: bool,
    verticals: tuple[str, ...],
    information_density: float,
    actionability: float,
) -> str:
    top_vertical = verticals[0] if verticals else "no-dominant-vertical"
    sponsor_note = "sponsored content detected. " if is_sponsored else ""
    return (
        f"{sponsor_note}"
        f"Classified as {content_type.value} with {sentiment.value} sentiment. "
        f"Primary vertical: {top_vertical}. "
        f"Information density {information_density:.0f}/100, "
        f"actionability {actionability:.0f}/100."
    )
