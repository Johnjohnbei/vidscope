"""Pure-Python metrics computed from VideoStats time-series data.

This module is domain-pure: stdlib only, no third-party runtime imports,
no project imports from outer layers. Every function operates on plain
Python types so they can be used anywhere in the codebase without
pulling in I/O, databases, or external libraries.

Design rules (from M009-CONTEXT.md)
-------------------------------------
- D-01: ``captured_at`` is always UTC-aware, truncated to the second.
- D-02: ``repost_count`` uses the yt-dlp field name (NOT ``share_count``).
- D-03: ``None`` is NOT ``0``. A missing counter must never be coerced to
  zero — the caller must check ``is None`` explicitly.
- D-04: Velocity is expressed in views/hour (float). ``None`` when there
  are fewer than 2 snapshots or when ``view_count`` is unavailable.
- D-05: Engagement rate is views-normalised. ``None`` when ``view_count``
  is 0 or ``None`` (never divide by zero).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vidscope.domain.entities import VideoStats

__all__ = ["engagement_rate", "views_velocity_24h"]


def views_velocity_24h(history: list[VideoStats]) -> float | None:
    """Return the average views gained per hour over the last 24 h window.

    The function selects the earliest and latest snapshot within the
    24-hour window ending at the most-recent snapshot's ``captured_at``
    and computes ``delta_views / delta_hours``.

    Returns ``None`` when:

    - ``history`` has fewer than 2 entries.
    - Any relevant snapshot has ``view_count is None``.
    - The two chosen snapshots have the same ``captured_at`` (delta = 0 s).

    Parameters
    ----------
    history:
        List of :class:`~vidscope.domain.entities.VideoStats` snapshots,
        ordered by ``captured_at`` ascending. The function sorts them
        internally so callers need not guarantee order.

    Returns
    -------
    float | None
        Views gained per hour, or ``None`` when the metric cannot be
        computed (D-04).
    """
    if len(history) < 2:
        return None

    sorted_history = sorted(history, key=lambda s: s.captured_at)
    latest = sorted_history[-1]

    # 24-hour window ending at latest snapshot
    from datetime import timedelta

    window_start = latest.captured_at - timedelta(hours=24)
    window = [s for s in sorted_history if s.captured_at >= window_start]

    if len(window) < 2:
        return None

    oldest = window[0]
    newest = window[-1]

    if oldest.view_count is None or newest.view_count is None:
        return None

    delta_seconds = (newest.captured_at - oldest.captured_at).total_seconds()
    if delta_seconds <= 0:
        return None

    delta_views = newest.view_count - oldest.view_count
    delta_hours = delta_seconds / 3600.0
    return delta_views / delta_hours


def engagement_rate(stats: VideoStats) -> float | None:
    """Return the engagement rate for a single snapshot.

    Engagement rate = (likes + comments + reposts + saves) / views.

    Returns ``None`` when:

    - ``view_count`` is ``None`` or ``0`` (D-03, D-05 — never divide by zero).
    - All engagement counters are ``None`` (no data to compute from).

    Parameters
    ----------
    stats:
        A single :class:`~vidscope.domain.entities.VideoStats` snapshot.

    Returns
    -------
    float | None
        A value in [0, ∞) representing the ratio of engagement actions
        to views. ``None`` when computation is impossible.
    """
    if stats.view_count is None or stats.view_count <= 0:
        return None

    # Treat None counters as 0 for the numerator (absent ≠ negative)
    likes = stats.like_count or 0
    comments = stats.comment_count or 0
    reposts = stats.repost_count or 0
    saves = stats.save_count or 0

    numerator = likes + comments + reposts + saves
    return numerator / stats.view_count
