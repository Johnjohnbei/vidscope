"""Unit tests for :class:`YtdlpDownloader`.

Every test monkeypatches ``yt_dlp.YoutubeDL`` so there is zero real
network traffic. Live-network coverage lives in
``tests/integration/test_ingest_live.py`` and is skipped by default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest
from yt_dlp.utils import DownloadError, ExtractorError

from vidscope.adapters.ytdlp import downloader as downloader_module
from vidscope.adapters.ytdlp.downloader import YtdlpDownloader
from vidscope.domain import IngestError, Platform

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeYoutubeDL:
    """A yt-dlp YoutubeDL stand-in that returns a pre-seeded info_dict.

    Tests swap the module-level ``yt_dlp.YoutubeDL`` symbol with a
    factory that closes over the info we want to return. ``__enter__``
    returns ``self`` so the downloader's context-manager usage works.
    """

    def __init__(
        self,
        info: dict[str, Any] | None = None,
        *,
        touch_file: Path | None = None,
        raise_on_extract: Exception | None = None,
    ) -> None:
        self._info = info
        self._touch_file = touch_file
        self._raise = raise_on_extract

    def __enter__(self) -> FakeYoutubeDL:
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def extract_info(
        self, url: str, *, download: bool = True
    ) -> dict[str, Any] | None:
        if self._raise is not None:
            raise self._raise
        if self._touch_file is not None:
            self._touch_file.parent.mkdir(parents=True, exist_ok=True)
            self._touch_file.write_bytes(b"fake media content")
        return self._info


def _install_fake(
    monkeypatch: pytest.MonkeyPatch,
    factory: Any,
) -> None:
    """Replace yt_dlp.YoutubeDL (as seen by the adapter) with ``factory``."""
    monkeypatch.setattr(downloader_module.yt_dlp, "YoutubeDL", factory)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_youtube_returns_ingest_outcome(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        destination = tmp_path / "downloads"
        expected_file = destination / "abc123.mp4"

        info = {
            "id": "abc123",
            "extractor_key": "Youtube",
            "webpage_url": "https://www.youtube.com/watch?v=abc123",
            "title": "Hello world",
            "uploader": "Test Channel",
            "duration": 120.5,
            "upload_date": "20260401",
            "view_count": 1234,
            "requested_downloads": [{"filepath": str(expected_file)}],
        }

        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                info=info, touch_file=expected_file
            ),
        )

        dl = YtdlpDownloader()
        outcome = dl.download(
            "https://www.youtube.com/watch?v=abc123", str(destination)
        )

        assert outcome.platform is Platform.YOUTUBE
        assert outcome.platform_id == "abc123"
        assert outcome.url == "https://www.youtube.com/watch?v=abc123"
        assert outcome.media_path == str(expected_file)
        assert outcome.title == "Hello world"
        assert outcome.author == "Test Channel"
        assert outcome.duration == 120.5
        assert outcome.upload_date == "20260401"
        assert outcome.view_count == 1234
        assert expected_file.exists()

    def test_tiktok_extractor_mapped(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        destination = tmp_path / "d"
        expected_file = destination / "7000000.mp4"
        info = {
            "id": "7000000",
            "extractor_key": "TikTok",
            "webpage_url": "https://www.tiktok.com/@user/video/7000000",
            "title": "Trending clip",
            "uploader": "@user",
            "duration": 15.0,
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                info=info, touch_file=expected_file
            ),
        )

        outcome = YtdlpDownloader().download(
            "https://www.tiktok.com/@user/video/7000000", str(destination)
        )
        assert outcome.platform is Platform.TIKTOK

    def test_instagram_extractor_mapped(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        destination = tmp_path / "d"
        expected_file = destination / "Cabc.mp4"
        info = {
            "id": "Cabc",
            "extractor_key": "Instagram",
            "webpage_url": "https://www.instagram.com/reel/Cabc/",
            "title": "Reel",
            "uploader": "someone",
            "duration": 30.0,
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                info=info, touch_file=expected_file
            ),
        )

        outcome = YtdlpDownloader().download(
            "https://www.instagram.com/reel/Cabc/", str(destination)
        )
        assert outcome.platform is Platform.INSTAGRAM

    def test_extractor_with_colon_still_mapped(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """yt-dlp sometimes reports extractor_key like 'youtube:tab'.
        We should split on ':' and find the base extractor."""
        destination = tmp_path / "d"
        expected_file = destination / "xyz.mp4"
        info = {
            "id": "xyz",
            "extractor_key": "youtube:tab",
            "webpage_url": "https://www.youtube.com/playlist?list=xyz",
            "title": "Playlist entry",
            "uploader": "Channel",
            "duration": 5.0,
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                info=info, touch_file=expected_file
            ),
        )

        outcome = YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=xyz", str(destination)
        )
        assert outcome.platform is Platform.YOUTUBE

    def test_resolves_media_via_legacy_filename_field(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        destination = tmp_path / "d"
        expected_file = destination / "legacy.mp4"
        info = {
            "id": "legacy",
            "extractor_key": "Youtube",
            "_filename": str(expected_file),
            "title": "Old format",
            "uploader": "Old uploader",
            "duration": 60.0,
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                info=info, touch_file=expected_file
            ),
        )

        outcome = YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=legacy", str(destination)
        )
        assert outcome.media_path == str(expected_file)

    def test_resolves_media_via_directory_glob_fallback(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        destination = tmp_path / "d"
        expected_file = destination / "fallback.webm"
        info = {
            "id": "fallback",
            "extractor_key": "Youtube",
            "title": "No filepath in info",
            "uploader": "Uploader",
            "duration": 10.0,
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                info=info, touch_file=expected_file
            ),
        )

        outcome = YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=fallback", str(destination)
        )
        assert outcome.media_path == str(expected_file)


# ---------------------------------------------------------------------------
# Error translation
# ---------------------------------------------------------------------------


class TestErrorTranslation:
    def test_download_error_is_translated_and_retryable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=DownloadError("network hiccup")
            ),
        )

        dl = YtdlpDownloader()
        with pytest.raises(IngestError) as exc_info:
            dl.download("https://www.youtube.com/watch?v=xyz", str(tmp_path))

        err = exc_info.value
        assert err.retryable is True
        assert "network hiccup" in str(err)
        assert isinstance(err.cause, DownloadError)

    def test_permanent_unsupported_url_is_not_retryable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=DownloadError("Unsupported URL: foo")
            ),
        )

        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader().download(
                "https://example.com/foo", str(tmp_path)
            )
        assert exc_info.value.retryable is False

    def test_permanent_video_unavailable_is_not_retryable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=DownloadError("video unavailable")
            ),
        )

        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader().download(
                "https://www.youtube.com/watch?v=gone", str(tmp_path)
            )
        assert exc_info.value.retryable is False

    def test_extractor_error_is_translated(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=ExtractorError("extractor broke")
            ),
        )

        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader().download(
                "https://www.instagram.com/reel/foo", str(tmp_path)
            )
        err = exc_info.value
        assert err.retryable is False  # default for extractor errors
        assert "extractor broke" in str(err)

    def test_extractor_error_can_be_retryable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=ExtractorError(
                    "Service is temporarily unavailable, try again later"
                )
            ),
        )

        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader().download(
                "https://www.tiktok.com/@user/video/1",
                str(tmp_path),
            )
        assert exc_info.value.retryable is True

    def test_unexpected_exception_becomes_non_retryable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=RuntimeError("something weird")
            ),
        )

        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader().download(
                "https://www.youtube.com/watch?v=x", str(tmp_path)
            )
        err = exc_info.value
        assert err.retryable is False
        assert "unexpected yt-dlp failure" in str(err)


class TestValidation:
    def test_empty_url_raises_ingest_error(self, tmp_path: Path) -> None:
        with pytest.raises(IngestError):
            YtdlpDownloader().download("", str(tmp_path))

    def test_whitespace_url_raises_ingest_error(self, tmp_path: Path) -> None:
        with pytest.raises(IngestError):
            YtdlpDownloader().download("   ", str(tmp_path))

    def test_missing_id_in_info_raises_ingest_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        info = {
            "extractor_key": "Youtube",
            "title": "No id",
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(info=info),
        )

        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader().download(
                "https://www.youtube.com/watch?v=x", str(tmp_path)
            )
        assert "no 'id' field" in str(exc_info.value)

    def test_unknown_extractor_raises_ingest_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        info = {
            "id": "foo",
            "extractor_key": "vimeo",
            "title": "Not supported",
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(info=info),
        )

        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader().download(
                "https://vimeo.com/foo", str(tmp_path)
            )
        assert "unsupported yt-dlp extractor" in str(exc_info.value)

    def test_none_info_raises_ingest_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(info=None),
        )

        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader().download(
                "https://www.youtube.com/watch?v=none", str(tmp_path)
            )
        assert "no metadata" in str(exc_info.value)

    def test_missing_media_file_raises_ingest_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """yt-dlp returned info but the file doesn't exist on disk."""
        info = {
            "id": "ghost",
            "extractor_key": "Youtube",
            "title": "No file on disk",
            "uploader": "Nobody",
            "duration": 10.0,
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(info=info),
        )

        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader().download(
                "https://www.youtube.com/watch?v=ghost", str(tmp_path)
            )
        assert "no media file was found" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Cookies support (S07/T02)
