"""Tests for :class:`GetStatusUseCase`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.application.get_status import GetStatusResult, GetStatusUseCase
from vidscope.domain import (
    PipelineRun,
    Platform,
    PlatformId,
    RunStatus,
    StageName,
    Video,
)

UTC_NOW = datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC)


class TestGetStatusUseCase:
    def test_empty_db_returns_zero_counts(
        self, uow_factory  # type: ignore[no-untyped-def]
    ) -> None:
        uc = GetStatusUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute()

        assert isinstance(result, GetStatusResult)
        assert result.runs == ()
        assert result.total_runs == 0
        assert result.total_videos == 0

    def test_populated_db_returns_recent_runs(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        # Seed a video and three runs
        with SqliteUnitOfWork(engine) as uow:
            video = uow.videos.upsert_by_platform_id(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("getst"),
                    url="https://example.com/getst",
                )
            )
            for i, status in enumerate(
                [RunStatus.OK, RunStatus.FAILED, RunStatus.PENDING]
            ):
                uow.pipeline_runs.add(
                    PipelineRun(
                        phase=StageName.INGEST,
                        status=status,
                        started_at=UTC_NOW + timedelta(minutes=i),
                        video_id=video.id,
                    )
                )

        uc = GetStatusUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(limit=10)

        assert result.total_runs == 3
        assert result.total_videos == 1
        assert len(result.runs) == 3
        # Newest-first ordering
        assert (
            result.runs[0].started_at
            >= result.runs[1].started_at
            >= result.runs[2].started_at
        )

    def test_limit_is_clamped(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            for i in range(5):
                uow.pipeline_runs.add(
                    PipelineRun(
                        phase=StageName.INGEST,
                        status=RunStatus.OK,
                        started_at=UTC_NOW + timedelta(minutes=i),
                    )
                )

        uc = GetStatusUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(limit=2)

        assert len(result.runs) == 2
        assert result.total_runs == 5  # Counts reflect DB, not the limit

    def test_negative_limit_is_clamped_to_one(
        self, uow_factory  # type: ignore[no-untyped-def]
    ) -> None:
        uc = GetStatusUseCase(unit_of_work_factory=uow_factory)
        result = uc.execute(limit=-5)
        # Empty DB: result.runs is still empty but no exception
        assert result.runs == ()
