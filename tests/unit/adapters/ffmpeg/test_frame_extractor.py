"""Unit tests for FfmpegFrameExtractor.

shutil.which and subprocess.run are monkeypatched so the real ffmpeg
binary is never invoked during unit tests.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from vidscope.adapters.ffmpeg import frame_extractor as fe_module
from vidscope.adapters.ffmpeg.frame_extractor import FfmpegFrameExtractor
from vidscope.domain import FrameExtractionError


@pytest.fixture()
def media_file(tmp_path: Path) -> Path:
    src = tmp_path / "video.mp4"
    src.write_bytes(b"fake video content")
    return src


class _FakeCompleted:
    """Stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = ""
        self.stderr = stderr


def _install_fake_ffmpeg(
    monkeypatch: pytest.MonkeyPatch,
    *,
    return_code: int = 0,
    stderr: str = "",
    create_frames: int = 5,
    raise_on_run: Exception | None = None,
) -> None:
    """Stub shutil.which + subprocess.run to simulate ffmpeg behavior."""
    monkeypatch.setattr(
        fe_module.shutil, "which", lambda _name: "/fake/ffmpeg"
    )

    def fake_run(cmd: list[str], **kwargs: Any) -> _FakeCompleted:
        if raise_on_run is not None:
            raise raise_on_run
        # The output template is the last argument: parse it to find
        # the destination dir and create fake frames there
        out_template = cmd[-1]
        out_dir = Path(out_template).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        for i in range(1, create_frames + 1):
            (out_dir / f"frame_{i:04d}.jpg").write_bytes(b"fake jpg")
        return _FakeCompleted(return_code, stderr)

    monkeypatch.setattr(fe_module.subprocess, "run", fake_run)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_extracts_expected_frame_count(
        self, monkeypatch: pytest.MonkeyPatch, media_file: Path, tmp_path: Path
    ) -> None:
        _install_fake_ffmpeg(monkeypatch, create_frames=8)
        out = tmp_path / "frames"
        extractor = FfmpegFrameExtractor()
        frames = extractor.extract_frames(str(media_file), str(out))
        assert len(frames) == 8
        for idx, frame in enumerate(frames):
            assert frame.timestamp_ms == idx * 5000  # default 0.2 fps
            assert "frame_" in frame.image_key
            assert frame.is_keyframe is False

    def test_caps_at_max_frames(
        self, monkeypatch: pytest.MonkeyPatch, media_file: Path, tmp_path: Path
    ) -> None:
        _install_fake_ffmpeg(monkeypatch, create_frames=50)
        extractor = FfmpegFrameExtractor()
        frames = extractor.extract_frames(
            str(media_file), str(tmp_path / "frames"), max_frames=10
        )
        assert len(frames) == 10

    def test_custom_fps_changes_timestamp_interval(
        self, monkeypatch: pytest.MonkeyPatch, media_file: Path, tmp_path: Path
    ) -> None:
        _install_fake_ffmpeg(monkeypatch, create_frames=4)
        extractor = FfmpegFrameExtractor(fps=1.0)  # 1 frame/sec
        frames = extractor.extract_frames(
            str(media_file), str(tmp_path / "frames")
        )
        assert frames[0].timestamp_ms == 0
        assert frames[1].timestamp_ms == 1000
        assert frames[2].timestamp_ms == 2000


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_missing_ffmpeg_raises(
        self, monkeypatch: pytest.MonkeyPatch, media_file: Path, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            fe_module.shutil, "which", lambda _name: None
        )
        with pytest.raises(FrameExtractionError, match="not found on PATH"):
            FfmpegFrameExtractor().extract_frames(
                str(media_file), str(tmp_path / "frames")
            )

    def test_missing_media_file_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            fe_module.shutil, "which", lambda _name: "/fake/ffmpeg"
        )
        with pytest.raises(FrameExtractionError, match="does not exist"):
            FfmpegFrameExtractor().extract_frames(
                str(tmp_path / "ghost.mp4"), str(tmp_path / "frames")
            )

    def test_non_zero_exit_raises(
        self, monkeypatch: pytest.MonkeyPatch, media_file: Path, tmp_path: Path
    ) -> None:
        _install_fake_ffmpeg(
            monkeypatch,
            return_code=1,
            stderr="Invalid data found when processing input",
            create_frames=0,
        )
        with pytest.raises(
            FrameExtractionError, match="Invalid data"
        ):
            FfmpegFrameExtractor().extract_frames(
                str(media_file), str(tmp_path / "frames")
            )

    def test_timeout_raises(
        self, monkeypatch: pytest.MonkeyPatch, media_file: Path, tmp_path: Path
    ) -> None:
        _install_fake_ffmpeg(
            monkeypatch,
            raise_on_run=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=60),
        )
        with pytest.raises(FrameExtractionError, match="timed out"):
            FfmpegFrameExtractor().extract_frames(
                str(media_file), str(tmp_path / "frames")
            )

    def test_os_error_raises(
        self, monkeypatch: pytest.MonkeyPatch, media_file: Path, tmp_path: Path
    ) -> None:
        _install_fake_ffmpeg(
            monkeypatch,
            raise_on_run=OSError("permission denied"),
        )
        with pytest.raises(FrameExtractionError, match="execute"):
            FfmpegFrameExtractor().extract_frames(
                str(media_file), str(tmp_path / "frames")
            )

    def test_no_frames_produced_raises(
        self, monkeypatch: pytest.MonkeyPatch, media_file: Path, tmp_path: Path
    ) -> None:
        """ffmpeg returns 0 but produces no .jpg files."""
        _install_fake_ffmpeg(monkeypatch, create_frames=0)
        with pytest.raises(
            FrameExtractionError, match="no frames were produced"
        ):
            FfmpegFrameExtractor().extract_frames(
                str(media_file), str(tmp_path / "frames")
            )