# ---------------------------------------------------------------------------


class CapturingFakeYoutubeDL(FakeYoutubeDL):
    """Fake yt-dlp that records the options dict it was constructed with."""

    last_options: dict[str, Any] | None = None

    def __init__(
        self,
        options: dict[str, Any],
        *,
        info: dict[str, Any] | None = None,
        touch_file: Path | None = None,
        raise_on_extract: Exception | None = None,
    ) -> None:
        super().__init__(
            info=info,
            touch_file=touch_file,
            raise_on_extract=raise_on_extract,
        )
        type(self).last_options = options


class TestCookiesSupport:
    """T02: cookies_file parameter on YtdlpDownloader."""

    def test_no_cookies_file_means_no_cookiefile_in_options(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Default constructor (no cookies) must NOT inject cookiefile."""
        destination = tmp_path / "downloads"
        expected_file = destination / "abc.mp4"
        info = {
            "id": "abc",
            "extractor_key": "Youtube",
            "webpage_url": "https://www.youtube.com/watch?v=abc",
            "title": "No cookies needed",
            "uploader": "Test",
            "duration": 5.0,
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        CapturingFakeYoutubeDL.last_options = None
        monkeypatch.setattr(
            downloader_module.yt_dlp,
            "YoutubeDL",
            lambda options: CapturingFakeYoutubeDL(
                options, info=info, touch_file=expected_file
            ),
        )

        YtdlpDownloader().download(
            "https://www.youtube.com/watch?v=abc", str(destination)
        )

        assert CapturingFakeYoutubeDL.last_options is not None
        assert "cookiefile" not in CapturingFakeYoutubeDL.last_options

    def test_cookies_file_added_to_options(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When cookies_file points at an existing file, the cookiefile
        option is added to every yt-dlp invocation."""
        cookies = tmp_path / "cookies.txt"
        cookies.write_text("# Netscape HTTP Cookie File\n")

        destination = tmp_path / "downloads"
        expected_file = destination / "withcookies.mp4"
        info = {
            "id": "withcookies",
            "extractor_key": "Instagram",
            "webpage_url": "https://www.instagram.com/reel/withcookies/",
            "title": "Cookied Reel",
            "uploader": "test",
            "duration": 30.0,
            "requested_downloads": [{"filepath": str(expected_file)}],
        }
        CapturingFakeYoutubeDL.last_options = None
        monkeypatch.setattr(
            downloader_module.yt_dlp,
            "YoutubeDL",
            lambda options: CapturingFakeYoutubeDL(
                options, info=info, touch_file=expected_file
            ),
        )

        dl = YtdlpDownloader(cookies_file=cookies)
        dl.download(
            "https://www.instagram.com/reel/withcookies/", str(destination)
        )

        assert CapturingFakeYoutubeDL.last_options is not None
        assert (
            CapturingFakeYoutubeDL.last_options.get("cookiefile")
            == str(cookies.resolve())
        )

    def test_missing_cookies_file_raises_at_init_time(
        self, tmp_path: Path
    ) -> None:
        """Init-time fail-fast: a missing cookies file raises IngestError
        immediately, not at the first download."""
        bad_path = tmp_path / "does-not-exist.txt"
        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader(cookies_file=bad_path)
        assert "cookies file not found" in str(exc_info.value)
        assert exc_info.value.retryable is False

    def test_cookies_path_pointing_at_directory_raises(
        self, tmp_path: Path
    ) -> None:
        """If the cookies path is a directory (typo'd to a folder), we
        catch that distinctly from 'not found' so the error message
        helps the user fix the right thing."""
        bad_dir = tmp_path / "subdir"
        bad_dir.mkdir()
        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader(cookies_file=bad_dir)
        assert "not a file" in str(exc_info.value)
        assert exc_info.value.retryable is False

    def test_cookies_path_with_tilde_is_expanded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tilde expansion in the cookies path so users can write
        ~/cookies.txt without resolving manually."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        cookies = fake_home / "cookies.txt"
        cookies.write_text("# Netscape HTTP Cookie File\n")
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("USERPROFILE", str(fake_home))

        # The path uses ~/cookies.txt — must resolve to fake_home/cookies.txt
        dl = YtdlpDownloader(cookies_file=Path("~/cookies.txt"))
        # Read the resolved path back via _build_options
        opts = dl._build_options(tmp_path)
        assert opts.get("cookiefile") == str(cookies.resolve())


# ---------------------------------------------------------------------------
# M003: list_channel_videos
# ---------------------------------------------------------------------------


class _ListCapturingFake(FakeYoutubeDL):
    """Fake that captures the options dict and returns a preset flat info."""

    captured_options: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        options: dict[str, Any],
        *,
        info: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(info=info)
        type(self).captured_options = options


class TestListChannelVideos:
    def test_returns_channel_entries(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        info = {
            "entries": [
                {"id": "v1", "webpage_url": "https://www.youtube.com/watch?v=v1"},
                {"id": "v2", "webpage_url": "https://www.youtube.com/watch?v=v2"},
                {"id": "v3", "webpage_url": "https://www.youtube.com/watch?v=v3"},
            ]
        }
        _install_fake(
            monkeypatch,
            lambda options: _ListCapturingFake(options, info=info),
        )

        entries = YtdlpDownloader().list_channel_videos(
            "https://www.youtube.com/@YouTube", limit=5
        )
        assert len(entries) == 3
        assert entries[0].platform_id == "v1"
        assert entries[0].url == "https://www.youtube.com/watch?v=v1"

    def test_passes_extract_flat_in_options(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _install_fake(
            monkeypatch,
            lambda options: _ListCapturingFake(
                options, info={"entries": []}
            ),
        )
        YtdlpDownloader().list_channel_videos(
            "https://www.youtube.com/@YouTube", limit=3
        )
        assert _ListCapturingFake.captured_options.get("extract_flat") is True
        assert _ListCapturingFake.captured_options.get("playlist_items") == "1-3"

    def test_limit_caps_returned_entries(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        info = {
            "entries": [{"id": f"v{i}"} for i in range(10)]
        }
        _install_fake(
            monkeypatch,
            lambda options: _ListCapturingFake(options, info=info),
        )

        entries = YtdlpDownloader().list_channel_videos(
            "https://www.youtube.com/@YouTube", limit=5
        )
        assert len(entries) == 5

    def test_empty_url_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        with pytest.raises(IngestError, match="empty"):
            YtdlpDownloader().list_channel_videos("", limit=5)

    def test_none_info_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _install_fake(
            monkeypatch,
            lambda options: _ListCapturingFake(options, info=None),
        )
        with pytest.raises(IngestError, match="no metadata"):
            YtdlpDownloader().list_channel_videos(
                "https://www.youtube.com/@YouTube", limit=5
            )

    def test_download_error_is_translated(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        class FailingFake(FakeYoutubeDL):
            def __init__(self, options: dict[str, Any]) -> None:
                super().__init__(
                    raise_on_extract=DownloadError("channel unavailable")
                )

        _install_fake(monkeypatch, FailingFake)

        with pytest.raises(IngestError, match="channel unavailable"):
            YtdlpDownloader().list_channel_videos(
                "https://www.youtube.com/@YouTube", limit=5
            )

    def test_skips_entries_without_id(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        info = {
            "entries": [
                {"id": "valid", "webpage_url": "https://www.youtube.com/watch?v=valid"},
                {},  # no id — skipped
                {"title": "no id either"},  # no id — skipped
                {"id": "valid2"},
            ]
        }
        _install_fake(
            monkeypatch,
            lambda options: _ListCapturingFake(options, info=info),
        )

        entries = YtdlpDownloader().list_channel_videos(
            "https://www.youtube.com/@YouTube", limit=10
        )
        assert len(entries) == 2
        assert [e.platform_id for e in entries] == ["valid", "valid2"]


# ---------------------------------------------------------------------------
# CookieAuthError detection (M005/S02)
# ---------------------------------------------------------------------------


class TestCookieAuthDetection:
    """yt-dlp errors mentioning auth markers should raise CookieAuthError."""

    def test_login_required_in_download_error_raises_cookie_auth(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from vidscope.domain import CookieAuthError

        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=DownloadError(
                    "ERROR: [instagram] foo: login required to view this content"
                )
            ),
        )

        with pytest.raises(CookieAuthError, match="cookies missing or expired"):
            YtdlpDownloader().download(
                "https://www.instagram.com/reel/abc/", str(tmp_path)
            )

    def test_sign_in_to_confirm_in_extractor_error_raises_cookie_auth(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from vidscope.domain import CookieAuthError

        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=ExtractorError(
                    "Sign in to confirm you're not a bot"
                )
            ),
        )

        with pytest.raises(CookieAuthError, match="vidscope cookies test"):
            YtdlpDownloader().download(
                "https://www.youtube.com/shorts/xyz", str(tmp_path)
            )

    def test_non_auth_error_still_raises_plain_ingest_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from vidscope.domain import CookieAuthError, IngestError

        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=DownloadError(
                    "ERROR: [generic] http error: connection refused"
                )
            ),
        )

        # Should be IngestError, NOT CookieAuthError
        with pytest.raises(IngestError) as exc_info:
            YtdlpDownloader().download("https://example.com/x", str(tmp_path))

        assert not isinstance(exc_info.value, CookieAuthError)


# ---------------------------------------------------------------------------
# probe() (M005/S02)
# ---------------------------------------------------------------------------


class TestProbe:
    def test_ok_returns_probe_status_ok_with_title(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.ports import ProbeStatus

        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                info={"id": "abc", "title": "My Test Reel"}
            ),
        )

        result = YtdlpDownloader().probe(
            "https://www.instagram.com/reel/abc/"
        )
        assert result.status == ProbeStatus.OK
        assert result.title == "My Test Reel"
        assert "My Test Reel" in result.detail

    def test_empty_url_returns_error(self) -> None:
        from vidscope.ports import ProbeStatus

        result = YtdlpDownloader().probe("")
        assert result.status == ProbeStatus.ERROR
        assert "empty" in result.detail

    def test_auth_required_when_login_required(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.ports import ProbeStatus

        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=DownloadError(
                    "ERROR: login required to view this content"
                )
            ),
        )

        result = YtdlpDownloader().probe(
            "https://www.instagram.com/reel/private/"
        )
        assert result.status == ProbeStatus.AUTH_REQUIRED
        assert "authentication required" in result.detail

    def test_unsupported_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.ports import ProbeStatus

        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=DownloadError(
                    "ERROR: Unsupported URL: https://example.com/foo"
                )
            ),
        )

        result = YtdlpDownloader().probe("https://example.com/foo")
        assert result.status == ProbeStatus.UNSUPPORTED

    def test_video_unavailable_returns_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.ports import ProbeStatus

        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=DownloadError("Video unavailable")
            ),
        )

        result = YtdlpDownloader().probe("https://youtube.com/shorts/dead")
        assert result.status == ProbeStatus.NOT_FOUND

    def test_unexpected_exception_returns_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.ports import ProbeStatus

        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(
                raise_on_extract=RuntimeError("boom")
            ),
        )

        result = YtdlpDownloader().probe("https://example.com/x")
        assert result.status == ProbeStatus.ERROR
        assert "boom" in result.detail


