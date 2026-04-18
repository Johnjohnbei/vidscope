"""Pure-Python URL normalization — stdlib only.

Used by :class:`RegexLinkExtractor` to produce the ``normalized_url``
deduplication key from a raw captured URL. Also importable directly
for other adapters (M008 OCR) that need the same dedup shape.

Normalization rules (per M007 CONTEXT §D-04 and RESEARCH §"URL
normalizer"):

1. Lowercase the scheme and host (path case is preserved — some URLs
   use case-sensitive paths).
2. Strip the fragment (``#anchor``).
3. Drop every query parameter whose key starts with ``utm_``
   (case-insensitive) — these are tracking params irrelevant for
   deduplication.
4. Sort the remaining query parameters alphabetically by key.
5. Strip the trailing slash from the path (``/`` at the very end).
6. When the input has no scheme (``bit.ly/abc``), prepend ``https://``
   so the output is always a well-formed absolute URL.

The function is idempotent: ``normalize_url(normalize_url(x)) ==
normalize_url(x)`` for every input.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

__all__ = ["normalize_url"]


def normalize_url(url: str) -> str:
    """Return the canonical normalized form of ``url``.

    See module docstring for the full rule list. Returns the original
    ``url`` unchanged when parsing fails (empty string, malformed
    input) — never raises.
    """
    raw = (url or "").strip()
    if not raw:
        return ""

    # Ensure a scheme is present so urlparse populates netloc
    # correctly. "bit.ly/abc" has no scheme → parsed.netloc == ''
    # and the whole string is treated as the path. We fix that by
    # prepending https:// when there is no "://" in the string.
    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Strip trailing slash from path.
    # Rule: a bare "/" path with no query string is collapsed to ""
    # (so "https://example.com/" → "https://example.com").
    # When a query string is present, the "/" is kept to preserve the
    # canonical form "https://example.com/?..." (the "?" already
    # separates path from query, so stripping "/" would be ambiguous).
    path = parsed.path
    query_after_filter_will_exist = bool(
        [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
         if not k.lower().startswith("utm_")]
    )
    if path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")
    elif path == "/" and not query_after_filter_will_exist:
        path = ""

    # Filter utm_* (case-insensitive) then sort by key.
    qs_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [
        (k, v) for k, v in qs_pairs if not k.lower().startswith("utm_")
    ]
    sorted_qs = sorted(filtered, key=lambda kv: kv[0])
    query = urlencode(sorted_qs)

    # Fragment is always discarded.
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))
