"""StatsStage — metadata-only probe appended to the video_stats table.

Standalone stage (M008 pattern from VisualIntelligenceStage): NOT
registered in the default ``vidscope add`` pipeline graph. Invoked only
by RefreshStatsUseCase and ``vidscope refresh-stats``.

Append-only contract (D031):
- ``is_satisfied()`` always returns ``False`` so every invocation produces a
  fresh snapshot (deduplication is handled by the repository via
  ``UNIQUE(video_id, captured_at)`` — D-01).
- Missing counters stay ``None`` (D-03) — never replaced with 0.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from vidscope.domain import DomainError, StageName, VideoStats
from vidscope.ports import PipelineContext, StageResult, UnitOfWork
from vidscope.ports.stats_probe import StatsProbe

__all__ = ["StatsStage"]

_logger = logging.getLogger(__name__)


class StatsStage:
    """Append-only stats probe stage.

    Executes :meth:`StatsProbe.probe_stats` and writes one row to
    ``video_stats`` via :meth:`UnitOfWork.video_stats.append`. The
    :class:`PipelineRunner` handles the pipeline_runs row and the
    transactional bundle when used within the runner; when invoked
    standalone by :class:`RefreshStatsUseCase`, the use case manages
    its own transaction.

    This stage is intentionally NOT registered in the default
    ``PipelineRunner.stages`` list (anti-pitfall M009 Pitfall-3). The
    :class:`Container` exposes it as a separate ``stats_stage`` attribute.
    """

    name: str = StageName.STATS.value

    def __init__(self, *, stats_probe: StatsProbe) -> None:
        self._probe = stats_probe

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Always ``False`` — append-only, every invocation creates a new row.

        The append-only design (D031) means we never short-circuit this stage
        based on existing rows. Deduplication within the same second is handled
        at the DB level via the ``UNIQUE(video_id, captured_at)`` constraint
        (D-01).
        """
        return False

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Probe stats for ``ctx.source_url`` and append the result.

        Raises
        ------
        DomainError
            When ``ctx.source_url`` is empty, when ``ctx.video_id`` is
            ``None`` (ingest must run first), or when the probe returns
            no data for the URL.
        """
        if not ctx.source_url:
            raise DomainError(
                "stats stage requires a non-empty ctx.source_url",
                stage=StageName.STATS,
            )

        if ctx.video_id is None:
            raise DomainError(
                "stats stage requires ctx.video_id — video must be ingested first",
                stage=StageName.STATS,
            )

        probed = self._probe.probe_stats(ctx.source_url)
        if probed is None:
            raise DomainError(
                f"stats probe returned no data for {ctx.source_url}",
                stage=StageName.STATS,
            )

        stats = replace(probed, video_id=ctx.video_id)
        uow.video_stats.append(stats)

        _logger.info(
            "stats appended for video_id=%s (views=%s, likes=%s)",
            ctx.video_id,
            stats.view_count,
            stats.like_count,
        )
        return StageResult(
            message=(
                f"stats appended for video_id={ctx.video_id} "
                f"(views={stats.view_count}, likes={stats.like_count})"
            )
        )
