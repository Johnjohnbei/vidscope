"""OpenCV Haarcascade-based FaceCounter adapter (M008/R049).

Wraps ``cv2.CascadeClassifier`` with the bundled
``haarcascade_frontalface_default.xml`` behind the
:class:`~vidscope.ports.ocr_engine.FaceCounter` protocol. Lazy-
loads ``cv2`` on first :meth:`count_faces` call. Gracefully
degrades when ``opencv-python-headless`` is not installed or the
cascade file cannot be located — returns ``0``.

See M008 RESEARCH §2.3 for the detectMultiScale API.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

__all__ = ["HaarcascadeFaceCounter"]


class HaarcascadeFaceCounter:
    """FaceCounter implementation backed by OpenCV haarcascade."""

    def __init__(self) -> None:
        self._cascade: Any | None = None
        self._cv2: Any | None = None
        self._unavailable: bool = False

    def _load(self) -> tuple[Any, Any] | None:
        """Return (cv2 module, cascade instance) or ``None``."""
        if self._unavailable:
            return None
        if self._cv2 is not None and self._cascade is not None:
            return self._cv2, self._cascade
        try:
            import cv2  # noqa: PLC0415
        except ImportError:
            _logger.info(
                "opencv-python-headless not installed — face count disabled. "
                "Install with: uv sync --extra vision"
            )
            self._unavailable = True
            return None
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            if cascade.empty():
                _logger.warning("haarcascade file empty at %s", cascade_path)
                self._unavailable = True
                return None
        except (AttributeError, OSError) as exc:
            _logger.warning("failed to load haarcascade: %s", exc)
            self._unavailable = True
            return None
        self._cv2 = cv2
        self._cascade = cascade
        return cv2, cascade

    def count_faces(self, image_path: str) -> int:
        """Return the number of frontal faces in the image, or
        ``0`` when any step fails.
        """
        if not Path(image_path).exists():
            return 0
        loaded = self._load()
        if loaded is None:
            return 0
        cv2, cascade = loaded
        try:
            img = cv2.imread(image_path)
            if img is None:
                return 0
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
            )
        except Exception as exc:
            _logger.warning(
                "haarcascade failed on %s: %s (continuing with 0)",
                image_path,
                exc,
            )
            return 0
        # detectMultiScale returns np.ndarray shape (N, 4) or empty tuple
        try:
            return len(faces)
        except TypeError:
            return 0
