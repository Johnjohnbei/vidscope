"""CLI tests for `vidscope trending` command (M009/S04).

Pattern: CliRunner + monkeypatch on ListTrendingUseCase and acquire_container
so no real DB or container is needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

runner = CliRunner()


def _make_entries():
    from vidscope.application.list_trending import TrendingEntry
    from vidscope.domain import Platform

    return [
        TrendingEntry(
            video_id=1,
            platform=Platform.YOUTUBE,
            title="Alpha video",
            views_velocity_24h=1200.0,
            engagement_rate=0.05,
            last_captured_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            latest_view_count=10000,
            latest_like_count=500,
        ),
        TrendingEntry(
            video_id=2,
            platform=Platform.TIKTOK,
            title="Beta video",
            views_velocity_24h=500.0,
            engagement_rate=None,
            last_captured_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            latest_view_count=4000,
            latest_like_count=None,
        ),
    ]


def _patch_container(monkeypatch: pytest.MonkeyPatch, *, entries: list) -> None:
    import vidscope.cli.commands.trending as mod

    class _UC:
        def __init__(self, **kw: object) -> None:
            pass

        def execute(self, **kw: object) -> list:
            return entries

    monkeypatch.setattr(mod, "ListTrendingUseCase", _UC)
    monkeypatch.setattr(
        mod,
        "acquire_container",
        lambda: MagicMock(
            unit_of_work=MagicMock(),
            clock=MagicMock(now=lambda: datetime(2026, 1, 1, tzinfo=UTC)),
        ),
    )


# ---------------------------------------------------------------------------
# Test 1: --since required (D-04 — no silent default)
# ---------------------------------------------------------------------------


def test_trending_since_required() -> None:
    """D-04: --since is mandatory. Missing it must exit with non-zero code."""
    from vidscope.cli.app import app

    res = runner.invoke(app, ["trending"])
    assert res.exit_code != 0


# ---------------------------------------------------------------------------
# Test 2: happy path with --since 7d
# ---------------------------------------------------------------------------


def test_trending_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """trending --since 7d exits 0 and lists titles in output."""
    _patch_container(monkeypatch, entries=_make_entries())
    from vidscope.cli.app import app

    res = runner.invoke(app, ["trending", "--since", "7d"])
    assert res.exit_code == 0, res.stdout
    assert "Alpha video" in res.stdout
    assert "Beta video" in res.stdout


# ---------------------------------------------------------------------------
# Test 3: --limit 0 rejected (T-INPUT-01)
# ---------------------------------------------------------------------------


def test_trending_limit_zero_rejected() -> None:
    """--limit 0 must exit with non-zero code (T-INPUT-01)."""
    from vidscope.cli.app import app

    res = runner.invoke(app, ["trending", "--since", "7d", "--limit", "0"])
    assert res.exit_code != 0


# ---------------------------------------------------------------------------
# Test 4: invalid --since format rejected (T-INPUT-02)
# ---------------------------------------------------------------------------


def test_trending_invalid_since_format() -> None:
    """--since 1week must exit with non-zero code (strict N(h|d) parser)."""
    from vidscope.cli.app import app

    res = runner.invoke(app, ["trending", "--since", "1week"])
    assert res.exit_code != 0


# ---------------------------------------------------------------------------
# Test 5: invalid --platform rejected (T-INPUT-03)
# ---------------------------------------------------------------------------


def test_trending_invalid_platform() -> None:
    """--platform myspace must exit with non-zero code (T-INPUT-03)."""
    from vidscope.cli.app import app

    res = runner.invoke(app, ["trending", "--since", "7d", "--platform", "myspace"])
    assert res.exit_code != 0


# ---------------------------------------------------------------------------
# Test 6: empty results prints actionable message
# ---------------------------------------------------------------------------


def test_trending_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty result set prints 'No trending' message (exit 0)."""
    _patch_container(monkeypatch, entries=[])
    from vidscope.cli.app import app

    res = runner.invoke(app, ["trending", "--since", "7d"])
    assert res.exit_code == 0
    assert "no trending" in res.stdout.lower() or "No trending" in res.stdout


# ---------------------------------------------------------------------------
# Test 7: Table columns per D-04 spec
# ---------------------------------------------------------------------------


def test_trending_table_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Output table contains required columns: title, platform, velocity, engagement."""
    _patch_container(monkeypatch, entries=_make_entries())
    from vidscope.cli.app import app

    res = runner.invoke(app, ["trending", "--since", "7d"])
    assert res.exit_code == 0
    out = res.stdout.lower()
    assert "title" in out
    assert "platform" in out
    assert "velocity" in out
    assert "engagement" in out


# ---------------------------------------------------------------------------
# Test 8: ASCII-only output — no Unicode glyphs
# ---------------------------------------------------------------------------


def test_trending_no_unicode_glyphs(monkeypatch: pytest.MonkeyPatch) -> None:
    """stdout must not contain Unicode checkmarks, arrows, or other glyphs."""
    _patch_container(monkeypatch, entries=_make_entries())
    from vidscope.cli.app import app

    res = runner.invoke(app, ["trending", "--since", "7d"])
    for glyph in ["\u2713", "\u2717", "\u2192", "\u2190", "\u2714", "\u2718"]:
        assert glyph not in res.stdout


# ---------------------------------------------------------------------------
# Test 9: --platform and --min-velocity forwarded to use case
# ---------------------------------------------------------------------------


def test_trending_filters_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    """--platform youtube --min-velocity 100 --limit 5 exits 0."""
    _patch_container(monkeypatch, entries=_make_entries()[:1])
    from vidscope.cli.app import app

    res = runner.invoke(
        app,
        ["trending", "--since", "7d", "--platform", "youtube", "--min-velocity", "100", "--limit", "5"],
    )
    assert res.exit_code == 0
