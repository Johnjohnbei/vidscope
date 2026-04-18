"""YtdlpStatsProbe — yt-dlp implementation of the StatsProbe port.

Wraps ``yt_dlp.YoutubeDL.extract_info(download=False)`` to fetch
engagement counters (views, likes, reposts, comments, saves) for a URL
without downloading any media.

Design notes
------------

- **Probe-never-raises (T-PROBE-01).** Every exception from yt-dlp is
  caught and returns ``None``. Callers must not handle exceptions — they
  handle ``None``.
- **_int_or_none helper (T-DATA-01).** Every counter field extracted from
  the yt-dlp info dict is passed through ``_int_or_none``. Any non-int
  value (str, float, bool, dict, …) becomes ``None`` rather than being
  stored as-is. This prevents type-confusion attacks from malicious
  platform responses.
- **captured_at truncated to second (D-01).** ``datetime.now(UTC)``
  is truncated to ``microsecond=0`` so the UNIQUE constraint on
  ``(video_id, captured_at)`` at second resolution works correctly.
- **repost_count uses yt-dlp field name (D-02).** The yt-dlp info dict
  exposes ``repost_count`` directly; we do NOT rename it to
  ``share_count``.
- **video_id is None on the returned entity.** The probe does not know
  the DB primary key — that is resolved by the StatsStage (S02) which
  calls ``uow.videos.get_by_platform_id`` before calling ``append``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yt_dlp

from vidscope.domain import VideoId, VideoStats

__all__ = ["YtdlpStatsProbe"]

# Sentinel VideoId used when the probe returns a stats object without
# a known DB id. The StatsStage (S02) replaces this with the real id.
_UNRESOLVED_VIDEO_ID = VideoId(0)


def _int_or_none(value: Any) -> int | None:
    """Return ``value`` cast to ``int``, or ``None`` if not safely castable.

    Accepts ``int`` and ``float`` (platform APIs sometimes return floats
    for count fields). Any other type returns ``None`` (T-DATA-01).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        # bool is a subclass of int in Python — exclude it explicitly
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


class YtdlpStatsProbe:
    """StatsProbe port implementation backed by yt-dlp.

    Parameters
    ----------
    cookies_file:
        Optional path to a Netscape cookies file. When provided, yt-dlp
        sends the cookies with every request so gated platforms (Instagram,
        age-gated YouTube) can be probed. Mirrors the same parameter on
        :class:`~vidscope.adapters.ytdlp.downloader.YtdlpDownloader`.
    """

    def __init__(self, cookies_file: Path | None = None) -> None:
        self._cookies_file = cookies_file

    def probe_stats(self, url: str) -> VideoStats | None:
        """Fetch engagement counters for ``url`` without downloading media.

        Returns a non-persisted :class:`VideoStats` with ``id=None`` and
        ``video_id`` set to the sentinel ``VideoId(0)`` (the StatsStage
        replaces it with the real DB id before persisting).

        Returns ``None`` on any failure — network errors, private videos,
        unsupported extractors, unexpected yt-dlp crashes. Never raises
        (T-PROBE-01).

        Parameters
        ----------
        url:
            Public video URL on any supported platform.
        """
        if not url or not url.strip():
            return None

        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "skip_download": True,
            "ignoreerrors": False,
        }
        if self._cookies_file is not None:
            options["cookiefile"] = str(self._cookies_file)

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:
            # T-PROBE-01: probe-never-raises
            return None

        if not isinstance(info, dict):
            return None

        # D-01: captured_at is UTC-aware and truncated to the second.
        captured_at = datetime.now(UTC).replace(microsecond=0)

        return VideoStats(
            video_id=_UNRESOLVED_VIDEO_ID,
            captured_at=captured_at,
            view_count=_int_or_none(info.get("view_count")),
            like_count=_int_or_none(info.get("like_count")),
            repost_count=_int_or_none(info.get("repost_count")),  # D-02
            comment_count=_int_or_none(info.get("comment_count")),
            save_count=_int_or_none(info.get("save_count")),
        )
