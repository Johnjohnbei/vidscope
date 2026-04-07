"""Return the last N pipeline runs — powers ``vidscope status``.

The status command is the operator's primary window into what the
pipeline has been doing. It reads exclusively from ``pipeline_runs``
so even a half-failed ingest leaves a visible trace.
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import PipelineRun
from vidscope.ports import UnitOfWorkFactory

__all__ = ["GetStatusResult", "GetStatusUseCase"]


@dataclass(frozen=True, slots=True)
class GetStatusResult:
    """List of the most recent pipeline runs.

    ``runs`` is ordered newest-first. An empty list is a valid state
    and means no ingest has ever been attempted.
    """

    runs: tuple[PipelineRun, ...]
    total_runs: int
    total_videos: int


class GetStatusUseCase:
    """Return the most recent pipeline runs and quick aggregate counts."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, limit: int = 10) -> GetStatusResult:
        """Return the ``limit`` most recent pipeline runs newest-first.

        ``limit`` is clamped to the range [1, 100] to prevent unbounded
        result sets. Also returns aggregate counts (total runs, total
        videos) so the CLI can render the dashboard header in one query.
        """
        limit = max(1, min(limit, 100))
        with self._uow_factory() as uow:
            runs = uow.pipeline_runs.list_recent(limit=limit)
            return GetStatusResult(
                runs=tuple(runs),
                total_runs=uow.pipeline_runs.count(),
                total_videos=uow.videos.count(),
            )
