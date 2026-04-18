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
# Negative lookbehind (?<!\w) prevents matching inside words like
# "version1.0" or "file.txt". Negative lookahead at end anchors on
# a separator.
_BARE_DOMAIN: Final[Pattern[str]] = re.compile(
    r"(?<!\w)"
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

        # Pass 1: scheme-explicit URLs
        for match in _SCHEME_URL.finditer(text):
            raw = match.group(0).rstrip(_TRAILING_PUNCT)
            norm = normalize_url(raw)
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

        # Pass 2: bare domains (only when the normalized form is
        # not already captured — avoids double-counting a URL
        # matched by pass 1).
        for match in _BARE_DOMAIN.finditer(text):
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
