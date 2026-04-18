"""RegexLinkExtractor — pure-Python regex URL extraction.

Strategy: two-pass regex.

1. **Scheme-explicit pass** — ``https?://...`` is easy and high-
   precision. Matches most captions / descriptions.

2. **Bare-domain pass** — captures ``bit.ly/abc``, ``shop.com/sale``
   where users omitted the scheme. To avoid false positives
   (``hello.world``, ``file.txt``, ``version 1.0.0``), bare matches
   require a TLD from a restricted list (``_COMMON_TLDS``). This
   trades recall for precision — preferred in M007 (the fixture
   corpus is the quality gate).

After both passes, results are deduplicated by ``normalized_url``
(per :func:`vidscope.adapters.text.url_normalizer.normalize_url`).

See the non-negotiable fixture corpus at
``tests/fixtures/link_corpus.json`` (≥ 100 strings) for the quality
gate. New edge cases → add to the corpus, re-run tests.
"""

from __future__ import annotations

import re
from re import Pattern
from typing import Final

from vidscope.adapters.text.url_normalizer import normalize_url
from vidscope.ports.link_extractor import RawLink

__all__ = ["RegexLinkExtractor"]


# Common TLDs used in the bare-domain pass. Tight list to minimise
# false positives on file extensions / version strings. Add only
# TLDs confirmed by the fixture corpus.
_COMMON_TLDS: Final[tuple[str, ...]] = (
    "com", "net", "org", "io", "co", "fr", "uk", "de", "app",
    "dev", "ly", "gg", "tv", "me", "ai", "tech", "shop", "store",
    "xyz", "link", "page",
)


_SCHEME_URL: Final[Pattern[str]] = re.compile(
    r"https?://"
    r"[^\s<>\"'`{}|\\^\[\]]+",
    re.IGNORECASE,
)


# Bare domain: "host.tld[/path][?query]" where tld is in _COMMON_TLDS.
# Negative lookbehind (?<![\\w@]) prevents matching inside words like
# "version1.0" or "file.txt", and also prevents matching the domain
# part of an email address like "user@example.com" (the "@" before the
# domain would trigger the lookbehind and skip the match).
_BARE_DOMAIN: Final[Pattern[str]] = re.compile(
    r"(?<![\w@])"
    r"(?:www\.)?"
    r"([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)"
    r"\.(" + "|".join(_COMMON_TLDS) + r")"
    r"(?:/[^\s<>\"'`{}|\\^\[\]\"']*)?"
    r"(?=[\s,;)>\]'\"!?.]|$)",
    re.IGNORECASE,
)


# Characters to strip from the end of a captured URL — common
# sentence punctuation that should NOT be part of the URL itself.
_TRAILING_PUNCT: Final[str] = ".,;:!?)]}>'\""


class RegexLinkExtractor:
    """LinkExtractor implementation backed by regex.

    Pure — no I/O. Never raises on input: garbage in, empty out.
    """

    def extract(self, text: str, *, source: str) -> list[RawLink]:
        if not text:
            return []

        results: list[RawLink] = []
        seen_normalized: set[str] = set()

        # Pass 1: scheme-explicit URLs.
        # Track the character spans already covered so that Pass 2 does
        # not produce a bare-domain match that is a substring of a
        # scheme-explicit match already captured (e.g. the "python.org/3"
        # tail of "https://docs.python.org/3" must not be re-captured).
        scheme_spans: list[tuple[int, int]] = []

        for match in _SCHEME_URL.finditer(text):
            raw = match.group(0).rstrip(_TRAILING_PUNCT)
            norm = normalize_url(raw)
            if not norm or norm in seen_normalized:
                continue
            seen_normalized.add(norm)
            # Record the span of the *stripped* raw string
            span_start = match.start()
            span_end = span_start + len(raw)
            scheme_spans.append((span_start, span_end))
            results.append(
                RawLink(
                    url=raw,
                    normalized_url=norm,
                    source=source,
                    position_ms=None,
                )
            )

        # Pass 2: bare domains (only when the normalized form is
        # not already captured — avoids double-counting a URL
        # matched by pass 1). Skip any bare-domain match whose span
        # overlaps with a scheme-explicit match span.
        for match in _BARE_DOMAIN.finditer(text):
            # Skip if this match falls inside a scheme-explicit span
            m_start, m_end = match.start(), match.end()
            if any(s <= m_start and m_end <= e for s, e in scheme_spans):
                continue
            raw = match.group(0).rstrip(_TRAILING_PUNCT)
            if not raw:
                continue
            candidate = "https://" + raw
            norm = normalize_url(candidate)
            if not norm or norm in seen_normalized:
                continue
            seen_normalized.add(norm)
            results.append(
                RawLink(
                    url=raw,
                    normalized_url=norm,
                    source=source,
                    position_ms=None,
                )
            )

        return results
