"""ffmpeg adapter package.

Implements the :class:`~vidscope.ports.pipeline.FrameExtractor` port
by shelling out to the ``ffmpeg`` binary. ffmpeg is the only place
in the codebase that calls a subprocess for media manipulation.
"""

from __future__ import annotations

from vidscope.adapters.ffmpeg.frame_extractor import FfmpegFrameExtractor

__all__ = ["FfmpegFrameExtractor"]
