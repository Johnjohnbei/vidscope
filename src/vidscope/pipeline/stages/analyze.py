"""AnalyzeStage — fourth stage of the pipeline.

Reads the transcript produced by the transcribe stage, runs the
configured Analyzer to produce a structured Analysis (language,
keywords, topics, score, summary), and persists it via the
AnalysisRepository in the same UnitOfWork as the matching
pipeline_runs row.
"""

from __future__ import annotations

from vidscope.domain import (
    Analysis,
    AnalysisError,
    MediaType,
    StageName,
)
from vidscope.ports import (
    Analyzer,
    PipelineContext,
    StageResult,
    UnitOfWork,
)

__all__ = ["AnalyzeStage"]


class AnalyzeStage:
    """Fourth stage of the pipeline — produce a structured analysis."""

    name: str = StageName.ANALYZE.value

    def __init__(self, *, analyzer: Analyzer) -> None:
        self._analyzer = analyzer

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Return True if analysis can be skipped.

        IMAGE and CAROUSEL have no transcript — text analysis is not
        applicable. For VIDEO, skip only when an analysis already exists.
        """
        if ctx.media_type in (MediaType.IMAGE, MediaType.CAROUSEL):
            return True
        if ctx.video_id is None:
            return False
        existing = uow.analyses.get_latest_for_video(ctx.video_id)
        return existing is not None

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Read the transcript, analyze it, persist the result.

        Mutates ``ctx.analysis_id`` on success.

        Raises
        ------
        AnalysisError
            When ctx.video_id is missing, when no transcript exists
            for the video (the upstream stage failed silently), or
            when the analyzer itself raises.
        """
        if ctx.video_id is None:
            raise AnalysisError(
                "analyze stage requires ctx.video_id; ingest stage must run first"
            )

        transcript = uow.transcripts.get_for_video(ctx.video_id)
        if transcript is None:
            raise AnalysisError(
                f"analyze stage requires a transcript for video {ctx.video_id}; "
                f"transcribe stage did not run or failed"
            )

        # The analyzer port itself raises AnalysisError on failure.
        # We let it propagate.
        raw_analysis = self._analyzer.analyze(transcript)

        # The analyzer should already set the right video_id (it
        # copies from the transcript). But to be defensive, we rebuild
        # the entity with ctx.video_id explicitly so the persisted
        # row's FK is always correct regardless of analyzer behavior.
        analysis = Analysis(
            video_id=ctx.video_id,
            provider=raw_analysis.provider,
            language=raw_analysis.language,
            keywords=raw_analysis.keywords,
            topics=raw_analysis.topics,
            score=raw_analysis.score,
            summary=raw_analysis.summary,
        )

        persisted = uow.analyses.add(analysis)
        ctx.analysis_id = persisted.id

        keyword_count = len(persisted.keywords)
        score_str = (
            f"{persisted.score:.0f}" if persisted.score is not None else "n/a"
        )
        return StageResult(
            message=(
                f"analyzed via {persisted.provider}: "
                f"{keyword_count} keywords, score={score_str}"
            )
        )
