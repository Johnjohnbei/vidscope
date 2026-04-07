"""FfmpegFrameExtractor — ffmpeg implementation of FrameExtractor.

Wraps the ``ffmpeg`` CLI behind the FrameExtractor Protocol from
:mod:`vidscope.ports.pipeline`. Every ffmpeg failure is translated
into a typed
:class:`~vidscope.domain.errors.FrameExtractionError`.

Strategy
--------

The default extraction extracts a frame every 5 seconds (0.2 fps),
capped at ``max_frames``. This is a deliberate trade-off for short-form
content: a Reel of 30 seconds yields ~6 frames, a 60-second Short
yields ~12, a 90-second Reel yields ~18 — well below the 30-frame
cap. Long-form videos (which are out of scope per D026) get capped.

Frames are written to a caller-provided ``output_dir`` using ffmpeg's
output template ``frame_%04d.jpg`` so the resulting filenames sort
lexicographically by extraction order.

Single subprocess boundary
--------------------------

ffmpeg is invoked exactly once per extract_frames call. We do NOT
chain multiple ffmpeg invocations or pipe between processes — that
adds Windows quoting headaches and makes the error path harder to
debug. One subprocess, one timeout, one stderr capture.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Final

from vidscope.domain import Frame, FrameExtractionError, VideoId

__all__ = ["FfmpegFrameExtractor"]


# 0.2 fps = one frame every 5 seconds. Tuned for short-form vertical
# content (D026) where 6-18 frames per video is the sweet spot.
_DEFAULT_FPS: Final[float] = 0.2

# Per-call timeout for the ffmpeg subprocess. Extracting a few frames
# from a short video should never take more than 30s; if it does, the
# input is probably broken or ffmpeg is hung.
_FFMPEG_TIMEOUT_SECONDS: Final[float] = 60.0

_INSTALL_REMEDIATION: Final[str] = (
    "Install ffmpeg:\n"
    "  - Windows: `winget install Gyan.FFmpeg`\n"
    "  - macOS:   `brew install ffmpeg`\n"
    "  - Linux:   `sudo apt install ffmpeg` or your distro equivalent\n"
    "Then verify with `vidscope doctor`."
)


class FfmpegFrameExtractor:
    """FrameExtractor port implementation backed by the ffmpeg CLI.

    Parameters
    ----------
    fps:
        Frames per second to extract. Default ``0.2`` (one frame
        every 5 seconds). Lower values mean fewer frames per video.
    timeout_seconds:
        Per-call subprocess timeout. Default ``60.0`` seconds.
    """

    def __init__(
        self,
        *,
        fps: float = _DEFAULT_FPS,
        timeout_seconds: float = _FFMPEG_TIMEOUT_SECONDS,
    ) -> None:
        self._fps = fps
        self._timeout = timeout_seconds

    def extract_frames(
        self,
        media_path: str,
        output_dir: str,
        *,
        max_frames: int = 30,
    ) -> list[Frame]:
        """Extract up to ``max_frames`` frames from ``media_path`` and
        return Frame entities with timestamps.

        Raises
        ------
        FrameExtractionError
            On any ffmpeg failure (binary missing, input corrupt,
            timeout, non-zero exit). Always retryable=False because
            extraction failures don't self-heal.
        """
        binary = shutil.which("ffmpeg")
        if binary is None:
            raise FrameExtractionError(
                "ffmpeg binary not found on PATH.\n" + _INSTALL_REMEDIATION
            )

        source = Path(media_path)
        if not source.exists():
            raise FrameExtractionError(
                f"media file does not exist: {media_path!r}"
            )

        dest = Path(output_dir)
        dest.mkdir(parents=True, exist_ok=True)

        cmd = [
            binary,
            "-y",  # overwrite existing
            "-loglevel", "error",
            "-i", str(source),
            "-vf", f"fps={self._fps}",
            "-vframes", str(max_frames),
            "-q:v", "3",  # JPEG quality 3 (high) — small files, good detail
            str(dest / "frame_%04d.jpg"),
        ]

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise FrameExtractionError(
                f"ffmpeg timed out after {self._timeout:.0f}s on {media_path!r}",
                cause=exc,
            ) from exc
        except OSError as exc:
            raise FrameExtractionError(
                f"failed to execute ffmpeg: {exc}",
                cause=exc,
            ) from exc

        if completed.returncode != 0:
            stderr_tail = completed.stderr.strip()[-500:]
            raise FrameExtractionError(
                f"ffmpeg exited with code {completed.returncode}: {stderr_tail}"
            )

        # Glob the output dir for the extracted frames, sorted by name
        # (ffmpeg's %04d template guarantees lexicographic == temporal).
        files = sorted(dest.glob("frame_*.jpg"))
        if not files:
            raise FrameExtractionError(
                f"ffmpeg succeeded but no frames were produced in {dest}"
            )

        files = files[:max_frames]
        interval_ms = int(1000.0 / self._fps)

        return [
            Frame(
                video_id=VideoId(0),  # placeholder, stage fills the real id
                image_key=str(file_path),  # local path; stage will copy + rekey
                timestamp_ms=index * interval_ms,
                is_keyframe=False,
            )
            for index, file_path in enumerate(files)
        ]
