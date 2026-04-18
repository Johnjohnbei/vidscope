"""Unit tests for YtdlpStatsProbe.

All tests mock yt_dlp.YoutubeDL so no network calls are made.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from vidscope.adapters.ytdlp.ytdlp_stats_probe import YtdlpStatsProbe, _int_or_none


# ---------------------------------------------------------------------------
# _int_or_none helper (T-DATA-01)
# ---------------------------------------------------------------------------

class TestIntOrNone:
    def test_int_returns_int(self) -> None:
        assert _int_or_none(42) == 42

    def test_none_returns_none(self) -> None:
        assert _int_or_none(None) is None

    def test_float_returns_int(self) -> None:
        assert _int_or_none(3.7) == 3

    def test_bool_returns_none(self) -> None:
        # bool is a subclass of int — must be excluded (T-DATA-01)
        assert _int_or_none(True) is None
        assert _int_or_none(False) is None

    def test_str_returns_none(self) -> None:
        assert _int_or_none("1000") is None

    def test_dict_returns_none(self) -> None:
        assert _int_or_none({"count": 42}) is None

    def test_list_returns_none(self) -> None:
        assert _int_or_none([1, 2, 3]) is None

    def test_zero_returns_zero(self) -> None:
        assert _int_or_none(0) == 0


# ---------------------------------------------------------------------------
# YtdlpStatsProbe.probe_stats
# ---------------------------------------------------------------------------

_GOOD_INFO: dict = {
    "view_count": 10000,
    "like_count": 500,
    "repost_count": 20,
    "comment_count": 100,
    "save_count": 50,
    "title": "Test Video",
    "id": "abc123",
}


def _make_probe() -> YtdlpStatsProbe:
    return YtdlpStatsProbe(cookies_file=None)


class TestProbeStats:
    def test_returns_video_stats_on_success(self) -> None:
        """Happy path: yt-dlp returns a complete info dict."""
        probe = _make_probe()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = _GOOD_INFO

        with patch("vidscope.adapters.ytdlp.ytdlp_stats_probe.yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = probe.probe_stats("https://example.com/video")

        assert result is not None
        assert result.view_count == 10000
        assert result.like_count == 500
        assert result.repost_count == 20
        assert result.comment_count == 100
        assert result.save_count == 50
        assert result.id is None

    def test_captured_at_is_utc_aware(self) -> None:
        """D-01: captured_at must be UTC-aware."""
        probe = _make_probe()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = _GOOD_INFO

        with patch("vidscope.adapters.ytdlp.ytdlp_stats_probe.yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = probe.probe_stats("https://example.com/video")

        assert result is not None
        assert result.captured_at.tzinfo is not None
        assert result.captured_at.microsecond == 0  # truncated to second

    def test_captured_at_has_no_microseconds(self) -> None:
        """D-01: captured_at is truncated to second precision."""
        probe = _make_probe()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = _GOOD_INFO

        with patch("vidscope.adapters.ytdlp.ytdlp_stats_probe.yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = probe.probe_stats("https://example.com/video")

        assert result is not None
        assert result.captured_at.microsecond == 0

    def test_none_counters_preserved(self) -> None:
        """D-03: None counters in yt-dlp info stay None (no coercion to 0)."""
        probe = _make_probe()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "view_count": 5000,
            "like_count": None,
            "repost_count": None,
            "comment_count": None,
            "save_count": None,
        }

        with patch("vidscope.adapters.ytdlp.ytdlp_stats_probe.yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = probe.probe_stats("https://example.com/video")

        assert result is not None
        assert result.view_count == 5000
        assert result.like_count is None
        assert result.repost_count is None
        assert result.comment_count is None
        assert result.save_count is None

    def test_non_int_counters_become_none(self) -> None:
        """T-DATA-01: non-int values from platform become None."""
        probe = _make_probe()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "view_count": "not_a_number",
            "like_count": {"nested": True},
            "repost_count": True,  # bool — excluded
        }

        with patch("vidscope.adapters.ytdlp.ytdlp_stats_probe.yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = probe.probe_stats("https://example.com/video")

        assert result is not None
        assert result.view_count is None
        assert result.like_count is None
        assert result.repost_count is None

    def test_returns_none_on_exception(self) -> None:
        """T-PROBE-01: any yt-dlp exception returns None, never raises."""
        probe = _make_probe()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.side_effect = RuntimeError("network failure")

        with patch("vidscope.adapters.ytdlp.ytdlp_stats_probe.yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = probe.probe_stats("https://example.com/video")

        assert result is None

    def test_returns_none_when_info_is_none(self) -> None:
        """yt-dlp can return None for unavailable videos."""
        probe = _make_probe()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = None

        with patch("vidscope.adapters.ytdlp.ytdlp_stats_probe.yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = probe.probe_stats("https://example.com/video")

        assert result is None

    def test_returns_none_for_empty_url(self) -> None:
        """Empty URL returns None without calling yt-dlp."""
        probe = _make_probe()
        assert probe.probe_stats("") is None
        assert probe.probe_stats("   ") is None

    def test_uses_cookies_file_when_provided(self, tmp_path: object) -> None:
        """cookies_file is passed to yt-dlp options as a string path."""
        from pathlib import Path

        cookies = Path(str(tmp_path)) / "cookies.txt"  # type: ignore[arg-type]
        cookies.touch()
        probe = YtdlpStatsProbe(cookies_file=cookies)
        captured_options: dict = {}

        def fake_ydl_cls(opts: dict) -> MagicMock:
            captured_options.update(opts)
            mock = MagicMock()
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            mock.extract_info.return_value = _GOOD_INFO
            return mock

        with patch("vidscope.adapters.ytdlp.ytdlp_stats_probe.yt_dlp.YoutubeDL", side_effect=fake_ydl_cls):
            probe.probe_stats("https://example.com/video")

        assert "cookiefile" in captured_options
        assert captured_options["cookiefile"] == str(cookies)

    def test_repost_count_uses_ytdlp_field_name(self) -> None:
        """D-02: field name is 'repost_count', not 'share_count'."""
        probe = _make_probe()
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "view_count": 1000,
            "repost_count": 42,
            "share_count": 999,  # must be ignored
        }

        with patch("vidscope.adapters.ytdlp.ytdlp_stats_probe.yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = probe.probe_stats("https://example.com/video")

        assert result is not None
        assert result.repost_count == 42  # from repost_count, not share_count
