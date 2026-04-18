"""RefreshStatsUseCase — orchestrate StatsStage for one or many videos.

The use case is self-contained: it takes a StatsStage + UnitOfWorkFactory
+ Clock and runs the stage inside a fresh transaction per video. Per-
video error isolation matches M003's RefreshWatchlistUseCase pattern:
one broken video doesn't stop the batch.

NO INFRASTRUCTURE IMPORT (import-linter application-has-no-adapters).
The caller in cli/commands/stats.py builds a container and wires
this use case with its dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from vidscope.domain import DomainError, VideoId, VideoStats
from vidscope.pipeline.stages.stats_stage import StatsStage
from vidscope.ports import Clock, PipelineContext, UnitOfWorkFactory

__all__ = [
    "RefreshStatsBatchResult",
    "RefreshStatsResult",
    "RefreshStatsUseCase",
]

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RefreshStatsResult:
    """Outcome of a single refresh-stats invocation."""

    success: bool
    video_id: int | None
    stats: VideoStats | None
    message: str


@dataclass(frozen=True, slots=True)
class RefreshStatsBatchResult:
    """Outcome of a batch refresh-stats invocation."""

    total: int
    refreshed: int
    failed: int
    per_video: tuple[RefreshStatsResult, ...]


class RefreshStatsUseCase:
    """Refresh video_stats for a single video or a batch.

    Dependencies injected via constructor (hexagonal architecture). No
    direct filesystem or network access — everything goes through
    StatsStage / UnitOfWork / Clock.
    """

    def __init__(
        self,
        *,
        stats_stage: StatsStage,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
    ) -> None:
        self._stage = stats_stage
        self._uow = unit_of_work_factory
        self._clock = clock

    def execute_one(self, video_id: VideoId) -> RefreshStatsResult:
        """Refresh stats for one video. Returns success/failure + message.

        Opens a fresh UoW transaction, looks up the video, runs StatsStage,
        and reads back the latest stats row for the result DTO. A missing
        video or a failed probe returns ``success=False`` without raising.
        """
        with self._uow() as uow:
            video = uow.videos.get(video_id)
            if video is None:
                return RefreshStatsResult(
                    success=False,
                    video_id=int(video_id),
                    stats=None,
                    message=f"video not found: id={int(video_id)}",
                )

            ctx = PipelineContext(
                source_url=video.url,
                video_id=video_id,
            )

            try:
                result = self._stage.execute(ctx, uow)
            except DomainError as exc:
                return RefreshStatsResult(
                    success=False,
                    video_id=int(video_id),
                    stats=None,
                    message=str(exc),
                )
            except Exception as exc:  # noqa: BLE001 — standalone stage, not in runner
                return RefreshStatsResult(
                    success=False,
                    video_id=int(video_id),
                    stats=None,
                    message=f"unexpected error: {exc}",
                )

            # StageResult.skipped=True signals a soft failure (probe returned
            # nothing but no exception was raised — defensive path).
            if result.skipped:
                return RefreshStatsResult(
                    success=False,
                    video_id=int(video_id),
                    stats=None,
                    message=result.message or "stats stage returned no data",
                )

            latest = uow.video_stats.latest_for_video(video_id)
            return RefreshStatsResult(
                success=True,
                video_id=int(video_id),
                stats=latest,
                message=result.message or "stats refreshed",
            )

    def execute_all(
        self,
        *,
        since: timedelta | None = None,
        limit: int = 1000,
    ) -> RefreshStatsBatchResult:
        """Refresh stats for up to ``limit`` videos. Per-video error isolation.

        If ``since`` is provided, only videos whose ``created_at`` falls within
        the given window from now are refreshed. Otherwise all videos up to
        ``limit`` are refreshed.

        Parameters
        ----------
        since:
            Optional time window relative to now. E.g. ``timedelta(days=7)``
            refreshes only videos ingested in the last 7 days.
        limit:
            Maximum number of videos to process. Must be >= 1 (T-INPUT-01).

        Raises
        ------
        ValueError
            When ``limit < 1`` (T-INPUT-01 double validation — CLI also enforces
            via Typer ``min=1``, but the use case validates independently).
        """
        if limit < 1:
            raise ValueError(f"limit must be >= 1 (T-INPUT-01), got {limit}")

        # Collect video list in a read-only UoW scope. Using a separate
        # transaction here avoids holding the DB lock across all probe calls.
        with self._uow() as read_uow:
            videos = read_uow.videos.list_recent(limit=limit)

        # Apply the since filter if provided
        if since is not None:
            cutoff = self._clock.now() - since
            videos = [
                v for v in videos
                if v.created_at is not None and v.created_at >= cutoff
            ]

        per_video: list[RefreshStatsResult] = []
        refreshed = 0
        failed = 0

        for video in videos:
            if video.id is None:
                _logger.warning("refresh_stats: skipping video with no id: %s", video)
                continue
            try:
                res = self.execute_one(video.id)
            except Exception as exc:  # noqa: BLE001 — batch isolation
                res = RefreshStatsResult(
                    success=False,
                    video_id=int(video.id),
                    stats=None,
                    message=f"unexpected error: {exc}",
                )
            per_video.append(res)
            if res.success:
                refreshed += 1
            else:
                failed += 1

        return RefreshStatsBatchResult(
            total=len(per_video),
            refreshed=refreshed,
            failed=failed,
            per_video=tuple(per_video),
        )
