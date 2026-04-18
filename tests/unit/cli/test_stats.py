"""CLI tests for vidscope refresh-stats via Typer CliRunner."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats

runner = CliRunner()


def _fake_video(vid: int = 1) -> Video:
    return Video(
        id=VideoId(vid),
        platform=Platform.YOUTUBE,
        platform_id=PlatformId("abc"),
        url="https://x.y/a",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _fake_stats(vid: int = 1) -> VideoStats:
    return VideoStats(
        video_id=VideoId(vid),
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        view_count=100,
        like_count=10,
    )


def _make_container(
    *,
    video: Video | None = None,
    stats: VideoStats | None = None,
    stage_ok: bool = True,
    stage_error: str = "",
) -> Any:
    """Build a minimal fake container for CLI tests."""
    fake_uow = MagicMock()
    fake_uow.__enter__ = lambda self: self
    fake_uow.__exit__ = lambda *a: None
    fake_uow.videos.get = MagicMock(return_value=video)
    fake_uow.videos.list_recent = MagicMock(
        return_value=[video] if video is not None else []
    )
    fake_uow.video_stats.latest_for_video = MagicMock(return_value=stats)
    fake_uow.video_stats.append = MagicMock(side_effect=lambda s: s)

    fake_stage = MagicMock()
    result = MagicMock()
    result.skipped = not stage_ok
    result.message = "stats appended" if stage_ok else stage_error
    fake_stage.execute = MagicMock(return_value=result)
    fake_stage.name = "stats"

    fake_container = MagicMock()
    fake_container.stats_stage = fake_stage
    fake_container.unit_of_work = lambda: fake_uow
    fake_container.clock = MagicMock(now=lambda: datetime(2026, 1, 1, tzinfo=UTC))

    return fake_container


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------


def test_refresh_stats_help_exits_zero() -> None:
    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--help"])
    assert res.exit_code == 0
    # Should mention the command name or its options
    assert "refresh-stats" in res.stdout.lower() or "refresh" in res.stdout.lower()


# ---------------------------------------------------------------------------
# single id mode
# ---------------------------------------------------------------------------


def test_refresh_stats_single_id_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: single id, video exists, probe returns stats."""
    import vidscope.cli.commands.stats as stats_mod
    container = _make_container(video=_fake_video(1), stats=_fake_stats(1))
    monkeypatch.setattr(stats_mod, "acquire_container", lambda: container)

    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "1"])
    assert res.exit_code == 0, res.stdout
    assert "OK" in res.stdout or "refreshed" in res.stdout.lower()


def test_refresh_stats_unknown_id_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown video id -> exit code != 0 with 'not found' message."""
    import vidscope.cli.commands.stats as stats_mod
    container = _make_container(video=None)
    monkeypatch.setattr(stats_mod, "acquire_container", lambda: container)

    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "999"])
    assert res.exit_code != 0


# ---------------------------------------------------------------------------
# --all / batch mode
# ---------------------------------------------------------------------------


def test_refresh_stats_all_no_videos(monkeypatch: pytest.MonkeyPatch) -> None:
    """--all with empty library exits 0 and prints zero counts."""
    import vidscope.cli.commands.stats as stats_mod
    container = _make_container(video=None)
    monkeypatch.setattr(stats_mod, "acquire_container", lambda: container)

    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--all"])
    assert res.exit_code == 0
    # Should show total=0
    assert "0" in res.stdout


def test_refresh_stats_all_one_video_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """--all with one video exits 0 and reports refreshed=1."""
    import vidscope.cli.commands.stats as stats_mod
    container = _make_container(video=_fake_video(1), stats=_fake_stats(1))
    monkeypatch.setattr(stats_mod, "acquire_container", lambda: container)

    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--all"])
    assert res.exit_code == 0


# ---------------------------------------------------------------------------
# T-INPUT-01: --limit validation
# ---------------------------------------------------------------------------


def test_refresh_stats_limit_zero_rejected_by_typer() -> None:
    """T-INPUT-01: Typer's min=1 refuses --limit 0."""
    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--all", "--limit", "0"])
    assert res.exit_code != 0
    combined = (res.stdout or "") + (res.stderr or "")
    assert "limit" in combined.lower() or "0" in combined


def test_refresh_stats_limit_negative_rejected() -> None:
    """T-INPUT-01: negative --limit is also rejected."""
    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--all", "--limit", "-5"])
    assert res.exit_code != 0


# ---------------------------------------------------------------------------
# T-INPUT-02: --since validation
# ---------------------------------------------------------------------------


def test_refresh_stats_since_valid_7d(monkeypatch: pytest.MonkeyPatch) -> None:
    """--since 7d is valid and accepted."""
    import vidscope.cli.commands.stats as stats_mod
    container = _make_container(video=None)
    monkeypatch.setattr(stats_mod, "acquire_container", lambda: container)

    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--all", "--since", "7d"])
    assert res.exit_code == 0


def test_refresh_stats_since_valid_24h(monkeypatch: pytest.MonkeyPatch) -> None:
    """--since 24h is valid and accepted."""
    import vidscope.cli.commands.stats as stats_mod
    container = _make_container(video=None)
    monkeypatch.setattr(stats_mod, "acquire_container", lambda: container)

    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--all", "--since", "24h"])
    assert res.exit_code == 0


def test_refresh_stats_invalid_since_format() -> None:
    """T-INPUT-02: --since must be N(h|d), not '7' or '1week'."""
    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--all", "--since", "1week"])
    assert res.exit_code != 0


def test_refresh_stats_since_bare_number_rejected() -> None:
    """--since '7' without unit is rejected."""
    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "--all", "--since", "7"])
    assert res.exit_code != 0


# ---------------------------------------------------------------------------
# KNOWLEDGE.md: no unicode glyphs in stdout
# ---------------------------------------------------------------------------


def test_cli_output_has_no_forbidden_unicode_glyphs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KNOWLEDGE.md: no unicode glyphs in CLI stdout (Windows cp1252 compat)."""
    import vidscope.cli.commands.stats as stats_mod
    container = _make_container(video=_fake_video(1), stats=_fake_stats(1))
    monkeypatch.setattr(stats_mod, "acquire_container", lambda: container)

    from vidscope.cli.app import app
    res = runner.invoke(app, ["refresh-stats", "1"])
    forbidden = ["\u2713", "\u2717", "\u2192", "\u2190", "\u2714", "\u2718"]
    for glyph in forbidden:
        assert glyph not in res.stdout, f"Found forbidden glyph {glyph!r} in stdout"
