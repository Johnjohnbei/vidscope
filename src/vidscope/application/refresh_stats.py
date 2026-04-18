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
from datetime import timedelta

from vidscope.domain import DomainError, VideoId, VideoStats
from vidscope.pipeline.stages.stats_stage import StatsStage
from vidscope.ports import Clock, PipelineContext, UnitOfWorkFactory

__all__ = [
    "RefreshStatsBatchResult",
    "RefreshStatsForWatchlistResult",
    "RefreshStatsForWatchlistUseCase",
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
            except Exception as exc:
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
            except Exception as exc:
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


# ---------------------------------------------------------------------------
# S03 — RefreshStatsForWatchlistUseCase
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RefreshStatsForWatchlistResult:
    """Outcome of refresh-stats-for-watchlist (M009/S03).

    Counts how many accounts were examined, how many videos received a
    fresh stats probe, and how many failed. ``errors`` contains one entry
    per account-level or video-level failure; the batch always runs to
    completion regardless of individual failures (per-account + per-video
    isolation, matching T-ISO-01 and T-ISO-02).
    """

    accounts_checked: int
    videos_checked: int
    stats_refreshed: int
    failed: int
    errors: tuple[str, ...]


class RefreshStatsForWatchlistUseCase:
    """Refresh video_stats for every video of every watched account.

    For each WatchedAccount:
    1. List its videos via ``uow.videos.list_by_author(platform, handle)``.
    2. For each video, call ``refresh_stats.execute_one(video.id)``.

    Per-account + per-video error isolation (T-ISO-01, T-ISO-02):
    - A failed ``list_by_author`` for one account is recorded in ``errors``
      and the next account is processed normally.
    - A failed ``execute_one`` for one video increments ``failed`` and the
      next video is processed normally.

    The use case does NOT call ``RefreshWatchlistUseCase`` — orchestration
    is the CLI's responsibility (M009/S03 design decision).

    NO INFRASTRUCTURE IMPORT (import-linter application-has-no-adapters).
    """

    def __init__(
        self,
        *,
        refresh_stats: RefreshStatsUseCase,
        unit_of_work_factory: UnitOfWorkFactory,
    ) -> None:
        self._refresh = refresh_stats
        self._uow = unit_of_work_factory

    def execute(self) -> RefreshStatsForWatchlistResult:
        """Iterate watched accounts and refresh stats for all their videos.

        Opens one read-only UoW transaction to collect accounts + build
        the work list, then calls ``execute_one`` outside the read scope
        so each probe runs in its own transaction (one commit per video).
        """
        errors: list[str] = []
        work: list[tuple[str, VideoId]] = []  # (label, video_id)
        accounts_checked = 0

        with self._uow() as uow:
            accounts = uow.watch_accounts.list_all()
            accounts_checked = len(accounts)
            for account in accounts:
                label_prefix = f"{account.platform.value}/{account.handle}"
                try:
                    videos = uow.videos.list_by_author(
                        account.platform, account.handle, limit=1000
                    )
                except Exception as exc:
                    errors.append(f"list videos failed for {label_prefix}: {exc}")
                    continue
                for v in videos:
                    if v.id is None:
                        continue
                    label = f"{label_prefix}#{int(v.id)}"
                    work.append((label, v.id))

        # Execute refresh per video OUTSIDE the read scope so each probe
        # runs in its own transaction (avoids holding the DB lock).
        videos_checked = 0
        stats_refreshed = 0
        failed = 0

        for label, vid in work:
            videos_checked += 1
            try:
                res = self._refresh.execute_one(vid)
            except Exception as exc:
                failed += 1
                errors.append(f"{label}: unexpected error: {exc}")
                continue
            if res.success:
                stats_refreshed += 1
            else:
                failed += 1
                errors.append(f"{label}: {res.message}")

        return RefreshStatsForWatchlistResult(
            accounts_checked=accounts_checked,
            videos_checked=videos_checked,
            stats_refreshed=stats_refreshed,
            failed=failed,
            errors=tuple(errors),
        )
