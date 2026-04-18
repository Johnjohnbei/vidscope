"""Tests for `vidscope search` command — M011/S03 new facets (R058).

Uses CliRunner with a monkeypatched container that provides all 4 new
repo attributes (video_tracking, tags, collections) so the use case
can do AND-intersection without a real DB.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

from vidscope.cli.app import app

runner = CliRunner()


def _make_m011_container(*, hits: list) -> Any:
    """Container with all M011 repos (video_tracking, tags, collections)."""
    class _UoW:
        def __init__(self) -> None:
            self.search_index = MagicMock()
            self.search_index.search = MagicMock(return_value=hits)
            self.analyses = MagicMock()
            self.analyses.list_by_filters = MagicMock(return_value=[])
            self.video_tracking = MagicMock()
            self.video_tracking.list_by_status = MagicMock(return_value=[])
            self.video_tracking.list_starred = MagicMock(return_value=[])
            self.tags = MagicMock()
            self.tags.list_video_ids_for_tag = MagicMock(return_value=[])
            self.collections = MagicMock()
            self.collections.list_video_ids_for_collection = MagicMock(return_value=[])

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    container = MagicMock()
    container.unit_of_work = lambda: _UoW()
    return container


class TestSearchCmdM011:
    def test_help_lists_new_options(self) -> None:
        r = runner.invoke(app, ["search", "--help"])
        assert r.exit_code == 0
        for opt in ("--status", "--starred", "--tag", "--collection"):
            assert opt in r.output, f"missing option {opt!r} in help output"

    def test_invalid_status_fails(self, monkeypatch) -> None:
        container = _make_m011_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        r = runner.invoke(app, ["search", "q", "--status", "bogus"])
        assert r.exit_code != 0

    def test_valid_status_runs(self, monkeypatch) -> None:
        container = _make_m011_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        r = runner.invoke(app, ["search", "q", "--status", "saved"])
        assert r.exit_code == 0

    def test_starred_flag(self, monkeypatch) -> None:
        container = _make_m011_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        r1 = runner.invoke(app, ["search", "q", "--starred"])
        assert r1.exit_code == 0
        r2 = runner.invoke(app, ["search", "q", "--unstarred"])
        assert r2.exit_code == 0

    def test_tag_and_collection(self, monkeypatch) -> None:
        container = _make_m011_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        r = runner.invoke(
            app,
            ["search", "q", "--tag", "Idea", "--collection", "MyCol"],
        )
        assert r.exit_code == 0

    def test_all_facets_combined(self, monkeypatch) -> None:
        container = _make_m011_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        r = runner.invoke(
            app,
            [
                "search", "q",
                "--content-type", "tutorial",
                "--min-actionability", "50",
                "--sponsored", "false",
                "--status", "saved",
                "--starred",
                "--tag", "idea",
                "--collection", "MyCol",
            ],
        )
        assert r.exit_code == 0

    def test_status_all_valid_values_pass(self, monkeypatch) -> None:
        """All 6 TrackingStatus values should parse without error."""
        container = _make_m011_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        for status in ("new", "reviewed", "saved", "actioned", "ignored", "archived"):
            r = runner.invoke(app, ["search", "q", "--status", status])
            assert r.exit_code == 0, f"status={status!r} failed: {r.output}"
