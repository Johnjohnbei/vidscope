"""Tests for :class:`PipelineRunRepositorySQLite`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    PipelineRun,
    Platform,
    PlatformId,
    RunStatus,
    StageName,
    Video,
    VideoId,
)

UTC_NOW = datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC)


def _seed_video(engine: Engine, platform_id: str = "seed") -> VideoId:
    with SqliteUnitOfWork(engine) as uow:
        v = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId(platform_id),
                url=f"https://example.com/{platform_id}",
            )
        )
        assert v.id is not None
        return v.id


class TestPipelineRunRepository:
    def test_add_and_read_back(self, engine: Engine) -> None:
        video_id = _seed_video(engine)

        with SqliteUnitOfWork(engine) as uow:
            stored = uow.pipeline_runs.add(
                PipelineRun(
                    phase=StageName.INGEST,
                    status=RunStatus.PENDING,
                    started_at=UTC_NOW,
                    video_id=video_id,
                    source_url="https://example.com/seed",
                )
            )
            assert stored.id is not None
            assert stored.status is RunStatus.PENDING

        with SqliteUnitOfWork(engine) as uow:
            latest = uow.pipeline_runs.latest_for_video(video_id)
            assert latest is not None
            assert latest.phase is StageName.INGEST
            assert latest.status is RunStatus.PENDING
            assert latest.source_url == "https://example.com/seed"
            assert latest.started_at.tzinfo is not None

    def test_update_status_to_ok(self, engine: Engine) -> None:
        video_id = _seed_video(engine, "ok1")
        with SqliteUnitOfWork(engine) as uow:
            run = uow.pipeline_runs.add(
                PipelineRun(
                    phase=StageName.TRANSCRIBE,
                    status=RunStatus.RUNNING,
                    started_at=UTC_NOW,
                    video_id=video_id,
                )
            )
            assert run.id is not None
            uow.pipeline_runs.update_status(
                run.id,
                status=RunStatus.OK,
                finished_at=UTC_NOW + timedelta(seconds=5),
            )

        with SqliteUnitOfWork(engine) as uow:
            latest = uow.pipeline_runs.latest_for_video(video_id)
            assert latest is not None
            assert latest.status is RunStatus.OK
            assert latest.finished_at is not None
            duration = latest.duration()
            assert duration is not None
            assert duration.total_seconds() == 5

    def test_latest_by_phase_returns_most_recent(self, engine: Engine) -> None:
        video_id = _seed_video(engine, "phase1")

        with SqliteUnitOfWork(engine) as uow:
            uow.pipeline_runs.add(
                PipelineRun(
                    phase=StageName.INGEST,
                    status=RunStatus.OK,
                    started_at=UTC_NOW - timedelta(hours=1),
                    video_id=video_id,
                )
            )
            uow.pipeline_runs.add(
                PipelineRun(
                    phase=StageName.TRANSCRIBE,
                    status=RunStatus.FAILED,
                    started_at=UTC_NOW,
                    video_id=video_id,
                    error="out of memory",
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            latest_ingest = uow.pipeline_runs.latest_by_phase(
                video_id, StageName.INGEST
            )
            assert latest_ingest is not None
            assert latest_ingest.status is RunStatus.OK

            latest_transcribe = uow.pipeline_runs.latest_by_phase(
                video_id, StageName.TRANSCRIBE
            )
            assert latest_transcribe is not None
            assert latest_transcribe.status is RunStatus.FAILED
            assert latest_transcribe.error == "out of memory"

            latest_frames = uow.pipeline_runs.latest_by_phase(
                video_id, StageName.FRAMES
            )
            assert latest_frames is None

    def test_list_recent_newest_first(self, engine: Engine) -> None:
        video_id = _seed_video(engine, "recent")

        with SqliteUnitOfWork(engine) as uow:
            for i in range(5):
                uow.pipeline_runs.add(
                    PipelineRun(
                        phase=StageName.INGEST,
                        status=RunStatus.OK,
                        started_at=UTC_NOW + timedelta(minutes=i),
                        video_id=video_id,
                    )
                )

        with SqliteUnitOfWork(engine) as uow:
            recent = uow.pipeline_runs.list_recent(limit=3)
            assert len(recent) == 3
            # Newest first: started_at descending
            assert recent[0].started_at >= recent[1].started_at >= recent[2].started_at

    def test_count_tracks_inserts(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            assert uow.pipeline_runs.count() == 0

        video_id = _seed_video(engine, "count")

        with SqliteUnitOfWork(engine) as uow:
            uow.pipeline_runs.add(
                PipelineRun(
                    phase=StageName.INGEST,
                    status=RunStatus.PENDING,
                    started_at=UTC_NOW,
                    video_id=video_id,
                )
            )
            uow.pipeline_runs.add(
                PipelineRun(
                    phase=StageName.TRANSCRIBE,
                    status=RunStatus.PENDING,
                    started_at=UTC_NOW,
                    video_id=video_id,
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            assert uow.pipeline_runs.count() == 2

    def test_run_without_video_id_is_valid(self, engine: Engine) -> None:
        """Ingest-stage failures happen before a videos row exists. The
        pipeline_run row must still be writable with only source_url."""
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.pipeline_runs.add(
                PipelineRun(
                    phase=StageName.INGEST,
                    status=RunStatus.FAILED,
                    started_at=UTC_NOW,
                    finished_at=UTC_NOW + timedelta(seconds=1),
                    source_url="https://broken.example/x",
                    error="url not reachable",
                )
            )
            assert stored.id is not None
            assert stored.video_id is None

        with SqliteUnitOfWork(engine) as uow:
            recent = uow.pipeline_runs.list_recent(limit=1)
            assert len(recent) == 1
            assert recent[0].video_id is None
            assert recent[0].source_url == "https://broken.example/x"
