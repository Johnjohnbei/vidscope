"""AnalyzeStage — fourth stage of the pipeline.

Reads the transcript produced by the transcribe stage (or, for
IMAGE / CAROUSEL content without audio, falls back to the OCR
frame_texts written by VisualIntelligenceStage — R062), runs the
configured Analyzer to produce a structured Analysis (language,
keywords, topics, score, summary + M010 score vector), and persists
it via the AnalysisRepository.
"""

from __future__ import annotations

from dataclasses import replace

from vidscope.domain import (
    AnalysisError,
    Language,
    StageName,
    Transcript,
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

        R062: no more IMAGE/CAROUSEL short-circuit. Every content with
        a known video_id is considered analyzable — we skip only when
        an Analysis row already exists for that video (idempotent).
        """
        if ctx.video_id is None:
            return False
        existing = uow.analyses.get_latest_for_video(ctx.video_id)
        return existing is not None

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Read the transcript (or OCR fallback), analyze it, persist.

        Mutates ``ctx.analysis_id`` on success.

        R062: when no Transcript is available (IMAGE / CAROUSEL or
        audio-less VIDEO), build a synthetic Transcript from the
        ``frame_texts`` rows written by VisualIntelligenceStage. If
        neither source is available, pass an empty Transcript so the
        analyzer produces a stub Analysis (score=0,
        summary='no speech detected') — no crash.

        Raises
        ------
        AnalysisError
            When ``ctx.video_id`` is missing, or when the analyzer
            itself raises.
        """
        if ctx.video_id is None:
            raise AnalysisError(
                "analyze stage requires ctx.video_id; ingest stage must run first"
            )

        transcript = uow.transcripts.get_for_video(ctx.video_id)
        if transcript is None:
            # R062: OCR fallback for IMAGE / CAROUSEL (and any video
            # that lost its transcript). Never raise — produce a stub
            # via the analyzer's empty-transcript branch if nothing.
            frame_texts = uow.frame_texts.list_for_video(ctx.video_id)
            ocr_concat = " ".join(
                ft.text for ft in frame_texts if ft.text and ft.text.strip()
            )
            transcript = Transcript(
                video_id=ctx.video_id,
                language=Language.UNKNOWN,
                full_text=ocr_concat,
                segments=(),
            )

        # The analyzer port itself raises AnalysisError on failure.
        # We let it propagate.
        raw_analysis = self._analyzer.analyze(transcript)

        # Preserve every field produced by the analyzer (including M010
        # additive fields: verticals, information_density, actionability,
        # novelty, production_quality, sentiment, is_sponsored,
        # content_type, reasoning). Only override video_id so the
        # persisted row's FK matches ctx regardless of analyzer behavior.
        analysis = replace(raw_analysis, video_id=ctx.video_id)

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
