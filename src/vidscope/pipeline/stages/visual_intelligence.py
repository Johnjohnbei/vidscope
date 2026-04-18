"""VisualIntelligenceStage — sixth stage of the pipeline (M008/R047).

Runs the :class:`~vidscope.ports.ocr_engine.OcrEngine` port on every
:class:`Frame` already persisted by :class:`FramesStage`, writes
:class:`FrameText` rows via :attr:`UnitOfWork.frame_texts`, and
routes the OCR text through the :class:`~vidscope.ports.LinkExtractor`
port (M007) to append ``source='ocr'`` rows to :attr:`UnitOfWork.links`
carrying ``position_ms = frame.timestamp_ms``.

Positioned between :class:`FramesStage` and
:class:`MetadataExtractStage` in the canonical pipeline (see
:class:`~vidscope.domain.StageName`).

Resume-from-failure
-------------------
``is_satisfied`` returns True when at least one
:class:`FrameText` row exists for the video. Re-runs of
``vidscope add`` skip OCR entirely once it has succeeded.

Graceful degradation
--------------------
When the underlying OCR engine is unavailable (``rapidocr-onnxruntime``
not installed), :meth:`OcrEngine.extract_text` returns ``[]`` for every
call. If the engine also exposes a ``_unavailable`` sentinel flag set to
``True``, the stage emits a SKIPPED StageResult with a message pointing
at the optional install. This keeps the rest of the pipeline working on
environments without the vision extra.
"""

from __future__ import annotations

import logging
from pathlib import Path

from vidscope.domain import (
    ContentShape,
    FrameText,
    IndexingError,
    Link,
    StageName,
)
from vidscope.ports import (
    LinkExtractor,
    MediaStorage,
    PipelineContext,
    StageResult,
    UnitOfWork,
)
from vidscope.ports.ocr_engine import FaceCounter, OcrEngine

_logger = logging.getLogger(__name__)

__all__ = ["VisualIntelligenceStage", "classify_content_shape"]

_TALKING_HEAD_THRESHOLD: float = 0.4


def classify_content_shape(face_counts: list[int]) -> ContentShape:
    """Classify a video's visual form from a list of per-frame face counts.

    Rules (per M008 RESEARCH §2.4):

    - Empty list → :attr:`ContentShape.UNKNOWN` (no frames were
      processed, or OpenCV is not installed)
    - Every count is 0 → :attr:`ContentShape.BROLL`
    - ≥ 40% of frames have at least one face →
      :attr:`ContentShape.TALKING_HEAD`
    - Otherwise → :attr:`ContentShape.MIXED`

    A frame with 3 faces counts as a single "has-face" frame — we
    only measure presence, not intensity.
    """
    if not face_counts:
        return ContentShape.UNKNOWN
    frames_with_face = sum(1 for c in face_counts if c > 0)
    if frames_with_face == 0:
        return ContentShape.BROLL
    ratio = frames_with_face / len(face_counts)
    if ratio >= _TALKING_HEAD_THRESHOLD:
        return ContentShape.TALKING_HEAD
    return ContentShape.MIXED


