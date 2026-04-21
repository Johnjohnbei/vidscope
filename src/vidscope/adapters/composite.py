"""Composite Downloader adapters.

:class:`FallbackDownloader` wraps a primary and a fallback
:class:`~vidscope.ports.Downloader`. On ``download()``, it tries the
primary first; if the primary raises a non-retryable :class:`IngestError`
whose message matches one of the configured fallback markers, it
transparently retries with the fallback. All other methods delegate to the
primary only.

:class:`PlatformRoutingDownloader` routes Instagram URLs to
:class:`~vidscope.adapters.instaloader.InstaLoaderDownloader` first so
that image slides in carousels are captured before yt-dlp has a chance to
grab only the video side of a mixed post. Pure Reels (no downloadable
images) fall back to yt-dlp. All other platforms go to yt-dlp directly.

Typical wiring (container)::

    downloader = PlatformRoutingDownloader(
        ytdlp=YtdlpDownloader(cookies_file=...),
        instaloader=InstaLoaderDownloader(cookies_file=...),
    )
"""

from __future__ import annotations

from typing import Final

from vidscope.domain import IngestError
from vidscope.ports import ChannelEntry, Downloader, IngestOutcome, ProbeResult

__all__ = ["FallbackDownloader", "PlatformRoutingDownloader"]


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


class PlatformRoutingDownloader:
    """Routes Instagram URLs to InstaLoaderDownloader first, yt-dlp second.

    Instagram carousels that contain at least one video slide are
    successfully downloaded by yt-dlp as a single video, silently
    discarding all image slides. OCR then runs on video frames and
    finds no text. By trying InstaLoaderDownloader first we capture
    every image slide, which is where carousel text lives.

    Routing rules
    -------------
    - Instagram URL → InstaLoaderDownloader first.
      If it raises a non-retryable IngestError whose message matches
      ``_INSTAGRAM_FALLBACK_MARKERS`` ("no downloadable images found"),
      fall back to YtdlpDownloader (handles pure Reels).
    - Any other platform URL → YtdlpDownloader directly.

    ``list_channel_videos`` and ``probe`` always delegate to yt-dlp
    regardless of platform (InstaLoaderDownloader does not implement them).
    """

    _INSTAGRAM_FALLBACK_MARKERS: Final[tuple[str, ...]] = (
        "no downloadable images found",
    )

    def __init__(self, *, ytdlp: Downloader, instaloader: Downloader) -> None:
        self._ytdlp = ytdlp
        self._instaloader = instaloader

    def download(self, url: str, destination_dir: str) -> IngestOutcome:
        if _is_instagram_url(url):
            try:
                return self._instaloader.download(url, destination_dir)
            except IngestError as exc:
                if not exc.retryable and any(
                    m in str(exc).lower() for m in self._INSTAGRAM_FALLBACK_MARKERS
                ):
                    return self._ytdlp.download(url, destination_dir)
                raise
        return self._ytdlp.download(url, destination_dir)

    def list_channel_videos(
        self, url: str, *, limit: int = 10
    ) -> list[ChannelEntry]:
        return self._ytdlp.list_channel_videos(url, limit=limit)

    def probe(self, url: str) -> ProbeResult:
        return self._ytdlp.probe(url)


def _is_instagram_url(url: str) -> bool:
    return "instagram.com" in url.lower()
