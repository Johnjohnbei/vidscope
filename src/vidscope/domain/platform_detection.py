"""URL → :class:`Platform` detection.

Pure-Python helper that inspects a URL and returns the matching
:class:`Platform` enum value. Lives in the domain layer because the
platform set is a business concept, not an adapter detail — the same
detection logic runs before we hand a URL to yt-dlp and again when
we format display output in the CLI.

Zero third-party imports (only :mod:`urllib.parse` from the stdlib).
Zero I/O. Runs in microseconds.

Design notes
------------

- **Host suffix match.** We compare the parsed URL host against a
  suffix-indexed mapping so ``m.youtube.com`` and ``music.youtube.com``
  both resolve to YouTube without each needing its own entry.

- **Reject non-http(s) upfront.** ``javascript:``, ``file://``, bare
  words, and empty strings all raise :class:`IngestError` before any
  host inspection. The pipeline never calls yt-dlp with a clearly
  broken URL.

- **Case-insensitive host comparison.** Hosts are lowercased before
  match because RFC says hosts are case-insensitive and users type
  ``YouTube.com`` sometimes.
"""

from __future__ import annotations

from typing import Final
from urllib.parse import urlparse

from vidscope.domain.errors import IngestError
from vidscope.domain.values import Platform

__all__ = ["detect_platform"]


# Map of host suffix → Platform. Listed in priority order
# (Instagram → TikTok → YouTube per D027) for documentation
# clarity, even though the loop checks all entries — order does not
# affect resolution because each suffix is unique.
_HOST_SUFFIXES: Final[tuple[tuple[str, Platform], ...]] = (
    # Instagram family — primary platform
    ("instagram.com", Platform.INSTAGRAM),
    # TikTok family — secondary platform
    ("tiktok.com", Platform.TIKTOK),
    # YouTube family — tertiary platform
    ("youtube.com", Platform.YOUTUBE),
    ("youtu.be", Platform.YOUTUBE),
)


def detect_platform(url: str) -> Platform:
    """Return the :class:`Platform` matching ``url``.

    Parameters
    ----------
    url:
        A full http(s):// URL. Leading/trailing whitespace is
        stripped before parsing.

    Raises
    ------
    IngestError
        If the URL is empty, malformed, not http/https, or points at
        a host we do not support. The error carries ``retryable=False``
        because URL issues never self-heal.
    """
    if url is None:
        raise IngestError("url is None", retryable=False)

    cleaned = url.strip()
    if not cleaned:
        raise IngestError("url is empty", retryable=False)

    try:
        parsed = urlparse(cleaned)
    except ValueError as exc:
        raise IngestError(
            f"url is not parseable: {cleaned!r}", retryable=False, cause=exc
        ) from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise IngestError(
            f"url must be http or https, got scheme {scheme!r} in {cleaned!r}",
            retryable=False,
        )

    host = (parsed.hostname or "").lower()
    if not host:
        raise IngestError(
            f"url has no host component: {cleaned!r}", retryable=False
        )

    for suffix, platform in _HOST_SUFFIXES:
        # Match exact host ("youtube.com") or any subdomain
        # ("m.youtube.com", "www.youtube.com", "music.youtube.com").
        if host == suffix or host.endswith(f".{suffix}"):
            return platform

    raise IngestError(
        f"unsupported platform URL: {cleaned!r}. "
        f"Supported: {', '.join(p.value for p in Platform)}",
        retryable=False,
    )
