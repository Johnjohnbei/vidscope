"""CLI tests for vidscope explain <id>."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    Platform,
    PlatformId,
    SentimentLabel,
    Video,
    VideoId,
)

runner = CliRunner()


def _make_video(vid: int = 1) -> Video:
    return Video(
        id=VideoId(vid), platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"p{vid}"),
        url=f"https://y.be/{vid}",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _make_analysis(vid: int = 1, *, reasoning: str = "Clear tutorial about Python.") -> Analysis:
    return Analysis(
        video_id=VideoId(vid),
        provider="heuristic",
        language=Language.ENGLISH,
        keywords=("python", "code"),
        topics=("python",),
        score=72.0,
        summary="A Python tutorial",
        verticals=("tech", "ai"),
        information_density=70.0,
        actionability=85.0,
        novelty=40.0,
        production_quality=60.0,
        sentiment=SentimentLabel.POSITIVE,
        is_sponsored=False,
        content_type=ContentType.TUTORIAL,
        reasoning=reasoning,
    )


def _make_container(*, video: Video | None, analysis: Analysis | None) -> Any:
    class _UoW:
        def __init__(self) -> None:
            self.videos = MagicMock()
            self.videos.get = MagicMock(return_value=video)
            self.analyses = MagicMock()
            self.analyses.get_latest_for_video = MagicMock(return_value=analysis)

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    container = MagicMock()
    container.unit_of_work = lambda: _UoW()
    return container


class TestExplainCommand:
    def test_explain_happy_path_shows_reasoning_and_scores(self, monkeypatch) -> None:
        container = _make_container(video=_make_video(1), analysis=_make_analysis(1))
        import vidscope.cli.commands.explain as ex_mod
        monkeypatch.setattr(ex_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(app, ["explain", "1"])
        assert res.exit_code == 0, res.stdout
        # Reasoning text present
        assert "Clear tutorial" in res.stdout
        # Per-dimension scores rendered
        assert "information_density" in res.stdout
        assert "actionability" in res.stdout
        # Categorical fields
        assert "tutorial" in res.stdout.lower()
        assert "positive" in res.stdout.lower()

    def test_explain_missing_video_exit_nonzero(self, monkeypatch) -> None:
        container = _make_container(video=None, analysis=None)
        import vidscope.cli.commands.explain as ex_mod
        monkeypatch.setattr(ex_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(app, ["explain", "999"])
        assert res.exit_code != 0
        assert "no video" in res.stdout.lower() or "not found" in res.stdout.lower()

    def test_explain_video_without_analysis_exit_nonzero(self, monkeypatch) -> None:
        container = _make_container(video=_make_video(1), analysis=None)
        import vidscope.cli.commands.explain as ex_mod
        monkeypatch.setattr(ex_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(app, ["explain", "1"])
        assert res.exit_code != 0
        assert "no analysis" in res.stdout.lower()

    def test_explain_no_unicode_glyphs_in_source(self) -> None:
        """KNOWLEDGE.md: no unicode glyphs in CLI source (Windows cp1252)."""
        src = Path("src/vidscope/cli/commands/explain.py").read_text(encoding="utf-8")
        for glyph in ("\u2713", "\u2717", "\u2192", "\u2190", "\u2714", "\u2718"):
            assert glyph not in src, f"unicode glyph found: {glyph!r}"


class TestExplainAppHelp:
    def test_help_lists_explain(self) -> None:
        from vidscope.cli.app import app
        res = runner.invoke(app, ["--help"])
        assert res.exit_code == 0
        assert "explain" in res.stdout.lower()
