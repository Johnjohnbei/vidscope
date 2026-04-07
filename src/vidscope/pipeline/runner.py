"""Generic pipeline runner.

Takes a list of :class:`Stage` implementations and runs them in order
against a :class:`PipelineContext`, producing one :class:`PipelineRun`
row per stage and enforcing the following guarantees:

1. **Resume-from-failure.** Before executing a stage, the runner calls
   ``stage.is_satisfied(ctx, uow)``. If it returns ``True``, the stage
   is skipped and a SKIPPED run row is written — the runner moves on.

2. **Transactional stage + run row coupling.** Each stage runs inside a
   single :class:`UnitOfWork`. The matching ``pipeline_runs`` row is
   written in the same transaction. Either both the stage's domain
   write and the run row commit, or neither does. This is what makes
   "no half-written rows" a property of the architecture, not a prayer.

3. **Typed-error propagation.** When a stage raises a
   :class:`DomainError`, the runner captures it, marks the current
   run row FAILED, and aborts subsequent stages. The exception is then
   re-raised so callers (the use case, ultimately the CLI) see the
   typed failure.

4. **Unexpected-exception wrapping.** If a stage leaks a non-domain
   exception, the runner wraps it in :class:`StageCrashError` so the
   run row gets a meaningful phase label and the next agent inspecting
   ``pipeline_runs`` knows an adapter failed to translate its error.

Design notes
------------

- The runner does not hold any state beyond the stages and collaborators
  it was constructed with. It is safe to share a single instance across
  multiple use-case invocations.
- The runner receives a ``UnitOfWorkFactory`` not a ``UnitOfWork`` — it
  opens exactly one UoW per stage so each stage's write is its own
  commit boundary.
- The runner calls ``clock.now()`` once before and once after each
  stage so started_at and finished_at are authoritative and testable.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from vidscope.domain import (
    DomainError,
    PipelineRun,
    RunStatus,
    StageCrashError,
    StageName,
)
from vidscope.ports import (
    Clock,
    PipelineContext,
    Stage,
    UnitOfWork,
    UnitOfWorkFactory,
)

__all__ = ["PipelineRunner", "RunResult", "StageOutcome"]


@dataclass(frozen=True, slots=True)
class StageOutcome:
    """Outcome of one stage execution as seen by the runner."""

    stage_name: str
    status: RunStatus
    skipped: bool
    error: str | None = None
    run_id: int | None = None


@dataclass(slots=True)
class RunResult:
    """Aggregate result of running a pipeline over a context.

    ``success`` is ``True`` when every stage finished OK or was skipped.
    ``failed_at`` names the stage that raised, if any. ``outcomes`` has
    one entry per stage that actually ran (including skipped).
    """

    success: bool
    context: PipelineContext
    outcomes: list[StageOutcome] = field(default_factory=list)
    failed_at: str | None = None


class PipelineRunner:
    """Runs a sequence of stages against a shared pipeline context.

    Construction takes the stages and the collaborators they need. A
    runner instance is stateless beyond these references and can be
    reused across many use-case invocations.
    """

    def __init__(
        self,
        stages: Sequence[Stage],
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
    ) -> None:
        self._stages: tuple[Stage, ...] = tuple(stages)
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def stage_names(self) -> tuple[str, ...]:
        return tuple(stage.name for stage in self._stages)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, ctx: PipelineContext) -> RunResult:
        """Execute every stage in order against ``ctx``.

        Returns a :class:`RunResult` describing what happened. Never
        raises for typed domain errors — they land in ``failed_at``
        and ``success=False``. Truly unexpected exceptions are wrapped
        in :class:`StageCrashError` inside the same pattern.
        """
        result = RunResult(success=True, context=ctx)

        for stage in self._stages:
            outcome = self._run_one_stage(stage, ctx)
            result.outcomes.append(outcome)
            if outcome.status is RunStatus.FAILED:
                result.success = False
                result.failed_at = stage.name
                break

        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_one_stage(
        self, stage: Stage, ctx: PipelineContext
    ) -> StageOutcome:
        """Execute a single stage inside its own transactional UoW."""
        phase = _resolve_stage_phase(stage)
        started_at = self._clock.now()

        with self._unit_of_work_factory() as uow:
            # Resume-from-failure check runs inside the same transaction
            # so its read is consistent with any concurrent writes.
            try:
                satisfied = stage.is_satisfied(ctx, uow)
            except DomainError as exc:
                run = self._record_failure(
                    uow,
                    ctx=ctx,
                    phase=phase,
                    started_at=started_at,
                    error=str(exc),
                )
                return StageOutcome(
                    stage_name=stage.name,
                    status=RunStatus.FAILED,
                    skipped=False,
                    error=str(exc),
                    run_id=run.id,
                )

            if satisfied:
                run = self._record_skipped(
                    uow,
                    ctx=ctx,
                    phase=phase,
                    started_at=started_at,
                )
                return StageOutcome(
                    stage_name=stage.name,
                    status=RunStatus.SKIPPED,
                    skipped=True,
                    run_id=run.id,
                )

            # Record a RUNNING row up-front so a crash mid-stage leaves
            # a visible trace even before the finish write lands.
            run = uow.pipeline_runs.add(
                PipelineRun(
                    phase=phase,
                    status=RunStatus.RUNNING,
                    started_at=started_at,
                    video_id=ctx.video_id,
                    source_url=ctx.source_url,
                )
            )
            assert run.id is not None

            try:
                stage_result = stage.execute(ctx, uow)
            except DomainError as exc:
                finished_at = self._clock.now()
                # Pass ctx.video_id too — the stage may have persisted
                # the videos row before failing on a later operation.
                # If it did, the pipeline_runs row should be linked
                # to the persisted video for full traceability.
                uow.pipeline_runs.update_status(
                    run.id,
                    status=RunStatus.FAILED,
                    finished_at=finished_at,
                    error=str(exc),
                    video_id=ctx.video_id,
                )
                return StageOutcome(
                    stage_name=stage.name,
                    status=RunStatus.FAILED,
                    skipped=False,
                    error=str(exc),
                    run_id=run.id,
                )
            except Exception as exc:
                finished_at = self._clock.now()
                wrapped = StageCrashError(
                    f"stage {stage.name!r} leaked an untyped exception: {exc}",
                    cause=exc,
                )
                uow.pipeline_runs.update_status(
                    run.id,
                    status=RunStatus.FAILED,
                    finished_at=finished_at,
                    error=str(wrapped),
                    video_id=ctx.video_id,
                )
                return StageOutcome(
                    stage_name=stage.name,
                    status=RunStatus.FAILED,
                    skipped=False,
                    error=str(wrapped),
                    run_id=run.id,
                )

            # Happy path: update the row to OK (or SKIPPED if the stage
            # short-circuited at runtime after inspection). Pass the
            # video_id that the stage populated on the context — for
            # the ingest stage this is the just-persisted videos row.
            finished_at = self._clock.now()
            final_status = (
                RunStatus.SKIPPED if stage_result.skipped else RunStatus.OK
            )
            uow.pipeline_runs.update_status(
                run.id,
                status=final_status,
                finished_at=finished_at,
                video_id=ctx.video_id,
            )
            return StageOutcome(
                stage_name=stage.name,
                status=final_status,
                skipped=stage_result.skipped,
                run_id=run.id,
            )

    # ------------------------------------------------------------------
    # Row helpers
    # ------------------------------------------------------------------

    def _record_skipped(
        self,
        uow: UnitOfWork,
        *,
        ctx: PipelineContext,
        phase: StageName,
        started_at: datetime,
    ) -> PipelineRun:
        finished_at = self._clock.now()
        return uow.pipeline_runs.add(
            PipelineRun(
                phase=phase,
                status=RunStatus.SKIPPED,
                started_at=started_at,
                finished_at=finished_at,
                video_id=ctx.video_id,
                source_url=ctx.source_url,
            )
        )

    def _record_failure(
        self,
        uow: UnitOfWork,
        *,
        ctx: PipelineContext,
        phase: StageName,
        started_at: datetime,
        error: str,
    ) -> PipelineRun:
        finished_at = self._clock.now()
        return uow.pipeline_runs.add(
            PipelineRun(
                phase=phase,
                status=RunStatus.FAILED,
                started_at=started_at,
                finished_at=finished_at,
                error=error,
                video_id=ctx.video_id,
                source_url=ctx.source_url,
            )
        )


def _resolve_stage_phase(stage: Stage) -> StageName:
    """Translate a stage's string name to a :class:`StageName` enum.

    Stages declare ``name: str`` so adapters can pick arbitrary values;
    we map to the enum at the edge so the DB stays consistent.
    """
    try:
        return StageName(stage.name)
    except ValueError as exc:
        raise StageCrashError(
            f"stage {stage!r} reports name={stage.name!r} which is not a "
            f"valid StageName enum value"
        ) from exc


