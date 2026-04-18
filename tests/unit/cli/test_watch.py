"""CLI tests for `vidscope watch refresh` — combined watch+stats summary (M009/S03)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

runner = CliRunner()


def _make_watch_summary(*, new_videos: int = 0, accounts: int = 0) -> Any:
    from vidscope.application.watchlist import RefreshSummary

    return RefreshSummary(
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, tzinfo=UTC),
        accounts_checked=accounts,
        new_videos_ingested=new_videos,
        errors=(),
        per_account=(),
    )


def _make_stats_result(
    *, videos: int = 0, refreshed: int = 0, failed: int = 0, errors: tuple[str, ...] = ()
) -> Any:
    from vidscope.application.refresh_stats import RefreshStatsForWatchlistResult

    return RefreshStatsForWatchlistResult(
        accounts_checked=0,
        videos_checked=videos,
        stats_refreshed=refreshed,
        failed=failed,
        errors=errors,
    )


def _patch_watch(
    monkeypatch: Any,
    *,
    watch_summary: Any,
    stats_result: Any,
    stats_raises: Exception | None = None,
) -> None:
    """Patch watch.py so no real container / use cases are created."""
    import vidscope.cli.commands.watch as watch_mod

    class _WatchUc:
        def __init__(self, **kw: Any) -> None: ...

        def execute(self) -> Any:
            return watch_summary

    monkeypatch.setattr(watch_mod, "RefreshWatchlistUseCase", _WatchUc)

    class _StatsUc:
        def __init__(self, **kw: Any) -> None: ...

        def execute(self) -> Any:
            if stats_raises is not None:
                raise stats_raises
            return stats_result

    monkeypatch.setattr(watch_mod, "RefreshStatsForWatchlistUseCase", _StatsUc)

    class _RefreshStatsUc:
        def __init__(self, **kw: Any) -> None: ...

    monkeypatch.setattr(watch_mod, "RefreshStatsUseCase", _RefreshStatsUc)

    fake_container = MagicMock()
    fake_container.pipeline_runner = MagicMock()
    fake_container.downloader = MagicMock()
    fake_container.clock = MagicMock()
    fake_container.clock.now.return_value = datetime(2026, 1, 1, tzinfo=UTC)
    fake_container.unit_of_work = MagicMock()
    fake_container.stats_stage = MagicMock()
    monkeypatch.setattr(watch_mod, "acquire_container", lambda: fake_container)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_watch_refresh_shows_both_counters(monkeypatch: Any) -> None:
    """stdout must contain new_videos AND stats_refreshed counters."""
    _patch_watch(
        monkeypatch,
        watch_summary=_make_watch_summary(new_videos=2, accounts=1),
        stats_result=_make_stats_result(videos=5, refreshed=4, failed=1),
    )
    from vidscope.cli.app import app

    res = runner.invoke(app, ["watch", "refresh"])
    assert res.exit_code == 0, res.stdout
    out = res.stdout
    # new_videos counter visible
    assert "2" in out
    # refreshed counter visible
    assert "4" in out
    # videos checked visible
    assert "5" in out


def test_watch_refresh_empty_watchlist(monkeypatch: Any) -> None:
    """Zero accounts => exit 0 with both zero counters."""
    _patch_watch(
        monkeypatch,
        watch_summary=_make_watch_summary(new_videos=0, accounts=0),
        stats_result=_make_stats_result(),
    )
    from vidscope.cli.app import app

    res = runner.invoke(app, ["watch", "refresh"])
    assert res.exit_code == 0


def test_watch_refresh_resilient_to_stats_failure(monkeypatch: Any) -> None:
    """Stats step raising must NOT hide the watch summary; exit code stays 0."""
    _patch_watch(
        monkeypatch,
        watch_summary=_make_watch_summary(new_videos=1, accounts=1),
        stats_result=None,
        stats_raises=RuntimeError("catastrophic"),
    )
    from vidscope.cli.app import app

    res = runner.invoke(app, ["watch", "refresh"])
    assert res.exit_code == 0, res.stdout
    # Watch summary must still be visible
    assert "1" in res.stdout
    # Error from stats step must appear
    assert "catastrophic" in res.stdout or "stats error" in res.stdout.lower()


def test_watch_refresh_no_unicode_glyphs(monkeypatch: Any) -> None:
    """stdout must not contain Unicode arrows, checkmarks, or crosses."""
    _patch_watch(
        monkeypatch,
        watch_summary=_make_watch_summary(new_videos=0, accounts=0),
        stats_result=_make_stats_result(),
    )
    from vidscope.cli.app import app

    res = runner.invoke(app, ["watch", "refresh"])
    for glyph in ["\u2713", "\u2717", "\u2192", "\u2190"]:
        assert glyph not in res.stdout


def test_watch_refresh_calls_both_use_cases(monkeypatch: Any) -> None:
    """Both RefreshWatchlistUseCase and RefreshStatsForWatchlistUseCase must be invoked."""
    import vidscope.cli.commands.watch as watch_mod

    watch_called: list[bool] = []
    stats_called: list[bool] = []

    class _WatchUc:
        def __init__(self, **kw: Any) -> None: ...

        def execute(self) -> Any:
            watch_called.append(True)
            return _make_watch_summary(new_videos=0, accounts=0)

    class _StatsUc:
        def __init__(self, **kw: Any) -> None: ...

        def execute(self) -> Any:
            stats_called.append(True)
            return _make_stats_result()

    class _RefreshStatsUc:
        def __init__(self, **kw: Any) -> None: ...

    monkeypatch.setattr(watch_mod, "RefreshWatchlistUseCase", _WatchUc)
    monkeypatch.setattr(watch_mod, "RefreshStatsForWatchlistUseCase", _StatsUc)
    monkeypatch.setattr(watch_mod, "RefreshStatsUseCase", _RefreshStatsUc)

    fake_container = MagicMock()
    fake_container.clock.now.return_value = datetime(2026, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(watch_mod, "acquire_container", lambda: fake_container)

    from vidscope.cli.app import app

    res = runner.invoke(app, ["watch", "refresh"])
    assert res.exit_code == 0, res.stdout
    assert len(watch_called) == 1, "RefreshWatchlistUseCase.execute not called"
    assert len(stats_called) == 1, "RefreshStatsForWatchlistUseCase.execute not called"
