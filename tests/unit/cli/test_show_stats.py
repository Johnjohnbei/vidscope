"""CLI tests for `vidscope show <id>` D-05 Stats section (M009/S04).

Tests the new Stats section rendered by show_command:
- Shows captured_at, view/like counters + velocity when latest_stats is present.
- Shows actionable message with refresh-stats command when no stats rows exist.

Separate from test_show_cmd.py which has pre-existing import errors.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vidscope.application.show_video import ShowVideoResult
from vidscope.domain import Platform, Video, VideoId, VideoStats
from vidscope.domain.values import PlatformId

runner = CliRunner()

_PATCH_CONTAINER = "vidscope.cli._support.build_container"
_PATCH_USE_CASE = "vidscope.cli.commands.show.ShowVideoUseCase"


def _make_video(vid: int = 1) -> Video:
    return Video(
        id=VideoId(vid),
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"p{vid}"),
        url=f"https://x.y/{vid}",
        title=f"Video {vid}",
    )


def _make_stats(vid: int = 1, view_count: int = 1000) -> VideoStats:
    return VideoStats(
        video_id=VideoId(vid),
        captured_at=datetime(2026, 1, 5, 12, 30, tzinfo=UTC),
        view_count=view_count,
        like_count=50,
        comment_count=10,
        repost_count=5,
        save_count=2,
    )


def _invoke_show(video_id: int, result: ShowVideoResult) -> object:
    """Invoke `vidscope show <video_id>` with a mocked use case."""
    mock_uc = MagicMock()
    mock_uc.execute.return_value = result
    container = MagicMock()

    with patch(_PATCH_CONTAINER, return_value=container), patch(
        _PATCH_USE_CASE, return_value=mock_uc
    ):
        from vidscope.cli.app import app

        return runner.invoke(app, ["show", str(video_id)])


# ---------------------------------------------------------------------------
# Test 1: Stats section shows when latest_stats is present
# ---------------------------------------------------------------------------


class TestShowStatsSection:
    def test_stats_section_present_when_latest_stats_set(self) -> None:
        """D-05: 'Stats' label appears in output when latest_stats is not None."""
        video = _make_video(1)
        stats = _make_stats(1, view_count=1000)
        result = ShowVideoResult(
            found=True,
            video=video,
            latest_stats=stats,
            views_velocity_24h=450.0,
        )
        cli_result = _invoke_show(1, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "Stats" in cli_result.output  # type: ignore[union-attr]

    def test_stats_section_shows_view_count(self) -> None:
        """D-05: view count appears in stats output."""
        video = _make_video(1)
        stats = _make_stats(1, view_count=5000)
        result = ShowVideoResult(
            found=True,
            video=video,
            latest_stats=stats,
            views_velocity_24h=100.0,
        )
        cli_result = _invoke_show(1, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "5000" in cli_result.output  # type: ignore[union-attr]

    def test_stats_section_shows_velocity(self) -> None:
        """D-05: velocity_24h appears in stats output when set."""
        video = _make_video(1)
        stats = _make_stats(1, view_count=1000)
        result = ShowVideoResult(
            found=True,
            video=video,
            latest_stats=stats,
            views_velocity_24h=450.0,
        )
        cli_result = _invoke_show(1, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        out = cli_result.output  # type: ignore[union-attr]
        assert "velocity_24h" in out.lower() or "450" in out

    def test_stats_section_shows_captured_at(self) -> None:
        """D-05: captured_at date appears in stats output."""
        video = _make_video(1)
        stats = _make_stats(1)
        result = ShowVideoResult(
            found=True,
            video=video,
            latest_stats=stats,
            views_velocity_24h=200.0,
        )
        cli_result = _invoke_show(1, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "2026-01-05" in cli_result.output  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Test 2: Actionable message when no stats rows (D-05)
# ---------------------------------------------------------------------------


class TestShowStatsActionableMessage:
    def test_actionable_message_when_no_stats(self) -> None:
        """D-05: 'refresh-stats <id>' appears when latest_stats is None."""
        video = _make_video(42)
        result = ShowVideoResult(
            found=True,
            video=video,
            latest_stats=None,
            views_velocity_24h=None,
        )
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "refresh-stats 42" in cli_result.output  # type: ignore[union-attr]

    def test_actionable_message_exit_zero(self) -> None:
        """Showing 'no stats' message must still exit 0 (not an error)."""
        video = _make_video(1)
        result = ShowVideoResult(
            found=True,
            video=video,
            latest_stats=None,
            views_velocity_24h=None,
        )
        cli_result = _invoke_show(1, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Test 3: velocity n/a message when single snapshot (< 2 rows)
# ---------------------------------------------------------------------------


class TestShowStatsSingleSnapshot:
    def test_velocity_na_when_single_snapshot(self) -> None:
        """D-05: 'n/a' appears for velocity when only 1 snapshot (velocity=None)."""
        video = _make_video(1)
        stats = _make_stats(1, view_count=100)
        result = ShowVideoResult(
            found=True,
            video=video,
            latest_stats=stats,
            views_velocity_24h=None,  # < 2 snapshots
        )
        cli_result = _invoke_show(1, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "n/a" in cli_result.output  # type: ignore[union-attr]

    def test_velocity_na_message_contains_refresh_hint(self) -> None:
        """n/a velocity message tells user to run refresh-stats again."""
        video = _make_video(7)
        stats = _make_stats(7)
        result = ShowVideoResult(
            found=True,
            video=video,
            latest_stats=stats,
            views_velocity_24h=None,
        )
        cli_result = _invoke_show(7, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "refresh-stats" in cli_result.output  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Test 4: ASCII-only output
# ---------------------------------------------------------------------------


class TestShowStatsAsciiOnly:
    def test_stats_output_is_ascii_safe(self) -> None:
        """Stats section must not contain Unicode glyphs."""
        video = _make_video(1)
        stats = _make_stats(1)
        result = ShowVideoResult(
            found=True,
            video=video,
            latest_stats=stats,
            views_velocity_24h=200.0,
        )
        cli_result = _invoke_show(1, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        for glyph in ["\u2713", "\u2717", "\u2192", "\u2190", "\u2014"]:
            assert glyph not in cli_result.output  # type: ignore[union-attr]
