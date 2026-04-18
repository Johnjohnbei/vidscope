"""Tests for `vidscope search` command — M007/S04-P01 facets.

Pattern: CliRunner + mock build_container so no real DB is needed.
The use case is replaced by a MagicMock whose execute() returns a
controlled SearchLibraryResult.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vidscope.cli.app import app
from vidscope.domain import VideoId
from vidscope.ports.pipeline import SearchResult

runner = CliRunner()

_PATCH = "vidscope.cli._support.build_container"


def _make_hit(video_id: int, source: str = "transcript", rank: float = 1.0) -> SearchResult:
    return SearchResult(
        video_id=VideoId(video_id),
        source=source,
        snippet="test snippet",
        rank=rank,
    )


def _make_container(hits: list[SearchResult] | None = None) -> MagicMock:
    """Return a mock container whose SearchLibraryUseCase returns given hits."""
    from vidscope.application.search_library import SearchLibraryResult

    mock_uc = MagicMock()
    mock_uc.execute.return_value = SearchLibraryResult(
        query="cooking",
        hits=tuple(hits or []),
    )

    container = MagicMock()
    # The command instantiates SearchLibraryUseCase directly — we need to
    # patch at the class level to intercept the constructor call.
    return container


class TestSearchCommandBaseline:
    def test_search_baseline_exit_ok(self, tmp_path: object) -> None:
        """vidscope search cooking → exit 0."""
        from vidscope.application.search_library import SearchLibraryResult

        mock_uc_instance = MagicMock()
        mock_uc_instance.execute.return_value = SearchLibraryResult(
            query="cooking", hits=()
        )

        container = MagicMock()
        container.unit_of_work = MagicMock()

        with patch(_PATCH, return_value=container), patch(
            "vidscope.cli.commands.search.SearchLibraryUseCase",
            return_value=mock_uc_instance,
        ):
            result = runner.invoke(app, ["search", "cooking"])

        assert result.exit_code == 0

    def test_search_no_hits_shows_no_matches_message(self) -> None:
        """Quand hits est vide → message 'No matches'."""
        from vidscope.application.search_library import SearchLibraryResult

        mock_uc = MagicMock()
        mock_uc.execute.return_value = SearchLibraryResult(query="cooking", hits=())
        container = MagicMock()

        with patch(_PATCH, return_value=container), patch(
            "vidscope.cli.commands.search.SearchLibraryUseCase", return_value=mock_uc
        ):
            result = runner.invoke(app, ["search", "cooking"])

        assert result.exit_code == 0
        assert "No matches" in result.output


class TestSearchFacetOptions:
    """Tests that facet CLI options are wired to use case kwargs."""

    def _invoke_search_with_mock(
        self, args: list[str], hits: list[SearchResult] | None = None
    ) -> tuple[object, MagicMock]:
        from vidscope.application.search_library import SearchLibraryResult

        mock_uc = MagicMock()
        mock_uc.execute.return_value = SearchLibraryResult(
            query="", hits=tuple(hits or [])
        )
        container = MagicMock()

        with patch(_PATCH, return_value=container), patch(
            "vidscope.cli.commands.search.SearchLibraryUseCase", return_value=mock_uc
        ):
            result = runner.invoke(app, args)

        return result, mock_uc

    def test_hashtag_option_passed_to_execute(self) -> None:
        """--hashtag recipe → use case.execute(hashtag='recipe')."""
        result, mock_uc = self._invoke_search_with_mock(
            ["search", "cooking", "--hashtag", "recipe"]
        )
        assert result.exit_code == 0
        call_kwargs = mock_uc.execute.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("hashtag") == "recipe"

    def test_mention_option_passed_to_execute(self) -> None:
        """--mention @alice → use case.execute(mention='@alice')."""
        result, mock_uc = self._invoke_search_with_mock(
            ["search", "cooking", "--mention", "@alice"]
        )
        assert result.exit_code == 0
        call_kwargs = mock_uc.execute.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("mention") == "@alice"

    def test_has_link_flag_passed_to_execute(self) -> None:
        """--has-link → use case.execute(has_link=True)."""
        result, mock_uc = self._invoke_search_with_mock(
            ["search", "cooking", "--has-link"]
        )
        assert result.exit_code == 0
        call_kwargs = mock_uc.execute.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("has_link") is True

    def test_music_track_option_passed_to_execute(self) -> None:
        """--music-track 'Original sound' → use case.execute(music_track=...)."""
        result, mock_uc = self._invoke_search_with_mock(
            ["search", "cooking", "--music-track", "Original sound"]
        )
        assert result.exit_code == 0
        call_kwargs = mock_uc.execute.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("music_track") == "Original sound"

    def test_and_facets_both_passed_to_execute(self) -> None:
        """search cooking --hashtag recipe --has-link → execute appele avec les deux."""
        result, mock_uc = self._invoke_search_with_mock(
            ["search", "cooking", "--hashtag", "recipe", "--has-link"]
        )
        assert result.exit_code == 0
        call_kwargs = mock_uc.execute.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("hashtag") == "recipe"
        assert call_kwargs.kwargs.get("has_link") is True


class TestSearchHelpOutput:
    def test_search_help_shows_facet_options(self) -> None:
        """vidscope search --help affiche --hashtag, --has-link."""
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "--hashtag" in result.output
        assert "--has-link" in result.output


# ---------------------------------------------------------------------------
# M008 — --on-screen-text flag
# ---------------------------------------------------------------------------


class TestOnScreenTextFlag:
    def _invoke_search_with_mock(
        self, args: list[str], hits: list | None = None
    ) -> tuple[object, object]:
        from vidscope.application.search_library import SearchLibraryResult

        mock_uc = MagicMock()
        mock_uc.execute.return_value = SearchLibraryResult(
            query="", hits=tuple(hits or [])
        )
        container = MagicMock()

        with patch(_PATCH, return_value=container), patch(
            "vidscope.cli.commands.search.SearchLibraryUseCase", return_value=mock_uc
        ):
            result = runner.invoke(app, args)

        return result, mock_uc

    def test_on_screen_text_flag_forwarded_to_execute(self) -> None:
        """--on-screen-text promo → use case.execute(on_screen_text='promo')."""
        result, mock_uc = self._invoke_search_with_mock(
            ["search", "--on-screen-text", "promo", ""]
        )
        assert result.exit_code == 0  # type: ignore[union-attr]
        call_kwargs = mock_uc.execute.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("on_screen_text") == "promo"

    def test_on_screen_text_facet_rendered_in_header(self) -> None:
        """--on-screen-text promo → output contient 'on-screen=promo'."""
        from vidscope.application.search_library import SearchLibraryResult
        from vidscope.domain import VideoId
        from vidscope.ports.pipeline import SearchResult

        hit = SearchResult(
            video_id=VideoId(1), source="video", snippet="Video 1", rank=1.0
        )
        mock_uc = MagicMock()
        mock_uc.execute.return_value = SearchLibraryResult(
            query="", hits=(hit,)
        )
        container = MagicMock()

        with patch(_PATCH, return_value=container), patch(
            "vidscope.cli.commands.search.SearchLibraryUseCase", return_value=mock_uc
        ):
            result = runner.invoke(app, ["search", "--on-screen-text", "promo", ""])

        assert result.exit_code == 0  # type: ignore[union-attr]
        assert "on-screen=promo" in result.output  # type: ignore[union-attr]

    def test_on_screen_text_appears_in_help(self) -> None:
        """vidscope search --help affiche --on-screen-text."""
        result = runner.invoke(app, ["search", "--help"])
        assert result.exit_code == 0
        assert "--on-screen-text" in result.output
