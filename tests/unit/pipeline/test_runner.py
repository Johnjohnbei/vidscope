"""Tests for :class:`PipelineRunner` using in-memory fake stages.

The runner contract is independent of SQLite — it just needs a
:class:`UnitOfWorkFactory` and a :class:`Clock`. We build the simplest
possible fake UoW (a SQLite engine with the real schema, wrapped in
:class:`SqliteUnitOfWork`) because building a conformant pure-Python
in-memory UoW is more code than reusing the real adapter in-memory.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    IngestError,
    RunStatus,
    StageCrashError,
    StageName,
)
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.pipeline import PipelineRunner
from vidscope.ports import PipelineContext, StageResult, UnitOfWork

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FixedClock:
    """A deterministic :class:`Clock` for tests."""

    def __init__(self, base: datetime) -> None:
        self._base = base
        self._ticks = 0

    def now(self) -> datetime:
        current = self._base + timedelta(seconds=self._ticks)
        self._ticks += 1
        return current


class DummyOkStage:
    """A stage that always succeeds."""

    name = StageName.INGEST.value

    def __init__(self) -> None:
        self.execute_called = 0

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        return False

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        self.execute_called += 1
        return StageResult(message="dummy ok")


class DummyFailingStage:
    """A stage that raises a typed :class:`IngestError`."""

    name = StageName.INGEST.value

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        return False

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        raise IngestError("simulated network failure")


class DummyCrashingStage:
    """A stage that leaks an untyped exception (a BUG — tests the wrapper)."""

    name = StageName.INGEST.value

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        return False

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        raise RuntimeError("oops, forgot to wrap this")


class DummySatisfiedStage:
    """A stage whose ``is_satisfied`` returns ``True`` — should be skipped."""

    name = StageName.TRANSCRIBE.value

    def __init__(self) -> None:
        self.execute_called = 0

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        return True

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        self.execute_called += 1
        return StageResult(message="should never run")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    db_path = tmp_path / "runner.db"
    eng = build_engine(db_path)
    init_db(eng)
    return eng


@pytest.fixture()
def uow_factory(engine: Engine):  # type: ignore[no-untyped-def]
    def _factory() -> UnitOfWork:
        return SqliteUnitOfWork(engine)

    return _factory


@pytest.fixture()
def clock() -> FixedClock:
    return FixedClock(datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_single_ok_stage_produces_one_ok_run(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
        clock: FixedClock,
    ) -> None:
        stage = DummyOkStage()
        runner = PipelineRunner(
            [stage], unit_of_work_factory=uow_factory, clock=clock
        )

        result = runner.run(PipelineContext(source_url="https://example.com/x"))

        assert result.success is True
        assert result.failed_at is None
        assert len(result.outcomes) == 1
        assert result.outcomes[0].status is RunStatus.OK
        assert stage.execute_called == 1

        # pipeline_runs has exactly one OK row for the stage
        with SqliteUnitOfWork(engine) as uow:
            runs = uow.pipeline_runs.list_recent(limit=10)
            assert len(runs) == 1
            assert runs[0].status is RunStatus.OK
            assert runs[0].phase is StageName.INGEST
            assert runs[0].finished_at is not None
            assert runs[0].source_url == "https://example.com/x"

    def test_multiple_stages_run_in_order(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
        clock: FixedClock,
    ) -> None:
        ingest = DummyOkStage()
        # Reuse DummyOkStage but tag it as TRANSCRIBE for the second run
        transcribe = DummyOkStage()
        transcribe.name = StageName.TRANSCRIBE.value

        runner = PipelineRunner(
            [ingest, transcribe],
            unit_of_work_factory=uow_factory,
            clock=clock,
        )
        result = runner.run(PipelineContext(source_url="https://example.com/y"))

        assert result.success is True
        assert [o.stage_name for o in result.outcomes] == [
            StageName.INGEST.value,
            StageName.TRANSCRIBE.value,
        ]

        with SqliteUnitOfWork(engine) as uow:
            runs = uow.pipeline_runs.list_recent(limit=10)
            assert len(runs) == 2
            phases = {run.phase for run in runs}
            assert phases == {StageName.INGEST, StageName.TRANSCRIBE}


class TestSkipping:
    def test_satisfied_stage_is_skipped(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
        clock: FixedClock,
    ) -> None:
        stage = DummySatisfiedStage()
        runner = PipelineRunner(
            [stage], unit_of_work_factory=uow_factory, clock=clock
        )

        result = runner.run(PipelineContext(source_url="https://example.com/z"))

        assert result.success is True
        assert result.outcomes[0].status is RunStatus.SKIPPED
        assert result.outcomes[0].skipped is True
        assert stage.execute_called == 0

        with SqliteUnitOfWork(engine) as uow:
            runs = uow.pipeline_runs.list_recent(limit=10)
            assert len(runs) == 1
            assert runs[0].status is RunStatus.SKIPPED


class TestFailurePaths:
    def test_typed_domain_error_marks_run_failed(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
        clock: FixedClock,
    ) -> None:
        stage = DummyFailingStage()
        runner = PipelineRunner(
            [stage], unit_of_work_factory=uow_factory, clock=clock
        )

        result = runner.run(PipelineContext(source_url="https://example.com/f"))

        assert result.success is False
        assert result.failed_at == StageName.INGEST.value
        assert len(result.outcomes) == 1
        assert result.outcomes[0].status is RunStatus.FAILED
        assert "simulated network failure" in (result.outcomes[0].error or "")

        with SqliteUnitOfWork(engine) as uow:
            runs = uow.pipeline_runs.list_recent(limit=10)
            assert len(runs) == 1
            assert runs[0].status is RunStatus.FAILED
            assert runs[0].error is not None
            assert "simulated network failure" in runs[0].error

    def test_untyped_exception_is_wrapped_in_stage_crash_error(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
        clock: FixedClock,
    ) -> None:
        stage = DummyCrashingStage()
        runner = PipelineRunner(
            [stage], unit_of_work_factory=uow_factory, clock=clock
        )

        result = runner.run(PipelineContext(source_url="https://example.com/c"))

        assert result.success is False
        assert result.outcomes[0].status is RunStatus.FAILED
        error_message = result.outcomes[0].error or ""
        assert "leaked an untyped exception" in error_message

        with SqliteUnitOfWork(engine) as uow:
            runs = uow.pipeline_runs.list_recent(limit=10)
            assert runs[0].status is RunStatus.FAILED
            assert "leaked an untyped exception" in (runs[0].error or "")

    def test_failing_stage_aborts_subsequent_stages(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
        clock: FixedClock,
    ) -> None:
        failing = DummyFailingStage()
        after = DummyOkStage()
        after.name = StageName.TRANSCRIBE.value

        runner = PipelineRunner(
            [failing, after],
            unit_of_work_factory=uow_factory,
            clock=clock,
        )

        result = runner.run(PipelineContext(source_url="https://example.com/a"))

        assert result.success is False
        assert len(result.outcomes) == 1
        assert after.execute_called == 0

        with SqliteUnitOfWork(engine) as uow:
            runs = uow.pipeline_runs.list_recent(limit=10)
            # Only the failing run was recorded; the transcribe stage
            # never started so no TRANSCRIBE row should exist.
            assert len(runs) == 1
            assert runs[0].phase is StageName.INGEST


class TestInvalidStageName:
    def test_stage_with_bogus_name_is_rejected(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
        clock: FixedClock,
    ) -> None:
        class BadStage:
            name = "not-a-real-stage-name"

            def is_satisfied(self, ctx, uow):  # type: ignore[no-untyped-def]
                return False

            def execute(self, ctx, uow):  # type: ignore[no-untyped-def]
                return StageResult()

        runner = PipelineRunner(
            [BadStage()],  # type: ignore[list-item]
            unit_of_work_factory=uow_factory,
            clock=clock,
        )

        with pytest.raises(StageCrashError):
            runner.run(PipelineContext(source_url="https://example.com/b"))


class TestStageNames:
    def test_stage_names_property_lists_all(
        self, uow_factory, clock: FixedClock  # type: ignore[no-untyped-def]
    ) -> None:
        stages = [DummyOkStage(), DummySatisfiedStage()]
        runner = PipelineRunner(
            stages, unit_of_work_factory=uow_factory, clock=clock
        )
        assert runner.stage_names == (
            StageName.INGEST.value,
            StageName.TRANSCRIBE.value,
        )
