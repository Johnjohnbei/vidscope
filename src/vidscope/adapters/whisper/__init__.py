"""faster-whisper adapter package.

Implements the :class:`~vidscope.ports.pipeline.Transcriber` port by
wrapping ``faster_whisper.WhisperModel``. The faster-whisper import
is contained in this package — no other layer references it.
"""

from __future__ import annotations

from vidscope.adapters.whisper.transcriber import FasterWhisperTranscriber

__all__ = ["FasterWhisperTranscriber"]
