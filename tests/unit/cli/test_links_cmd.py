"""Tests for `vidscope links <id>` command — M007/S04-P01.

Pattern: CliRunner + mock build_container. The ListLinksUseCase is
patched at the class level so the CLI receives a controlled result.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vidscope.cli.app import app
from vidscope.domain import Link, VideoId

runner = CliRunner()

_PATCH = "vidscope.cli._support.build_container"


def _make_link(
    vid: int,
    url: str = "https://example.com",
    source: str = "description",
    position_ms: int | None = None,
    link_id: int | None = 1,
) -> Link:
    return Link(
        video_id=VideoId(vid),
        url=url,
        normalized_url=url.lower(),
        source=source,
        position_ms=position_ms,
        id=link_id,
    )


def _make_result(found: bool, links: list[Link] | None = None, video_id: int = 42) -> object:
    from vidscope.application.list_links import ListLinksResult
    return ListLinksResult(
        video_id=video_id,
        found=found,
        links=tuple(links or []),
    )


class TestLinksCommandBasic:
    def test_links_found_exits_ok(self) -> None:
        """vidscope links 42 → exit 0 quand video existe avec des liens."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = _make_result(
            found=True,
            links=[_make_link(42, "https://example.com")],
        )
        container = MagicMock()

        with patch(_PATCH, return_value=container), patch(
            "vidscope.cli.commands.links.ListLinksUseCase", return_value=mock_uc
        ):
            result = runner.invoke(app, ["links", "42"])

        assert result.exit_code == 0
        assert "example.com" in result.output

    def test_links_not_found_exits_nonzero(self) -> None:
        """vidscope links 999 sur video inexistant → exit != 0."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = _make_result(found=False, video_id=999)
        container = MagicMock()

        with patch(_PATCH, return_value=container), patch(
            "vidscope.cli.commands.links.ListLinksUseCase", return_value=mock_uc
        ):
            result = runner.invoke(app, ["links", "999"])

        assert result.exit_code != 0

    def test_links_source_option_passed_to_execute(self) -> None:
        """links 42 --source description → execute(42, source='description')."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = _make_result(found=True, links=[])
        container = MagicMock()

        with patch(_PATCH, return_value=container), patch(
            "vidscope.cli.commands.links.ListLinksUseCase", return_value=mock_uc
        ):
            result = runner.invoke(app, ["links", "42", "--source", "description"])

        assert result.exit_code == 0
        call_kwargs = mock_uc.execute.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("source") == "description"

    def test_links_help_shows_source_option(self) -> None:
        """vidscope links --help affiche --source."""
        result = runner.invoke(app, ["links", "--help"])
        assert result.exit_code == 0
        assert "--source" in result.output

    def test_links_empty_shows_no_urls_message(self) -> None:
        """Video existante sans liens → affiche message 'No URLs'."""
        mock_uc = MagicMock()
        mock_uc.execute.return_value = _make_result(found=True, links=[])
        container = MagicMock()

        with patch(_PATCH, return_value=container), patch(
            "vidscope.cli.commands.links.ListLinksUseCase", return_value=mock_uc
        ):
            result = runner.invoke(app, ["links", "42"])

        assert result.exit_code == 0
        assert "No URLs" in result.output