# ---------------------------------------------------------------------------
# M006/S01 — ProbeResult creator fields (T12)
# ---------------------------------------------------------------------------


class TestProbeCreatorExtraction:
    """Verify that YtdlpDownloader.probe populates the 6 new creator
    fields added to ProbeResult in S01-P01."""

    def test_uploader_fields_populated_from_info_dict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Core creator fields are extracted from a full info_dict."""
        from vidscope.ports import ProbeResult, ProbeStatus

        info: dict[str, Any] = {
            "id": "UC_abc",
            "title": "My video",
            "uploader": "AliceChannel",
            "uploader_id": "UC_aliceid",
            "uploader_url": "https://www.youtube.com/@Alice",
            "channel_follower_count": 42000,
            "uploader_thumbnail": "https://yt3.ggpht.com/alice.jpg",
            "channel_verified": True,
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(info=info),
        )

        result = YtdlpDownloader().probe("https://www.youtube.com/watch?v=UC_abc")

        assert result.status == ProbeStatus.OK
        assert result.uploader == "AliceChannel"
        assert result.uploader_id == "UC_aliceid"
        assert result.uploader_url == "https://www.youtube.com/@Alice"
        assert result.channel_follower_count == 42000
        assert result.uploader_thumbnail == "https://yt3.ggpht.com/alice.jpg"
        assert result.uploader_verified is True

    def test_uploader_thumbnail_as_list_of_dicts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When uploader_thumbnail is a list of dicts, the first url is used."""
        from vidscope.ports import ProbeStatus

        info: dict[str, Any] = {
            "id": "v2",
            "title": "Bob video",
            "uploader": "BobCreator",
            "uploader_id": "bob_id",
            "uploader_thumbnail": [
                {"url": "https://yt3.ggpht.com/bob_small.jpg", "width": 48},
                {"url": "https://yt3.ggpht.com/bob_large.jpg", "width": 240},
            ],
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(info=info),
        )

        result = YtdlpDownloader().probe("https://www.youtube.com/watch?v=v2")

        assert result.status == ProbeStatus.OK
        assert result.uploader_thumbnail == "https://yt3.ggpht.com/bob_small.jpg"

    def test_channel_follower_count_fallback_and_none_verified(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """channel_followers is used as fallback; uploader_verified=None
        when neither channel_verified nor uploader_verified is in info."""
        from vidscope.ports import ProbeStatus

        info: dict[str, Any] = {
            "id": "v3",
            "title": "TikTok video",
            "uploader": "TikToker",
            "uploader_id": "tt_123",
            "channel_followers": 9999,
            # No channel_verified / uploader_verified key → None
        }
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(info=info),
        )

        result = YtdlpDownloader().probe("https://www.tiktok.com/@TikToker/video/v3")

        assert result.status == ProbeStatus.OK
        assert result.channel_follower_count == 9999
        assert result.uploader_verified is None

    def test_all_creator_fields_none_when_info_lacks_them(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Minimal info_dict (only id + title) leaves all creator fields None —
        backward-compatible with existing probe callers."""
        from vidscope.ports import ProbeStatus

        info: dict[str, Any] = {"id": "minimal", "title": "Minimal"}
        _install_fake(
            monkeypatch,
            lambda *_args, **_kwargs: FakeYoutubeDL(info=info),
        )

        result = YtdlpDownloader().probe("https://www.instagram.com/reel/minimal/")

        assert result.status == ProbeStatus.OK
        assert result.uploader is None
        assert result.uploader_id is None
        assert result.uploader_url is None
        assert result.channel_follower_count is None
        assert result.uploader_thumbnail is None
        assert result.uploader_verified is None
