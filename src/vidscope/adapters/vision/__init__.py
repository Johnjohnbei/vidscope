"""Vision adapter submodule for M008 (R047, R049).

Exports a :class:`RapidOcrEngine` (OcrEngine port) and a
:class:`HaarcascadeFaceCounter` (FaceCounter port). Both adapters
lazy-load their heavy deps (``rapidocr_onnxruntime``, ``cv2``) so
importing this package is cheap and safe even when the optional
``[vision]`` extra is not installed.

Import-linter contract ``vision-adapter-is-self-contained`` forbids
this package from importing any other adapter, infrastructure,
application, pipeline, CLI, or MCP module.
"""

from __future__ import annotations

from vidscope.adapters.vision.haarcascade_face_counter import (
    HaarcascadeFaceCounter,
)
from vidscope.adapters.vision.rapidocr_engine import RapidOcrEngine

__all__ = ["HaarcascadeFaceCounter", "RapidOcrEngine"]