class VisualIntelligenceStage:
    """Sixth stage — OCR every frame + thumbnail copy + content_shape.

    In a single pass over each frame:
    - Extracts text via :class:`OcrEngine` (R047)
    - Counts faces via :class:`FaceCounter` (R049)
    - After the loop: copies the middle frame to the canonical thumbnail
      key ``videos/{platform}/{platform_id}/thumb.jpg`` (R048)
    - Classifies :class:`ContentShape` from face counts (R049)
    - Persists both visual-metadata columns via
      :meth:`VideoRepository.update_visual_metadata` (R048+R049)
    """

    name: str = StageName.VISUAL_INTELLIGENCE.value

    def __init__(
        self,
        *,
        ocr_engine: OcrEngine,
        face_counter: FaceCounter,
        link_extractor: LinkExtractor,
        media_storage: MediaStorage,
        min_confidence: float = 0.5,
    ) -> None:
        self._ocr = ocr_engine
        self._face_counter = face_counter
        self._extractor = link_extractor
        self._media_storage = media_storage
        self._min_confidence = min_confidence

    # ------------------------------------------------------------------
    # Stage protocol
    # ------------------------------------------------------------------

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Return True when the stage's full output is in place:
        (a) at least one :class:`FrameText` row for the video,
        (b) ``videos.thumbnail_key`` is populated,
        (c) ``videos.content_shape`` is populated.

        Any missing piece forces re-execution. This guarantees a
        half-completed run (e.g. OCR succeeded but process died
        before face-count) eventually finishes on the next invocation.
        """
        if ctx.video_id is None:
            return False
        if not uow.frame_texts.has_any_for_video(ctx.video_id):
            return False
        video = uow.videos.get(ctx.video_id)
        if video is None:
            return False
        return (
            video.thumbnail_key is not None
            and video.content_shape is not None
        )

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Run OCR + face-count on each frame, copy thumbnail, persist results.

        Raises
        ------
        IndexingError
            When ``ctx.video_id`` is missing (ingest stage failed silently).
        """
        if ctx.video_id is None:
            raise IndexingError(
                "visual_intelligence stage requires ctx.video_id; "
                "ingest must run first"
            )

        frames = uow.frames.list_for_video(ctx.video_id)
        if not frames:
            return StageResult(
                skipped=True,
                message="no frames to OCR — frames stage produced nothing",
            )

        total_text_blocks = 0
        all_ocr_links: list[Link] = []
        frames_with_text = 0
        face_counts: list[int] = []

        for frame in frames:
            if frame.id is None:
                _logger.warning(
                    "visual_intelligence: frame without id for video %s, skipping",
                    ctx.video_id,
                )
                continue

            try:
                resolved = self._media_storage.resolve(frame.image_key)
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "visual_intelligence: failed to resolve %s for video %s: %s",
                    frame.image_key,
                    ctx.video_id,
                    exc,
                )
                continue

            frame_path = resolved if isinstance(resolved, Path) else Path(str(resolved))
            path_str = str(frame_path)

            # Face count (R049) — one call per frame. Returns 0 on
            # any failure (missing cv2, corrupt image, etc.).
            face_counts.append(self._face_counter.count_faces(path_str))

            # OCR (R047) — same file, same pass.
            lines = self._ocr.extract_text(path_str, min_confidence=self._min_confidence)
            if not lines:
                continue
            frames_with_text += 1

            frame_texts = [
                FrameText(
                    video_id=ctx.video_id,
                    frame_id=frame.id,
                    text=line.text,
                    confidence=line.confidence,
                    bbox=line.bbox,
                )
                for line in lines
            ]
            uow.frame_texts.add_many_for_frame(frame.id, ctx.video_id, frame_texts)
            total_text_blocks += len(frame_texts)

            concatenated = " ".join(line.text for line in lines)
            for raw in self._extractor.extract(concatenated, source="ocr"):
                all_ocr_links.append(
                    Link(
                        video_id=ctx.video_id,
                        url=raw["url"],
                        normalized_url=raw["normalized_url"],
                        source="ocr",
                        position_ms=frame.timestamp_ms,
                    )
                )

        # Persist all OCR-sourced links in one batched insert.
        persisted_links = uow.links.add_many_for_video(ctx.video_id, all_ocr_links)

        # --- R048: thumbnail copy from the middle frame ---
        thumbnail_key: str | None = None
        if frames:
            middle_idx = len(frames) // 2
            middle_frame = frames[middle_idx]
            try:
                source_path = self._media_storage.resolve(middle_frame.image_key)
                source_path = (
                    source_path
                    if isinstance(source_path, Path)
                    else Path(str(source_path))
                )
                suffix = source_path.suffix or ".jpg"
                platform_segment = ctx.platform.value if ctx.platform else "unknown"
                id_segment = str(ctx.platform_id or ctx.video_id)
                # T-M008-S03-01 defensive: reject path-traversal in id_segment
                # Check both forward-slash (Unix) and backslash (Windows, WR-02).
                if "/" in id_segment or "\\" in id_segment or ".." in id_segment:
                    _logger.warning(
                        "visual_intelligence: suspicious platform_id %r for video %s, "
                        "skipping thumbnail copy",
                        id_segment,
                        ctx.video_id,
                    )
                    thumbnail_key = None
                else:
                    thumb_key = f"videos/{platform_segment}/{id_segment}/thumb{suffix}"
                    # T-M008-S03-06 defensive: never store empty string
                    stored_key = self._media_storage.store(thumb_key, source_path)
                    thumbnail_key = stored_key if stored_key else None
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "visual_intelligence: thumbnail copy failed for video %s: %s",
                    ctx.video_id,
                    exc,
                )
                thumbnail_key = None

        # --- R049: content_shape classification ---
        shape = classify_content_shape(face_counts)

        # --- Persist both visual-metadata columns ---
        uow.videos.update_visual_metadata(
            ctx.video_id,
            thumbnail_key=thumbnail_key,
            content_shape=shape.value,
        )

        # Graceful-degradation detection (from S02-P01, preserved).
        engine_marked_unavailable = getattr(self._ocr, "_unavailable", False)
        if frames_with_text == 0 and engine_marked_unavailable:
            return StageResult(
                skipped=True,
                message=(
                    "OCR engine unavailable — rapidocr-onnxruntime "
                    "not installed. Install with: uv sync --extra vision"
                ),
            )

        if total_text_blocks == 0:
            return StageResult(
                message=(
                    f"OCR produced no text for {len(frames)} frames; "
                    f"content_shape={shape.value}, thumbnail={'yes' if thumbnail_key else 'no'}"
                )
            )

        return StageResult(
            message=(
                f"extracted {total_text_blocks} text block(s), "
                f"{len(persisted_links)} link(s) across {len(frames)} frame(s); "
                f"content_shape={shape.value}, thumbnail={'yes' if thumbnail_key else 'no'}"
            )
        )
