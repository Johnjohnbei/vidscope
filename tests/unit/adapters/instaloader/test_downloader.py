"""Tests for InstaLoaderDownloader and its helpers."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vidscope.adapters.instaloader.downloader import (
    InstaLoaderDownloader,
    _extract_shortcode,
    _download_images,
)
from vidscope.domain import IngestError, MediaType, Platform
from vidscope.ports import ProbeStatus


# ---------------------------------------------------------------------------
# _extract_shortcode
# ---------------------------------------------------------------------------


class TestExtractShortcode:
    def test_post_url(self) -> None:
        assert _extract_shortcode("https://www.instagram.com/p/DXJXAQkAbYt/") == "DXJXAQkAbYt"

    def test_post_url_with_query(self) -> None:
        assert (
            _extract_shortcode(
                "https://www.instagram.com/p/DXJXAQkAbYt/?img_index=4&igsh=abc"
            )
            == "DXJXAQkAbYt"
        )

    def test_reel_url(self) -> None:
        assert (
            _extract_shortcode("https://www.instagram.com/reel/DXWdHTsiPP5/")
            == "DXWdHTsiPP5"
        )

    def test_tv_url(self) -> None:
        assert _extract_shortcode("https://www.instagram.com/tv/Cabc123/") == "Cabc123"

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(IngestError, match="cannot extract"):
            _extract_shortcode("https://www.youtube.com/watch?v=abc")

    def test_empty_url_raises(self) -> None:
        with pytest.raises(IngestError):
            _extract_shortcode("")


# ---------------------------------------------------------------------------
# _download_images
# ---------------------------------------------------------------------------


def _make_node(*, is_video: bool, display_url: str) -> MagicMock:
    n = MagicMock()
    n.is_video = is_video
    n.display_url = display_url
    return n


def _make_session(content: bytes = b"fake-image") -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.get.return_value = resp
    return session


class TestDownloadImages:
    def test_single_image_post(self, tmp_path: Path) -> None:
        post = MagicMock()
        post.typename = "GraphImage"
        post.is_video = False
        post.url = "https://cdn.instagram.com/img.jpg"

        paths = _download_images(post, tmp_path, _make_session(b"img-data"))

        assert len(paths) == 1
        assert Path(paths[0]).name == "image.jpg"
        assert Path(paths[0]).read_bytes() == b"img-data"

    def test_carousel_downloads_all_images(self, tmp_path: Path) -> None:
        nodes = [
            _make_node(is_video=False, display_url="https://cdn/0.jpg"),
            _make_node(is_video=False, display_url="https://cdn/1.jpg"),
            _make_node(is_video=False, display_url="https://cdn/2.jpg"),
        ]
        post = MagicMock()
        post.typename = "GraphSidecar"
        post.get_sidecar_nodes.return_value = iter(nodes)

        paths = _download_images(post, tmp_path, _make_session())

        assert len(paths) == 3
        names = [Path(p).name for p in paths]
        assert names == ["slide_0000.jpg", "slide_0001.jpg", "slide_0002.jpg"]

    def test_carousel_skips_video_nodes(self, tmp_path: Path) -> None:
        nodes = [
            _make_node(is_video=False, display_url="https://cdn/0.jpg"),
            _make_node(is_video=True, display_url="https://cdn/vid.mp4"),
            _make_node(is_video=False, display_url="https://cdn/2.jpg"),
        ]
        post = MagicMock()
        post.typename = "GraphSidecar"
        post.get_sidecar_nodes.return_value = iter(nodes)

        paths = _download_images(post, tmp_path, _make_session())

        assert len(paths) == 2

    def test_video_post_returns_empty(self, tmp_path: Path) -> None:
        post = MagicMock()
        post.typename = "GraphVideo"
        post.is_video = True

        paths = _download_images(post, tmp_path, _make_session())

        assert paths == []


# ---------------------------------------------------------------------------
# Helpers to build a fake instaloader
# ---------------------------------------------------------------------------


def _make_fake_instaloader(post: MagicMock) -> MagicMock:
    """Return a fake instaloader module whose Post.from_shortcode returns post."""
    context = MagicMock()
    context._session = _make_session()

    L_instance = MagicMock()
    L_instance.context = context

    IL_class = MagicMock(return_value=L_instance)

    fake_post_cls = MagicMock()
    fake_post_cls.from_shortcode.return_value = post

    fake_module = MagicMock()
    fake_module.Instaloader = IL_class
    fake_module.Post = fake_post_cls

    return fake_module


def _make_post(
    *,
    typename: str = "GraphImage",
    is_video: bool = False,
    url: str = "https://cdn/img.jpg",
    caption: str | None = "Hello world",
    owner_username: str = "testuser",
    sidecar_nodes: list | None = None,
    likes: int | None = 10,
    comments: int | None = 2,
) -> MagicMock:
    post = MagicMock()
    post.typename = typename
    post.is_video = is_video
    post.url = url
    post.caption = caption
    post.owner_username = owner_username
    post.date_utc = datetime(2026, 4, 20, tzinfo=timezone.utc)
    post.likes = likes
    post.comments = comments
    if sidecar_nodes is not None:
        post.get_sidecar_nodes.return_value = iter(sidecar_nodes)
    return post


# ---------------------------------------------------------------------------
# InstaLoaderDownloader.download
# ---------------------------------------------------------------------------


class TestInstaLoaderDownloaderDownload:
    def test_single_image_returns_image_outcome(self, tmp_path: Path) -> None:
        post = _make_post(typename="GraphImage", is_video=False)
        fake_il = _make_fake_instaloader(post)

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            dl = InstaLoaderDownloader()
            outcome = dl.download(
                "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
            )

        assert outcome.platform == Platform.INSTAGRAM
        assert str(outcome.platform_id) == "DXJXAQkAbYt"
        assert outcome.media_type == MediaType.IMAGE
        assert outcome.carousel_items == ()
        assert outcome.author == "testuser"
        assert outcome.title == "Hello world"
        assert outcome.upload_date == "20260420"

    def test_carousel_returns_carousel_outcome(self, tmp_path: Path) -> None:
        nodes = [
            _make_node(is_video=False, display_url="https://cdn/0.jpg"),
            _make_node(is_video=False, display_url="https://cdn/1.jpg"),
        ]
        post = _make_post(typename="GraphSidecar", sidecar_nodes=nodes)
        fake_il = _make_fake_instaloader(post)

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            dl = InstaLoaderDownloader()
            outcome = dl.download(
                "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
            )

        assert outcome.media_type == MediaType.CAROUSEL
        assert len(outcome.carousel_items) == 2

    def test_video_post_raises_no_images(self, tmp_path: Path) -> None:
        post = _make_post(typename="GraphVideo", is_video=True)
        fake_il = _make_fake_instaloader(post)

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            with pytest.raises(IngestError, match="no downloadable images"):
                InstaLoaderDownloader().download(
                    "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
                )

    def test_instaloader_not_installed_raises(self, tmp_path: Path) -> None:
        with patch.dict(sys.modules, {"instaloader": None}):
            with pytest.raises(IngestError, match="instaloader is not installed"):
                InstaLoaderDownloader().download(
                    "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
                )

    def test_invalid_url_raises(self, tmp_path: Path) -> None:
        post = _make_post()
        fake_il = _make_fake_instaloader(post)

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            with pytest.raises(IngestError, match="cannot extract"):
                InstaLoaderDownloader().download(
                    "https://www.youtube.com/watch?v=abc", str(tmp_path)
                )

    def test_post_fetch_failure_raises_retryable(self, tmp_path: Path) -> None:
        fake_il = MagicMock()
        fake_il.Instaloader.return_value.context._session = _make_session()
        fake_il.Post.from_shortcode.side_effect = ConnectionError("timeout")

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            with pytest.raises(IngestError) as info:
                InstaLoaderDownloader().download(
                    "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
                )

        assert info.value.retryable is True

    def test_none_caption_gives_none_title(self, tmp_path: Path) -> None:
        post = _make_post(caption=None)
        fake_il = _make_fake_instaloader(post)

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            outcome = InstaLoaderDownloader().download(
                "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
            )

        assert outcome.title is None

    def test_long_caption_truncated_to_200(self, tmp_path: Path) -> None:
        post = _make_post(caption="x" * 300)
        fake_il = _make_fake_instaloader(post)

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            outcome = InstaLoaderDownloader().download(
                "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
            )

        assert outcome.title is not None
        assert len(outcome.title) == 200

    def test_caption_populates_description(self, tmp_path: Path) -> None:
        """R060 — full caption goes to outcome.description (not just title)."""
        caption = "A" * 300  # > 200 chars → title tronqué mais description complète
        post = _make_post(caption=caption)
        fake_il = _make_fake_instaloader(post)

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            outcome = InstaLoaderDownloader().download(
                "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
            )

        assert outcome.description == caption
        assert outcome.title == caption[:200]

    def test_null_caption_gives_null_description(self, tmp_path: Path) -> None:
        post = _make_post(caption=None)
        fake_il = _make_fake_instaloader(post)

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            outcome = InstaLoaderDownloader().download(
                "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
            )

        assert outcome.description is None
        assert outcome.title is None

    def test_engagement_stats_populated(self, tmp_path: Path) -> None:
        """R061 — like_count / comment_count extracted from Post."""
        post = _make_post(likes=123, comments=45)
        fake_il = _make_fake_instaloader(post)

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            outcome = InstaLoaderDownloader().download(
                "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
            )

        assert outcome.like_count == 123
        assert outcome.comment_count == 45

    def test_none_likes_gives_none_engagement(self, tmp_path: Path) -> None:
        post = _make_post(likes=None, comments=None)
        fake_il = _make_fake_instaloader(post)

        with patch.dict(sys.modules, {"instaloader": fake_il}):
            outcome = InstaLoaderDownloader().download(
                "https://www.instagram.com/p/DXJXAQkAbYt/", str(tmp_path)
            )

        assert outcome.like_count is None
        assert outcome.comment_count is None


# ---------------------------------------------------------------------------
# InstaLoaderDownloader.list_channel_videos and probe
# ---------------------------------------------------------------------------


class TestInstaLoaderDownloaderOtherMethods:
    def test_list_channel_videos_raises_ingest_error(self) -> None:
        with pytest.raises(IngestError):
            InstaLoaderDownloader().list_channel_videos("http://x")

    def test_probe_returns_unsupported(self) -> None:
        result = InstaLoaderDownloader().probe("http://x")
        assert result.status == ProbeStatus.UNSUPPORTED
        assert result.url == "http://x"
