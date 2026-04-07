"""Tests for :class:`IngestVideoUseCase` with the S02 real pipeline runner.

Uses a fake PipelineRunner that returns preset RunResult values so the
use case can be exercised without spinning up real stages. A real
SqliteUnitOfWork backs the `.videos.get()` read-back path so we verify
the actual round-trip works.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.application.ingest_video import IngestResult, IngestVideoUseCase
from vidscope.domain import (
    Platform,
    PlatformId,
    RunStatus,
    StageName,
    Video,
    VideoId,
)
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.pipeline.runner import RunResult, StageOutcome
from vidscope.ports import PipelineContext

# ---------------------------------------------------------------------------
# Fake pipeline runner
# ---------------------------------------------------------------------------


@dataclass
class FakeRunResult:
    """Minimal RunResult-shaped object for tests.

    The real :class:`RunResult` is a dataclass but we want to control
    every field independently so tests can simulate happy path,
    failing path, and edge cases without running real stages.
    """

    success: bool
    context: PipelineContext
    outcomes: list[StageOutcome] = field(default_factory=list)
    failed_at: str | None = None


class FakeRunner:
    """A PipelineRunner stand-in.

    ``behavior`` is a callable taking the PipelineContext and returning
    a RunResult-compatible object. It's called on every ``run()``.
    """

    def __init__(self, behavior) -> None:  # type: ignore[no-untyped-def]
        self._behavior = behavior
        self.calls: list[PipelineContext] = []

    def run(self, ctx: PipelineContext) -> RunResult:
        self.calls.append(ctx)
        return self._behavior(ctx)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    db_path = tmp_path / "use_case.db"
    eng = build_engine(db_path)
    init_db(eng)
    return eng


@pytest.fixture()
def uow_factory(engine: Engine):  # type: ignore[no-untyped-def]
    def _factory():  # type: ignore[no-untyped-def]
        return SqliteUnitOfWork(engine)

    return _factory


def _seed_video(engine: Engine, platform_id: str = "abc123") -> VideoId:
    """Insert a videos row and return its id. Used by happy-path tests
    so the use case's read-back query finds a real row."""
    with SqliteUnitOfWork(engine) as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId(platform_id),
                url=f"https://www.youtube.com/watch?v={platform_id}",
                title="Seeded title",
                author="Seeded author",
                duration=60.0,
                media_key=f"videos/youtube/{platform_id}/media.mp4",
            )
        )
        assert video.id is not None
        return video.id


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_success_returns_ok_result_with_metadata(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        video_id = _seed_video(engine, platform_id="happy1")

        def behavior(ctx: PipelineContext) -> FakeRunResult:
            # Simulate the runner: mutate the context the way a real
            # IngestStage would, then return success.
            ctx.video_id = video_id
            ctx.platform = Platform.YOUTUBE
            ctx.platform_id = PlatformId("happy1")
            ctx.media_key = "videos/youtube/happy1/media.mp4"
            return FakeRunResult(  # type: ignore[return-value]
                success=True,
                context=ctx,
                outcomes=[
                    StageOutcome(
                        stage_name=StageName.INGEST.value,
                        status=RunStatus.OK,
                        skipped=False,
                        run_id=42,
                    )
                ],
            )

        runner = FakeRunner(behavior)
        uc = IngestVideoUseCase(
            unit_of_work_factory=uow_factory, pipeline_runner=runner  # type: ignore[arg-type]
        )

        result = uc.execute("https://www.youtube.com/watch?v=happy1")

        assert isinstance(result, IngestResult)
        assert result.status is RunStatus.OK
        assert "youtube/happy1" in result.message
        assert "Seeded title" in result.message
        assert result.url == "https://www.youtube.com/watch?v=happy1"
        assert result.video_id == video_id
        assert result.platform is Platform.YOUTUBE
        assert result.platform_id == PlatformId("happy1")
        assert result.title == "Seeded title"
        assert result.author == "Seeded author"
        assert result.duration == 60.0
        assert result.run_id == 42

        # Runner was called exactly once with the trimmed URL
        assert len(runner.calls) == 1
        assert runner.calls[0].source_url == "https://www.youtube.com/watch?v=happy1"

    def test_trims_whitespace_from_url(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        _seed_video(engine, platform_id="trim1")

        def behavior(ctx: PipelineContext) -> FakeRunResult:
            ctx.video_id = VideoId(1)
            ctx.platform = Platform.YOUTUBE
            ctx.platform_id = PlatformId("trim1")
            return FakeRunResult(  # type: ignore[return-value]
                success=True,
                context=ctx,
                outcomes=[
                    StageOutcome(
                        stage_name=StageName.INGEST.value,
                        status=RunStatus.OK,
                        skipped=False,
                        run_id=1,
                    )
                ],
            )

        runner = FakeRunner(behavior)
        uc = IngestVideoUseCase(
            unit_of_work_factory=uow_factory, pipeline_runner=runner  # type: ignore[arg-type]
        )
        result = uc.execute("  https://www.youtube.com/watch?v=trim1  ")
        assert result.url == "https://www.youtube.com/watch?v=trim1"
        assert runner.calls[0].source_url == (
            "https://www.youtube.com/watch?v=trim1"
        )


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


class TestFailurePaths:
    def test_failing_runner_returns_failed_result_with_error_message(
        self,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        def behavior(ctx: PipelineContext) -> FakeRunResult:
            return FakeRunResult(  # type: ignore[return-value]
                success=False,
                context=ctx,
                outcomes=[
                    StageOutcome(
                        stage_name=StageName.INGEST.value,
                        status=RunStatus.FAILED,
                        skipped=False,
                        error="simulated network failure",
                        run_id=5,
                    )
                ],
                failed_at=StageName.INGEST.value,
            )

        runner = FakeRunner(behavior)
        uc = IngestVideoUseCase(
            unit_of_work_factory=uow_factory, pipeline_runner=runner  # type: ignore[arg-type]
        )
        result = uc.execute("https://www.youtube.com/watch?v=broken")

        assert result.status is RunStatus.FAILED
        assert "simulated network failure" in result.message
        assert result.run_id == 5
        assert result.video_id is None
        assert result.title is None

    def test_empty_url_returns_failed_without_calling_runner(
        self,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        runner = FakeRunner(lambda _ctx: None)
        uc = IngestVideoUseCase(
            unit_of_work_factory=uow_factory, pipeline_runner=runner  # type: ignore[arg-type]
        )

        result = uc.execute("   ")

        assert result.status is RunStatus.FAILED
        assert "empty" in result.message
        assert result.run_id is None
        assert len(runner.calls) == 0

    def test_none_url_returns_failed(
        self,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        runner = FakeRunner(lambda _ctx: None)
        uc = IngestVideoUseCase(
            unit_of_work_factory=uow_factory, pipeline_runner=runner  # type: ignore[arg-type]
        )
        result = uc.execute(None)  # type: ignore[arg-type]
        assert result.status is RunStatus.FAILED
        assert len(runner.calls) == 0

    def test_failing_runner_without_outcomes_still_returns_failed(
        self,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        """Edge case: runner returns success=False with no outcomes."""

        def behavior(ctx: PipelineContext) -> FakeRunResult:
            return FakeRunResult(  # type: ignore[return-value]
                success=False,
                context=ctx,
                outcomes=[],
                failed_at="ingest",
            )

        runner = FakeRunner(behavior)
        uc = IngestVideoUseCase(
            unit_of_work_factory=uow_factory, pipeline_runner=runner  # type: ignore[arg-type]
        )
        result = uc.execute("https://www.youtube.com/watch?v=weird")
        assert result.status is RunStatus.FAILED
        assert "pipeline failed" in result.message
