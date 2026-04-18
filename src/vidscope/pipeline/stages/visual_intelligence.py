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
    """Sixth stage — OCR every frame + extract on-screen URLs."""

    name: str = StageName.VISUAL_INTELLIGENCE.value

    def __init__(
        self,
        *,
        ocr_engine: OcrEngine,
        link_extractor: LinkExtractor,
        media_storage: MediaStorage,
        min_confidence: float = 0.5,
    ) -> None:
        self._ocr = ocr_engine
        self._extractor = link_extractor
        self._media_storage = media_storage
        self._min_confidence = min_confidence

    # ------------------------------------------------------------------
    # Stage protocol
    # ------------------------------------------------------------------

    def is_satisfied(self, ctx: PipelineContext, uow: UnitOfWork) -> bool:
        """Return True when frame_texts already exist for this video."""
        if ctx.video_id is None:
            return False
        return uow.frame_texts.has_any_for_video(ctx.video_id)

    def execute(self, ctx: PipelineContext, uow: UnitOfWork) -> StageResult:
        """Run OCR on each frame, persist text, extract + persist links.

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
        # Track frames that received at least one OcrLine — used
        # for SKIPPED detection when the engine is unavailable.
        frames_with_text = 0

        for frame in frames:
            if frame.id is None:
                # Defensive: FramesStage persists via add_many which
                # populates ids; a None here would be a contract
                # violation upstream. Skip rather than fail.
                _logger.warning(
                    "visual_intelligence: frame without id for video %s, "
                    "skipping",
                    ctx.video_id,
                )
                continue

            try:
                resolved = self._media_storage.resolve(frame.image_key)
            except Exception as exc:
                _logger.warning(
                    "visual_intelligence: failed to resolve %s for video %s: %s",
                    frame.image_key,
                    ctx.video_id,
                    exc,
                )
                continue

            frame_path = resolved if isinstance(resolved, Path) else Path(str(resolved))
            lines = self._ocr.extract_text(
                str(frame_path), min_confidence=self._min_confidence
            )
            if not lines:
                continue
            frames_with_text += 1

            # Persist the text blocks for this frame. One UoW-scoped
            # insert per frame is fine — frames are at most 30 per
            # video so worst case is 30 small inserts inside one
            # transaction.
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
            uow.frame_texts.add_many_for_frame(
                frame.id, ctx.video_id, frame_texts
            )
            total_text_blocks += len(frame_texts)

            # Feed the concatenated text through LinkExtractor. Each
            # produced RawLink inherits position_ms from this frame.
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

        # Persist all OCR-sourced links in one batched insert. The
        # LinkRepository dedups by (normalized_url, source) within
        # the call — same URL across multiple frames becomes ONE
        # row (position_ms is the first-seen frame's timestamp).
        persisted_links = uow.links.add_many_for_video(
            ctx.video_id, all_ocr_links
        )

        # Graceful-degradation detection: if NO frame produced any
        # text, the OCR engine is either (a) unavailable/not installed
        # or (b) simply saw no text (valid B-roll case). We cannot
        # distinguish (a) from (b) purely from the result — the
        # OcrEngine port returns [] in both cases by contract. We
        # peek at a sentinel attribute (_unavailable) when present;
        # otherwise we report the empty result as a normal success.
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
                message=f"OCR produced no text for {len(frames)} frames"
            )

        return StageResult(
            message=(
                f"extracted {total_text_blocks} text block(s), "
                f"{len(persisted_links)} link(s) across {len(frames)} frame(s)"
            )
        )
