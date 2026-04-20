"""Unit tests for _detect_media_type_and_paths in YtdlpDownloader."""

from __future__ import annotations

from pathlib import Path

import pytest

from vidscope.adapters.ytdlp.downloader import _detect_media_type_and_paths
from vidscope.domain import MediaType, PlatformId


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file(tmp_path: Path, name: str) -> Path:
    """Create a real file under tmp_path and return its Path."""
    p = tmp_path / name
    p.write_bytes(b"fake content")
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDetectMediaTypeAndPaths:
    def test_single_mp4_returns_video(self, tmp_path: Path) -> None:
        media_file = _make_file(tmp_path, "abc123.mp4")
        info = {
            "requested_downloads": [{"filepath": str(media_file)}],
        }
        media_type, paths = _detect_media_type_and_paths(
            info, tmp_path, PlatformId("abc123")
        )
        assert media_type is MediaType.VIDEO
        assert paths == [media_file]

    def test_single_jpg_returns_image(self, tmp_path: Path) -> None:
        media_file = _make_file(tmp_path, "abc123.jpg")
        info = {
            "requested_downloads": [{"filepath": str(media_file)}],
        }
        media_type, paths = _detect_media_type_and_paths(
            info, tmp_path, PlatformId("abc123")
        )
        assert media_type is MediaType.IMAGE
        assert paths == [media_file]

    def test_single_webp_returns_image(self, tmp_path: Path) -> None:
        media_file = _make_file(tmp_path, "abc123.webp")
        info = {
            "requested_downloads": [{"filepath": str(media_file)}],
        }
        media_type, paths = _detect_media_type_and_paths(
            info, tmp_path, PlatformId("abc123")
        )
        assert media_type is MediaType.IMAGE

    def test_three_requested_downloads_returns_carousel(
        self, tmp_path: Path
    ) -> None:
        files = [_make_file(tmp_path, f"slide_{i}.jpg") for i in range(3)]
        info = {
            "requested_downloads": [
                {"filepath": str(f)} for f in files
            ],
        }
        media_type, paths = _detect_media_type_and_paths(
            info, tmp_path, PlatformId("car1")
        )
        assert media_type is MediaType.CAROUSEL
        assert len(paths) == 3
        assert set(paths) == set(files)

    def test_two_requested_downloads_returns_carousel(
        self, tmp_path: Path
    ) -> None:
        files = [_make_file(tmp_path, f"slide_{i}.jpg") for i in range(2)]
        info = {
            "requested_downloads": [
                {"filepath": str(f)} for f in files
            ],
        }
        media_type, paths = _detect_media_type_and_paths(
            info, tmp_path, PlatformId("car2")
        )
        assert media_type is MediaType.CAROUSEL
        assert len(paths) == 2

    def test_no_requested_downloads_falls_back_to_glob(
        self, tmp_path: Path
    ) -> None:
        media_file = _make_file(tmp_path, "vid99.mp4")
        info: dict = {}  # no requested_downloads, no _filename
        media_type, paths = _detect_media_type_and_paths(
            info, tmp_path, PlatformId("vid99")
        )
        assert media_type is MediaType.VIDEO
        assert paths == [media_file]

    def test_no_file_found_returns_video_empty_list(
        self, tmp_path: Path
    ) -> None:
        info: dict = {}
        media_type, paths = _detect_media_type_and_paths(
            info, tmp_path, PlatformId("ghost")
        )
        assert media_type is MediaType.VIDEO
        assert paths == []

    def test_legacy_filename_field_used_as_fallback(
        self, tmp_path: Path
    ) -> None:
        media_file = _make_file(tmp_path, "legacy.mp4")
        info = {"_filename": str(media_file)}
        media_type, paths = _detect_media_type_and_paths(
            info, tmp_path, PlatformId("legacy")
        )
        assert media_type is MediaType.VIDEO
        assert paths == [media_file]
