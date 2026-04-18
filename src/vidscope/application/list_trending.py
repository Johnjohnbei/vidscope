"""ListTrendingUseCase — rank videos by views_velocity_24h on a time window.

Scalability (D-04): the candidate set is reduced via a SQL GROUP BY +
ORDER BY delta DESC + LIMIT query in the repository. Only that subset
loads its full history to compute the exact metrics (metrics.py pure
domain). No full table scan in Python.

NO INFRASTRUCTURE IMPORT (application-has-no-adapters contract).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from vidscope.domain import Platform, VideoId
from vidscope.domain.metrics import engagement_rate, views_velocity_24h
from vidscope.ports import UnitOfWorkFactory
from vidscope.ports.clock import Clock

if TYPE_CHECKING:
    pass

__all__ = ["ListTrendingUseCase", "TrendingEntry"]


@dataclass(frozen=True, slots=True)
class TrendingEntry:
    """One row in the vidscope trending output."""

    video_id: int
    platform: Platform
    title: str | None
    views_velocity_24h: float   # views per hour (D-04)
    engagement_rate: float | None   # 0..1 or None when view_count==0/None
    last_captured_at: datetime
    latest_view_count: int | None
    latest_like_count: int | None


class ListTrendingUseCase:
    """Rank videos by views_velocity_24h on the given time window.

    Scalability (D-04): the repository query uses SQL-level GROUP BY +
    HAVING count >= 2 + ORDER BY delta DESC + LIMIT to produce a small
    candidate set. Python then computes exact metrics on that subset.

    Parameters to execute():
    - since (timedelta): mandatory window. The caller converts the CLI
      --since "7d" string to a timedelta before calling here.
    - platform: optional filter.
    - min_velocity: floor on views_velocity_24h (default 0.0).
    - limit: max results (default 20).
    """

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
    ) -> None:
        self._uow = unit_of_work_factory
        self._clock = clock

    def execute(
        self,
        *,
        since: timedelta,
        platform: Platform | None = None,
        min_velocity: float = 0.0,
        limit: int = 20,
    ) -> list[TrendingEntry]:
        """Return up to ``limit`` trending videos ranked by views_velocity_24h.

        Parameters
        ----------
        since:
            Time window — only stats rows captured within this window
            are included. Mandatory (D-04: no silent defaults).
        platform:
            Optional filter. When provided, only videos on that platform
            appear in results.
        min_velocity:
            Minimum views_velocity_24h threshold. Videos below this are
            excluded (default 0.0 = include all positive velocities).
        limit:
            Maximum number of results (default 20, must be >= 1).

        Returns
        -------
        list[TrendingEntry]
            Sorted by views_velocity_24h descending. May be shorter than
            ``limit`` when fewer videos qualify.

        Raises
        ------
        ValueError
            When ``limit < 1`` or ``since.total_seconds() <= 0``.
        """
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if since.total_seconds() <= 0:
            raise ValueError("since must be positive")

        cutoff = self._clock.now() - since

        with self._uow() as uow:
            # SQL-level candidate shortlist: fetch more than limit so the
            # min_velocity filter in Python can still return limit results.
            candidate_ids = uow.video_stats.rank_candidates_by_delta(
                since=cutoff,
                platform=platform,
                limit=max(limit * 5, 100),
            )

            entries: list[TrendingEntry] = []
            for vid in candidate_ids:
                history = uow.video_stats.list_for_video(vid, limit=1000)
                if len(history) < 2:
                    continue
                velocity = views_velocity_24h(history)
                if velocity is None or velocity < min_velocity:
                    continue

                latest = history[-1]
                video = uow.videos.get(vid)
                if video is None:
                    continue
                entries.append(
                    TrendingEntry(
                        video_id=int(vid),
                        platform=video.platform,
                        title=video.title,
                        views_velocity_24h=velocity,
                        engagement_rate=engagement_rate(latest),
                        last_captured_at=latest.captured_at,
                        latest_view_count=latest.view_count,
                        latest_like_count=latest.like_count,
                    )
                )

        entries.sort(key=lambda e: e.views_velocity_24h, reverse=True)
        return entries[:limit]
