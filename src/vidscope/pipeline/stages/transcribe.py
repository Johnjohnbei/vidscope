"""TranscribeStage — second stage of the pipeline.

Reads ``videos.media_key`` from the pipeline context, resolves it
through MediaStorage to a real on-disk path, calls the Transcriber
port to produce a Transcript, and persists it via the
TranscriptRepository in the same UnitOfWork as the matching
pipeline_runs row.

Resume-from-failure
-------------------

Unlike :class:`IngestStage` (which always re-downloads per D025),
this stage CAN check whether its output exists cheaply: a single DB
query for ``transcripts.video_id``. So :meth:`is_satisfied` returns
True when a transcript already exists, letting re-runs of
``vidscope add <url>`` skip transcription entirely after the first
successful run.
"""

from __future__ import annotations

from pathlib import Path

from vidscope.domain import (
    MediaType,
    StageName,
    Transcript,
    TranscriptionError,
)
from vidscope.ports import (
    MediaStorage,
    PipelineContext,
    StageResult,
    Transcriber,
    UnitOfWork,
)

__all__ = ["TranscribeStage"]


class TranscribeStage:
    """Second stage of the pipeline — produce a transcript from media."""

    name: str = StageName.TRANSCRIBE.value

    def __init__(
        self,
        *,
        transcriber: Transcriber,
        media_storage: MediaStorage,
    ) -> None:
        self._transcriber = transcriber
        self._media_storage = media_storage

    # ------------------------------------------------------------------
    # Stage protocol
    # ------------------------------------------------------------------

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Return True if transcription is not needed or already done.

        Images and carousels have no audio track — skip immediately.
        For videos, a cheap DB query checks whether a transcript exists.
        """
        if ctx.media_type in (MediaType.IMAGE, MediaType.CAROUSEL):
            return True
        if ctx.video_id is None:
            return False
        existing = uow.transcripts.get_for_video(ctx.video_id)
        return existing is not None

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Transcribe the video's media file and persist the transcript.

        Mutates ``ctx.transcript_id`` and ``ctx.language`` on success.

        Raises
        ------
        TranscriptionError
            When ctx.video_id or ctx.media_key is missing (the ingest
            stage didn't run or failed silently), when the media file
            cannot be resolved on disk, or when the transcriber itself
            fails. Always retryable=False — transcription failures
            don't self-heal.
        """
        if ctx.video_id is None:
            raise TranscriptionError(
                "transcribe stage requires ctx.video_id; ingest stage "
                "must run successfully first"
            )
        if not ctx.media_key:
            raise TranscriptionError(
                f"transcribe stage requires ctx.media_key for video "
                f"{ctx.video_id}; ingest stage did not store a media key"
            )

        try:
            media_path = self._media_storage.resolve(ctx.media_key)
        except Exception as exc:
            raise TranscriptionError(
                f"failed to resolve media key {ctx.media_key!r}: {exc}",
                cause=exc,
            ) from exc

        if not isinstance(media_path, Path) or not media_path.exists():
            raise TranscriptionError(
                f"media file not found at resolved path {media_path}"
            )

        # Run the transcriber. The Transcriber port itself raises
        # TranscriptionError on failure — we let it propagate as-is.
        raw_transcript = self._transcriber.transcribe(str(media_path))

        # The transcriber returns a Transcript with VideoId(0) as a
        # placeholder. Build a new instance with the real video_id
        # before persisting.
        transcript = Transcript(
            video_id=ctx.video_id,
            language=raw_transcript.language,
            full_text=raw_transcript.full_text,
            segments=raw_transcript.segments,
        )

        persisted = uow.transcripts.add(transcript)
        ctx.transcript_id = persisted.id
        ctx.language = persisted.language

        segment_count = len(persisted.segments)
        text_length = len(persisted.full_text)
        return StageResult(
            message=(
                f"transcribed {persisted.language.value}: "
                f"{segment_count} segments, {text_length} chars"
            )
        )
