"""OCR + face-count ports (M008/R047, R049).

Both Protocols are pure — implementations must not raise on I/O
failures during normal operation (missing file, corrupt JPEG),
they return an empty list / zero instead. This keeps the
:class:`VisualIntelligenceStage` simple: no per-frame exception
handling, one pass over frames.

:class:`OcrEngine` implementations may raise :class:`OCRUnavailableError`
from a constructor or the first call ONLY when the underlying
library is not installed. The stage catches that error and
returns a SKIPPED :class:`StageResult`. See M008 RESEARCH §1.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["FaceCounter", "OcrEngine", "OcrLine"]


@dataclass(frozen=True, slots=True)
class OcrLine:
    """One line of OCR-extracted text.

    ``text`` is the raw string as reported by the engine — no
    canonicalisation. ``confidence`` is the engine's score in
    ``[0.0, 1.0]``; callers filter on a threshold before
    persisting. ``bbox`` is an opaque JSON string of the 4
    corner points (format: ``'[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]'``)
    or ``None`` when the engine does not expose bounding boxes.
    """

    text: str
    confidence: float
    bbox: str | None = None


@runtime_checkable
class OcrEngine(Protocol):
    """OCR engine port. Default implementation:
    :class:`~vidscope.adapters.vision.RapidOcrEngine`.
    """

    def extract_text(
        self, image_path: str, *, min_confidence: float = 0.5
    ) -> list[OcrLine]:
        """Return OCR lines above ``min_confidence`` found in
        the image at ``image_path``.

        Returns an empty list when no text is detected, when the
        file is missing or corrupt, or when the underlying OCR
        library is not installed. Never raises in normal
        operation — the stage interprets an empty list as "no
        on-screen text" and moves on.
        """
        ...


@runtime_checkable
class FaceCounter(Protocol):
    """Face-count port. Default implementation:
    :class:`~vidscope.adapters.vision.HaarcascadeFaceCounter`.
    """

    def count_faces(self, image_path: str) -> int:
        """Return the number of faces detected in the image at
        ``image_path``.

        Returns ``0`` when no face is detected, when the file is
        missing or corrupt, or when OpenCV is not installed. Never
        raises in normal operation.
        """
        ...
