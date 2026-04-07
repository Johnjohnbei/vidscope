"""IndexStage — fifth and final stage of the pipeline.

Writes the transcript and analysis summary for a video into the FTS5
virtual table via the SearchIndex port. This is what makes
``vidscope search "<term>"`` return real hits.

The SearchIndex adapter (SearchIndexSQLite in S01) uses
DELETE-then-INSERT semantics so re-indexing is safe and idempotent.
This stage's :meth:`is_satisfied` returns False always: we always
re-run the index to pick up any transcript or analysis changes,
and since the adapter is idempotent there is no duplication.
"""

from __future__ import annotations

from vidscope.domain import (
    IndexingError,
    StageName,
)
from vidscope.ports import (
    PipelineContext,
    StageResult,
    UnitOfWork,
)

__all__ = ["IndexStage"]


class IndexStage:
    """Fifth stage of the pipeline — populate the FTS5 search index."""

    name: str = StageName.INDEX.value

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Always False: re-indexing is cheap and idempotent."""
        _ = (ctx, uow)
        return False

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Index the latest transcript and analysis summary for the video.

        Raises
        ------
        IndexingError
            When ctx.video_id is missing.
        """
        if ctx.video_id is None:
            raise IndexingError(
                "index stage requires ctx.video_id; ingest must run first"
            )

        indexed_documents = 0

        transcript = uow.transcripts.get_for_video(ctx.video_id)
        if transcript is not None and transcript.full_text.strip():
            uow.search_index.index_transcript(transcript)
            indexed_documents += 1

        analysis = uow.analyses.get_latest_for_video(ctx.video_id)
        if analysis is not None and analysis.summary and analysis.summary.strip():
            uow.search_index.index_analysis(analysis)
            indexed_documents += 1

        return StageResult(
            message=f"indexed {indexed_documents} documents"
        )
