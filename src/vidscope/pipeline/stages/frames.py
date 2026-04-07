"""FramesStage — third stage of the pipeline.

Reads ``videos.media_key`` from the pipeline context, resolves it
through MediaStorage to a real on-disk path, calls the FrameExtractor
port to extract a set of frames, copies each extracted frame into
MediaStorage at a stable key, and persists Frame entities via
FrameRepository.add_many in the same UnitOfWork as the matching
pipeline_runs row.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from vidscope.domain import (
    Frame,
    FrameExtractionError,
    StageName,
)
from vidscope.ports import (
    FrameExtractor,
    MediaStorage,
    PipelineContext,
    StageResult,
    UnitOfWork,
)

__all__ = ["FramesStage"]


class FramesStage:
    """Third stage of the pipeline — extract frames from media."""

    name: str = StageName.FRAMES.value

    def __init__(
        self,
        *,
        frame_extractor: FrameExtractor,
        media_storage: MediaStorage,
        cache_dir: Path,
        max_frames: int = 30,
    ) -> None:
        self._extractor = frame_extractor
        self._media_storage = media_storage
        self._cache_dir = cache_dir
        self._max_frames = max_frames

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Return True if frames already exist for the video."""
        if ctx.video_id is None:
            return False
        existing = uow.frames.list_for_video(ctx.video_id)
        return len(existing) > 0

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Extract frames and persist them with stable storage keys.

        Mutates ``ctx.frame_ids`` on success.

        Raises
        ------
        FrameExtractionError
            When ctx.video_id or ctx.media_key is missing, when the
            media file cannot be resolved on disk, or when the
            extractor itself fails.
        """
        if ctx.video_id is None:
            raise FrameExtractionError(
                "frames stage requires ctx.video_id; ingest stage must run first"
            )
        if not ctx.media_key:
            raise FrameExtractionError(
                f"frames stage requires ctx.media_key for video {ctx.video_id}"
            )

        try:
            media_path = self._media_storage.resolve(ctx.media_key)
        except Exception as exc:
            raise FrameExtractionError(
                f"failed to resolve media key {ctx.media_key!r}: {exc}",
                cause=exc,
            ) from exc

        if not isinstance(media_path, Path) or not media_path.exists():
            raise FrameExtractionError(
                f"media file not found at resolved path {media_path}"
            )

        # Extract into a temp dir under cache, then copy each frame
        # into MediaStorage at the canonical key. The temp dir is
        # cleaned up automatically.
        with tempfile.TemporaryDirectory(
            prefix="vidscope-frames-", dir=str(self._cache_dir)
        ) as tmp:
            raw_frames = self._extractor.extract_frames(
                str(media_path), tmp, max_frames=self._max_frames
            )

            if not raw_frames:
                raise FrameExtractionError(
                    f"extractor produced no frames for video {ctx.video_id}"
                )

            # Build stable storage keys and copy each frame into
            # MediaStorage. The platform/platform_id come from the
            # context (set by IngestStage).
            platform_segment = (
                ctx.platform.value if ctx.platform else "unknown"
            )
            id_segment = str(ctx.platform_id or ctx.video_id)

            persistable: list[Frame] = []
            for index, raw in enumerate(raw_frames):
                source_path = Path(raw.image_key)
                if not source_path.exists():
                    raise FrameExtractionError(
                        f"extractor reported frame at {source_path} but "
                        f"file does not exist"
                    )

                key = (
                    f"videos/{platform_segment}/{id_segment}"
                    f"/frames/{index:04d}{source_path.suffix}"
                )
                stored_key = self._media_storage.store(key, source_path)

                persistable.append(
                    Frame(
                        video_id=ctx.video_id,
                        image_key=stored_key,
                        timestamp_ms=raw.timestamp_ms,
                        is_keyframe=raw.is_keyframe,
                    )
                )

        stored_frames = uow.frames.add_many(persistable)
        ctx.frame_ids = [f.id for f in stored_frames if f.id is not None]

        return StageResult(
            message=f"extracted {len(stored_frames)} frames"
        )
