"""Composite Downloader adapters.

:class:`FallbackDownloader` wraps a primary and a fallback
:class:`~vidscope.ports.Downloader`. On ``download()``, it tries the
primary first; if the primary raises a non-retryable :class:`IngestError`
whose message matches one of the configured fallback markers, it
transparently retries with the fallback. All other methods delegate to the
primary only.

Typical wiring (container)::

    downloader = FallbackDownloader(
        primary=YtdlpDownloader(cookies_file=...),
        fallback=InstaLoaderDownloader(cookies_file=...),
        fallback_on=("no video formats found",),
    )
"""

from __future__ import annotations

from typing import Final

from vidscope.domain import IngestError
from vidscope.ports import ChannelEntry, Downloader, IngestOutcome, ProbeResult

__all__ = ["FallbackDownloader"]


class FallbackDownloader:
    """Tries *primary*; falls back to *fallback* on specific error messages.

    Parameters
    ----------
    primary:
        The first :class:`Downloader` to try. Also handles
        ``list_channel_videos`` and ``probe``.
    fallback:
        Alternative downloader used when *primary* raises a
        non-retryable :class:`IngestError` matching any of
        *fallback_on*.
    fallback_on:
        Substrings (case-insensitive) that trigger a fallback.
        Default: ``("no video formats found",)``.
    """

    _DEFAULT_MARKERS: Final[tuple[str, ...]] = ("no video formats found",)

    def __init__(
        self,
        primary: Downloader,
        fallback: Downloader,
        *,
        fallback_on: tuple[str, ...] = _DEFAULT_MARKERS,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._markers = tuple(m.lower() for m in fallback_on)

    # ------------------------------------------------------------------
    # Downloader protocol
    # ------------------------------------------------------------------

    def download(self, url: str, destination_dir: str) -> IngestOutcome:
        try:
            return self._primary.download(url, destination_dir)
        except IngestError as exc:
            if not exc.retryable and any(m in str(exc).lower() for m in self._markers):
                return self._fallback.download(url, destination_dir)
            raise

    def list_channel_videos(
        self, url: str, *, limit: int = 10
    ) -> list[ChannelEntry]:
        return self._primary.list_channel_videos(url, limit=limit)

    def probe(self, url: str) -> ProbeResult:
        return self._primary.probe(url)
