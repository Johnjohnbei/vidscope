"""StatsProbe port — metadata-only probe for video engagement counters.

The probe fetches live engagement counters (views, likes, reposts,
comments, saves) from the platform without downloading the media.
Callers receive a non-persisted :class:`~vidscope.domain.entities.VideoStats`
that the ``StatsStage`` (S02) will persist via ``UnitOfWork.video_stats``.

Design contract
---------------
- ``probe_stats`` NEVER raises. Any failure returns ``None`` so the
  caller can decide whether to skip or retry without a try/except block.
- The returned ``VideoStats`` has ``id=None`` and ``created_at=None``
  (not yet persisted).
- ``captured_at`` is always UTC-aware and truncated to the second (D-01).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from vidscope.domain import VideoStats

__all__ = ["StatsProbe"]


@runtime_checkable
class StatsProbe(Protocol):
    """Protocol for a metadata-only stats probe.

    Implementations wrap platform-specific APIs (yt-dlp ``extract_info``
    with ``download=False``) to fetch engagement counters without storing
    any media locally.
    """

    def probe_stats(self, url: str) -> VideoStats | None:
        """Fetch engagement counters for ``url`` without downloading media.

        Parameters
        ----------
        url:
            Public video URL on any supported platform.

        Returns
        -------
        VideoStats | None
            A non-persisted snapshot with ``id=None``, or ``None`` if the
            probe could not fetch data (network error, private video, etc.).
        """
        ...
