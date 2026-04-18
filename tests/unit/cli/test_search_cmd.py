"""Tests for `vidscope search` command — M010 facets.

Pattern: CliRunner + monkeypatch acquire_container so no real DB is needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

from vidscope.cli.app import app

runner = CliRunner()


def _make_m010_container(*, hits: list) -> MagicMock:
    class _UoW:
        def __init__(self) -> None:
            self.search_index = MagicMock()
            self.search_index.search = MagicMock(return_value=hits)
            self.analyses = MagicMock()
            self.analyses.list_by_filters = MagicMock(
                return_value=[1] if hits else []
            )

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    container = MagicMock()
    container.unit_of_work = lambda: _UoW()
    return container


class TestSearchCommandBaseline:
    def test_search_baseline_exit_ok(self, monkeypatch) -> None:
        """vidscope search cooking → exit 0."""
        container = _make_m010_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        result = runner.invoke(app, ["search", "cooking"])
        assert result.exit_code == 0

    def test_search_no_hits_shows_no_matches_message(self, monkeypatch) -> None:
        """Quand hits est vide → message 'No matches'."""
        container = _make_m010_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        result = runner.invoke(app, ["search", "cooking"])
        assert result.exit_code == 0
        assert "No matches" in result.output


class TestSearchM010Facets:
    """M010: --content-type, --min-actionability, --sponsored flags."""

    def _make_container(self, *, hits: list) -> Any:
        from unittest.mock import MagicMock

        class _UoW:
            def __init__(self) -> None:
                self.search_index = MagicMock()
                self.search_index.search = MagicMock(return_value=hits)
                self.analyses = MagicMock()
                self.analyses.list_by_filters = MagicMock(
                    return_value=[1] if hits else []
                )

            def __enter__(self) -> Any:
                return self

            def __exit__(self, *_: Any) -> None:
                return None

        container = MagicMock()
        container.unit_of_work = lambda: _UoW()
        return container

    def test_search_with_valid_content_type(self, monkeypatch) -> None:
        from dataclasses import dataclass

        @dataclass
        class _Hit:
            video_id: int = 1
            source: str = "transcript"
            rank: float = 0.9
            snippet: str = "..."

        container = self._make_container(hits=[_Hit()])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(
            app, ["search", "python", "--content-type", "tutorial"],
        )
        assert res.exit_code == 0, res.stdout

    def test_search_with_invalid_content_type_errors(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(
            app, ["search", "python", "--content-type", "podcast"],
        )
        assert res.exit_code != 0

    def test_search_with_min_actionability_valid(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)

        from vidscope.cli.app import app
        res = runner.invoke(
            app, ["search", "python", "--min-actionability", "70"],
        )
        assert res.exit_code == 0

    def test_search_min_actionability_negative_rejected(self) -> None:
        from vidscope.cli.app import app
        res = runner.invoke(
            app, ["search", "python", "--min-actionability", "-5"],
        )
        assert res.exit_code != 0

    def test_search_min_actionability_over_100_rejected(self) -> None:
        from vidscope.cli.app import app
        res = runner.invoke(
            app, ["search", "python", "--min-actionability", "150"],
        )
        assert res.exit_code != 0

    def test_search_sponsored_true(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        from vidscope.cli.app import app
        res = runner.invoke(app, ["search", "python", "--sponsored", "true"])
        assert res.exit_code == 0

    def test_search_sponsored_false(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        from vidscope.cli.app import app
        res = runner.invoke(app, ["search", "python", "--sponsored", "false"])
        assert res.exit_code == 0

    def test_search_sponsored_invalid(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        from vidscope.cli.app import app
        res = runner.invoke(app, ["search", "python", "--sponsored", "maybe"])
        assert res.exit_code != 0

    def test_search_combined_facets(self, monkeypatch) -> None:
        container = self._make_container(hits=[])
        import vidscope.cli.commands.search as s_mod
        monkeypatch.setattr(s_mod, "acquire_container", lambda: container)
        from vidscope.cli.app import app
        res = runner.invoke(app, [
            "search", "python",
            "--content-type", "tutorial",
            "--min-actionability", "70",
            "--sponsored", "false",
        ])
        assert res.exit_code == 0


