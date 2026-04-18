"""LinkExtractor port.

Extracts URLs from arbitrary text (video description, transcript full
text, OCR output in M008). Implementations are expected to be pure —
no network call, no DB access. See M007/S02
:class:`RegexLinkExtractor` for the default implementation.
"""

from __future__ import annotations

from typing import Protocol, TypedDict, runtime_checkable

__all__ = ["LinkExtractor", "RawLink"]


class RawLink(TypedDict):
    """One URL extracted from text.

    ``url`` is the raw string as captured (case preserved, trailing
    punctuation stripped). ``normalized_url`` is the deduplication
    key — see M007/S02 ``URLNormalizer`` for the exact shape
    (lowercase scheme+host, stripped utm_*, strip fragment, sorted
    query params). ``source`` is ``"description"``, ``"transcript"``,
    or ``"ocr"``. ``position_ms`` is optional per source type
    (``None`` for description-sourced URLs; transcript/OCR may
    populate it when a timestamp is known).
    """

    url: str
    normalized_url: str
    source: str
    position_ms: int | None


@runtime_checkable
class LinkExtractor(Protocol):
    """Pure URL extractor — no I/O.

    The default implementation in :mod:`vidscope.adapters.text`
    (M007/S02) uses a regex + a restricted TLD list to minimise
    false positives like ``hello.world`` or ``version 1.0.0``. See
    the non-negotiable fixture corpus at
    ``tests/fixtures/link_corpus.json`` for the quality gate.
    """

    def extract(self, text: str, *, source: str) -> list[RawLink]:
        """Extract URLs from ``text``. Returns empty list when none.

        ``source`` is copied verbatim into every returned
        :class:`RawLink`. Callers pass ``"description"`` at ingest
        time, ``"transcript"`` after TranscribeStage. The extractor
        MUST NOT raise on any input string — garbage in, empty out.
        """
        ...
