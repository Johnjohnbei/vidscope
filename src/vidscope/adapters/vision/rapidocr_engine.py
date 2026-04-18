"""RapidOCR-based OcrEngine adapter (M008/R047).

Wraps ``rapidocr-onnxruntime 1.4.x`` (CPU-only, ONNX) behind the
:class:`~vidscope.ports.ocr_engine.OcrEngine` protocol. Lazy-loads
the ONNX model on the first :meth:`extract_text` call so
constructor is cheap (~0ms, no network). Gracefully degrades when
the library is not installed — returns ``[]`` instead of raising.

See M008 RESEARCH §1.2 for the v1.4.x return-tuple shape.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from vidscope.ports.ocr_engine import OcrLine

_logger = logging.getLogger(__name__)

__all__ = ["RapidOcrEngine"]


class RapidOcrEngine:
    """OcrEngine implementation backed by rapidocr-onnxruntime 1.4.x."""

    def __init__(self) -> None:
        # Lazy: do NOT import or instantiate rapidocr here. The
        # ONNX model (~50 MB) downloads on first RapidOCR() call.
        self._engine: Any | None = None
        self._unavailable: bool = False

    def _get_engine(self) -> Any | None:
        """Return the underlying RapidOCR instance or ``None`` if
        unavailable. Caches the failure to avoid repeated
        ImportError on every frame.
        """
        if self._unavailable:
            return None
        if self._engine is not None:
            return self._engine
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415
        except ImportError:
            _logger.info(
                "rapidocr-onnxruntime not installed — OCR disabled. "
                "Install with: uv sync --extra vision"
            )
            self._unavailable = True
            return None
        self._engine = RapidOCR()
        return self._engine

    def extract_text(
        self, image_path: str, *, min_confidence: float = 0.5
    ) -> list[OcrLine]:
        """Run OCR on ``image_path`` and return filtered lines.

        Returns ``[]`` when: (a) rapidocr is not installed,
        (b) the file does not exist, (c) no text was detected,
        or (d) all detected text was below ``min_confidence``.
        """
        if not Path(image_path).exists():
            _logger.debug("OCR skipped: file missing %s", image_path)
            return []

        engine = self._get_engine()
        if engine is None:
            return []

        try:
            result, _elapse = engine(image_path)
        except Exception as exc:
            _logger.warning(
                "rapidocr failed on %s: %s (continuing with empty result)",
                image_path,
                exc,
            )
            return []

        if result is None:
            return []

        lines: list[OcrLine] = []
        for item in result:
            # v1.4.x shape: [[bbox_4pts], text, confidence]
            if len(item) < 3:
                continue
            bbox_raw, text_raw, conf_raw = item[0], item[1], item[2]
            try:
                confidence = float(conf_raw)
            except (TypeError, ValueError):
                continue
            if confidence < min_confidence:
                continue
            text = str(text_raw).strip()
            if not text:
                continue
            # Serialise bbox as JSON so the value remains opaque
            # in the domain (OcrLine.bbox: str | None).
            try:
                bbox = json.dumps(
                    [[float(p[0]), float(p[1])] for p in bbox_raw]
                )
            except (TypeError, ValueError, IndexError):
                bbox = None
            lines.append(OcrLine(text=text, confidence=confidence, bbox=bbox))
        return lines
