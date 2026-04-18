"""Tests for `vidscope show <id>` command — M007/S04-P02.

Pattern: CliRunner + mock ShowVideoUseCase.execute. The use case is
patched so the CLI receives a controlled ShowVideoResult.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vidscope.application.show_video import ShowVideoResult
from vidscope.cli.app import app
from vidscope.domain import (
    Hashtag,
    Link,
    Mention,
    Platform,
    Video,
    VideoId,
)
from vidscope.domain.values import PlatformId

runner = CliRunner()

_PATCH_CONTAINER = "vidscope.cli._support.build_container"
_PATCH_USE_CASE = "vidscope.cli.commands.show.ShowVideoUseCase"


def _make_video(
    vid: int = 42,
    description: str | None = None,
    music_track: str | None = None,
    music_artist: str | None = None,
) -> Video:
    return Video(
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"yt{vid}"),
        url=f"https://youtube.com/watch?v=yt{vid}",
        id=VideoId(vid),
        title=f"Video {vid}",
        description=description,
        music_track=music_track,
        music_artist=music_artist,
    )


def _make_result(
    found: bool = True,
    video: Video | None = None,
    hashtags: tuple[Hashtag, ...] = (),
    mentions: tuple[Mention, ...] = (),
    links: tuple[Link, ...] = (),
    video_id: int = 42,
) -> ShowVideoResult:
    if not found:
        return ShowVideoResult(found=False)
    if video is None:
        video = _make_video(video_id)
    return ShowVideoResult(
        found=True,
        video=video,
        hashtags=hashtags,
        mentions=mentions,
        links=links,
    )


def _invoke_show(video_id: int, result: ShowVideoResult) -> object:
    """Helper to invoke show command with a mocked use case."""
    mock_uc = MagicMock()
    mock_uc.execute.return_value = result
    container = MagicMock()

    with patch(_PATCH_CONTAINER, return_value=container), patch(
        _PATCH_USE_CASE, return_value=mock_uc
    ):
        return runner.invoke(app, ["show", str(video_id)])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestShowCommandDescription:
    def test_show_video_with_description_displays_it(self) -> None:
        """show 42 sur video avec description → stdout contient la description."""
        video = _make_video(42, description="My great video description")
        result = _make_result(video=video)
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "My great video description" in cli_result.output  # type: ignore[union-attr]

    def test_show_video_long_description_is_truncated(self) -> None:
        """Description > 240 chars est tronquée avec '...' ou '…'."""
        long_desc = "A" * 300
        video = _make_video(42, description=long_desc)
        result = _make_result(video=video)
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        # Should NOT contain all 300 chars — truncated
        assert "A" * 300 not in cli_result.output  # type: ignore[union-attr]
        # But should contain some of the description
        assert "A" * 50 in cli_result.output  # type: ignore[union-attr]

    def test_show_video_without_description_shows_none(self) -> None:
        """show 42 sur video sans description → affiche 'none' (pas d'erreur)."""
        video = _make_video(42, description=None)
        result = _make_result(video=video)
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "description" in cli_result.output.lower()  # type: ignore[union-attr]


class TestShowCommandMusic:
    def test_show_video_with_music_displays_track_and_artist(self) -> None:
        """show 42 avec music_track + music_artist → stdout contient 'Song — X'."""
        video = _make_video(42, music_track="Best Song", music_artist="Cool Artist")
        result = _make_result(video=video)
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "Best Song" in cli_result.output  # type: ignore[union-attr]
        assert "Cool Artist" in cli_result.output  # type: ignore[union-attr]

    def test_show_video_without_music_shows_none(self) -> None:
        """show 42 sans music → affiche 'none' (pas d'erreur)."""
        video = _make_video(42, music_track=None, music_artist=None)
        result = _make_result(video=video)
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "music" in cli_result.output.lower()  # type: ignore[union-attr]


class TestShowCommandHashtags:
    def test_show_video_with_hashtags_displays_them(self) -> None:
        """show 42 avec hashtags → stdout liste les hashtags avec '#'."""
        hashtags = (
            Hashtag(video_id=VideoId(42), tag="cooking", id=1),
            Hashtag(video_id=VideoId(42), tag="recipe", id=2),
        )
        result = _make_result(hashtags=hashtags)
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "#cooking" in cli_result.output  # type: ignore[union-attr]
        assert "#recipe" in cli_result.output  # type: ignore[union-attr]

    def test_show_video_without_hashtags_shows_none(self) -> None:
        """show 42 sans hashtags → affiche 'none' (pas d'erreur)."""
        result = _make_result(hashtags=())
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "hashtags" in cli_result.output.lower()  # type: ignore[union-attr]


class TestShowCommandMentions:
    def test_show_video_with_mentions_displays_them(self) -> None:
        """show 42 avec mentions → stdout liste les mentions avec '@'."""
        mentions = (
            Mention(video_id=VideoId(42), handle="alice", id=1),
        )
        result = _make_result(mentions=mentions)
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "@alice" in cli_result.output  # type: ignore[union-attr]

    def test_show_video_without_mentions_shows_none(self) -> None:
        """show 42 sans mentions → affiche 'none' (pas d'erreur)."""
        result = _make_result(mentions=())
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "mentions" in cli_result.output.lower()  # type: ignore[union-attr]


class TestShowCommandBaseline:
    def test_show_without_m007_data_does_not_crash(self) -> None:
        """show 42 sur video sans données M007 → exit 0, affiche champs vides."""
        video = _make_video(
            42,
            description=None,
            music_track=None,
            music_artist=None,
        )
        result = _make_result(video=video, hashtags=(), mentions=(), links=())
        cli_result = _invoke_show(42, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        # Should display all section labels even when empty
        assert "description" in cli_result.output.lower()  # type: ignore[union-attr]
        assert "music" in cli_result.output.lower()  # type: ignore[union-attr]
        assert "hashtags" in cli_result.output.lower()  # type: ignore[union-attr]
        assert "mentions" in cli_result.output.lower()  # type: ignore[union-attr]

    def test_show_nonexistent_video_exits_nonzero(self) -> None:
        """show 999 sur video inexistant → exit != 0 (pas de régression)."""
        result = _make_result(found=False)
        cli_result = _invoke_show(999, result)

        assert cli_result.exit_code != 0  # type: ignore[union-attr]
