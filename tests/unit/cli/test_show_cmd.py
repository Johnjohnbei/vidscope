"""Tests for `vidscope show <id>` command — M007/S04-P02.

Pattern: CliRunner + mock ShowVideoUseCase.execute. The use case is
patched so the CLI receives a controlled ShowVideoResult.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vidscope.application.show_video import ShowVideoResult
from vidscope.cli.app import app
from vidscope.domain import (
    FrameText,
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


# ---------------------------------------------------------------------------
# M008 CLI tests — on-screen text + thumbnail + content_shape
# ---------------------------------------------------------------------------


def _make_video_with_visual(
    vid: int = 42,
    thumbnail_key: str | None = None,
    content_shape: str | None = None,
) -> Video:
    return Video(
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"yt{vid}"),
        url=f"https://youtube.com/watch?v=yt{vid}",
        id=VideoId(vid),
        title=f"Video {vid}",
        thumbnail_key=thumbnail_key,
        content_shape=content_shape,
    )


def _make_frame_text(
    vid: int, frame_id: int, text: str, fid: int = 1, confidence: float = 0.90
) -> FrameText:
    return FrameText(
        video_id=VideoId(vid),
        frame_id=frame_id,
        text=text,
        confidence=confidence,
        id=fid,
    )


def _invoke_show_m008(video_id: int, result: ShowVideoResult) -> object:
    mock_uc = MagicMock()
    mock_uc.execute.return_value = result
    container = MagicMock()

    with patch(_PATCH_CONTAINER, return_value=container), patch(
        _PATCH_USE_CASE, return_value=mock_uc
    ):
        return runner.invoke(app, ["show", str(video_id)])


class TestShowCommandM008:
    def test_show_renders_on_screen_text_section(self) -> None:
        """show 42 avec 3 frame_texts → output contient 'on-screen text: 3 block(s)'."""
        vid = 42
        video = _make_video_with_visual(vid)
        ft1 = _make_frame_text(vid, 1, "Link in bio", fid=1)
        ft2 = _make_frame_text(vid, 2, "Promo code XYZ", fid=2)
        ft3 = _make_frame_text(vid, 3, "Subscribe now", fid=3)
        result = ShowVideoResult(
            found=True,
            video=video,
            frame_texts=(ft1, ft2, ft3),
        )
        cli_result = _invoke_show_m008(vid, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "on-screen text: 3 block(s)" in cli_result.output  # type: ignore[union-attr]
        assert "Link in bio" in cli_result.output  # type: ignore[union-attr]
        assert "Promo code XYZ" in cli_result.output  # type: ignore[union-attr]
        assert "Subscribe now" in cli_result.output  # type: ignore[union-attr]

    def test_show_renders_none_when_no_frame_texts(self) -> None:
        """show 42 sans frame_texts → output contient 'on-screen text: none'."""
        vid = 42
        video = _make_video_with_visual(vid)
        result = ShowVideoResult(found=True, video=video, frame_texts=())
        cli_result = _invoke_show_m008(vid, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "on-screen text: none" in cli_result.output  # type: ignore[union-attr]

    def test_show_renders_thumbnail_key(self) -> None:
        """show 42 avec thumbnail_key → output contient 'thumbnail: <key>'."""
        vid = 42
        video = _make_video_with_visual(vid, thumbnail_key="videos/yt/abc/thumb.jpg")
        result = ShowVideoResult(found=True, video=video, thumbnail_key="videos/yt/abc/thumb.jpg")
        cli_result = _invoke_show_m008(vid, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "videos/yt/abc/thumb.jpg" in cli_result.output  # type: ignore[union-attr]
        assert "thumbnail" in cli_result.output.lower()  # type: ignore[union-attr]

    def test_show_renders_thumbnail_none(self) -> None:
        """show 42 sans thumbnail_key → output contient 'thumbnail: none'."""
        vid = 42
        video = _make_video_with_visual(vid, thumbnail_key=None)
        result = ShowVideoResult(found=True, video=video, thumbnail_key=None)
        cli_result = _invoke_show_m008(vid, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "thumbnail: none" in cli_result.output  # type: ignore[union-attr]

    def test_show_renders_content_shape(self) -> None:
        """show 42 avec content_shape → output contient 'content_shape: talking_head'."""
        vid = 42
        video = _make_video_with_visual(vid, content_shape="talking_head")
        result = ShowVideoResult(found=True, video=video, content_shape="talking_head")
        cli_result = _invoke_show_m008(vid, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "talking_head" in cli_result.output  # type: ignore[union-attr]
        assert "content_shape" in cli_result.output  # type: ignore[union-attr]

    def test_show_renders_content_shape_unknown_when_none(self) -> None:
        """show 42 sans content_shape → output contient 'content_shape: unknown'."""
        vid = 42
        video = _make_video_with_visual(vid, content_shape=None)
        result = ShowVideoResult(found=True, video=video, content_shape=None)
        cli_result = _invoke_show_m008(vid, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "content_shape: unknown" in cli_result.output  # type: ignore[union-attr]

    def test_show_preview_cap_with_more_indicator(self) -> None:
        """show 42 avec 10 frame_texts → output contient '...and 5 more'."""
        vid = 42
        video = _make_video_with_visual(vid)
        frame_texts = tuple(
            _make_frame_text(vid, i, f"text {i}", fid=i) for i in range(1, 11)
        )
        result = ShowVideoResult(found=True, video=video, frame_texts=frame_texts)
        cli_result = _invoke_show_m008(vid, result)

        assert cli_result.exit_code == 0  # type: ignore[union-attr]
        assert "...and 5 more" in cli_result.output  # type: ignore[union-attr]
