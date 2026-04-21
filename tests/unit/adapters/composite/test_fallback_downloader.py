"""Tests for FallbackDownloader and PlatformRoutingDownloader."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vidscope.adapters.composite import FallbackDownloader, PlatformRoutingDownloader
from vidscope.domain import IngestError, MediaType, Platform, PlatformId
from vidscope.ports import IngestOutcome, ProbeResult, ProbeStatus


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _outcome(**kwargs) -> IngestOutcome:
    defaults = dict(
        platform=Platform.INSTAGRAM,
        platform_id=PlatformId("abc"),
        url="https://www.instagram.com/p/abc/",
        media_path="/tmp/abc.jpg",
        media_type=MediaType.IMAGE,
    )
    return IngestOutcome(**{**defaults, **kwargs})


def _make_downloader(
    *,
    download_return: IngestOutcome | None = None,
    download_raise: Exception | None = None,
    list_return: list | None = None,
    probe_return: ProbeResult | None = None,
) -> MagicMock:
    dl = MagicMock()
    if download_raise is not None:
        dl.download.side_effect = download_raise
    else:
        dl.download.return_value = download_return or _outcome()
    dl.list_channel_videos.return_value = list_return or []
    dl.probe.return_value = probe_return or ProbeResult(
        status=ProbeStatus.OK, url="http://x", detail="ok"
    )
    return dl


# ---------------------------------------------------------------------------
# download — primary succeeds
# ---------------------------------------------------------------------------


class TestDownloadPrimarySucceeds:
    def test_returns_primary_result(self, tmp_path) -> None:
        result = _outcome(media_path="/primary.jpg")
        primary = _make_downloader(download_return=result)
        fallback = _make_downloader()

        fd = FallbackDownloader(primary=primary, fallback=fallback)
        assert fd.download("http://x", str(tmp_path)) is result

    def test_fallback_not_called_on_success(self, tmp_path) -> None:
        primary = _make_downloader(download_return=_outcome())
        fallback = _make_downloader()

        FallbackDownloader(primary=primary, fallback=fallback).download(
            "http://x", str(tmp_path)
        )

        fallback.download.assert_not_called()


# ---------------------------------------------------------------------------
# download — primary fails, fallback triggered
# ---------------------------------------------------------------------------


class TestDownloadFallbackTriggered:
    def test_falls_back_on_matching_non_retryable_error(self, tmp_path) -> None:
        fallback_result = _outcome(media_path="/fallback.jpg")
        primary = _make_downloader(
            download_raise=IngestError("No video formats found!", retryable=False)
        )
        fallback = _make_downloader(download_return=fallback_result)

        result = FallbackDownloader(primary=primary, fallback=fallback).download(
            "http://x", str(tmp_path)
        )

        assert result is fallback_result
        fallback.download.assert_called_once()

    def test_case_insensitive_marker_match(self, tmp_path) -> None:
        primary = _make_downloader(
            download_raise=IngestError("NO VIDEO FORMATS FOUND", retryable=False)
        )
        fallback = _make_downloader(download_return=_outcome())

        FallbackDownloader(primary=primary, fallback=fallback).download(
            "http://x", str(tmp_path)
        )

        fallback.download.assert_called_once()

    def test_custom_fallback_on_marker(self, tmp_path) -> None:
        primary = _make_downloader(
            download_raise=IngestError("image only content", retryable=False)
        )
        fallback = _make_downloader(download_return=_outcome())

        FallbackDownloader(
            primary=primary,
            fallback=fallback,
            fallback_on=("image only content",),
        ).download("http://x", str(tmp_path))

        fallback.download.assert_called_once()

    def test_passes_same_args_to_fallback(self, tmp_path) -> None:
        url = "https://www.instagram.com/p/XYZ/"
        dest = str(tmp_path)
        primary = _make_downloader(
            download_raise=IngestError("no video formats found", retryable=False)
        )
        fallback = _make_downloader(download_return=_outcome())

        FallbackDownloader(primary=primary, fallback=fallback).download(url, dest)

        fallback.download.assert_called_once_with(url, dest)


# ---------------------------------------------------------------------------
# download — primary fails, error NOT forwarded to fallback
# ---------------------------------------------------------------------------


class TestDownloadErrorNotForwarded:
    def test_retryable_error_is_reraised(self, tmp_path) -> None:
        exc = IngestError("no video formats found", retryable=True)
        primary = _make_downloader(download_raise=exc)
        fallback = _make_downloader()

        with pytest.raises(IngestError) as info:
            FallbackDownloader(primary=primary, fallback=fallback).download(
                "http://x", str(tmp_path)
            )

        assert info.value is exc
        fallback.download.assert_not_called()

    def test_non_matching_error_is_reraised(self, tmp_path) -> None:
        exc = IngestError("network timeout", retryable=False)
        primary = _make_downloader(download_raise=exc)
        fallback = _make_downloader()

        with pytest.raises(IngestError) as info:
            FallbackDownloader(primary=primary, fallback=fallback).download(
                "http://x", str(tmp_path)
            )

        assert info.value is exc
        fallback.download.assert_not_called()

    def test_non_ingest_error_propagates(self, tmp_path) -> None:
        primary = _make_downloader(download_raise=RuntimeError("boom"))
        fallback = _make_downloader()

        with pytest.raises(RuntimeError):
            FallbackDownloader(primary=primary, fallback=fallback).download(
                "http://x", str(tmp_path)
            )

        fallback.download.assert_not_called()


# ---------------------------------------------------------------------------
# list_channel_videos and probe — always primary
# ---------------------------------------------------------------------------


class TestDelegation:
    def test_list_channel_videos_delegates_to_primary(self) -> None:
        from vidscope.ports import ChannelEntry

        entries = [ChannelEntry(platform_id=PlatformId("v1"), url="http://v1")]
        primary = _make_downloader(list_return=entries)
        fallback = _make_downloader()

        result = FallbackDownloader(primary=primary, fallback=fallback).list_channel_videos(
            "http://channel", limit=5
        )

        assert result is entries
        primary.list_channel_videos.assert_called_once_with("http://channel", limit=5)
        fallback.list_channel_videos.assert_not_called()

    def test_probe_delegates_to_primary(self) -> None:
        probe = ProbeResult(status=ProbeStatus.OK, url="http://x", detail="fine")
        primary = _make_downloader(probe_return=probe)
        fallback = _make_downloader()

        result = FallbackDownloader(primary=primary, fallback=fallback).probe("http://x")

        assert result is probe
        primary.probe.assert_called_once_with("http://x")
        fallback.probe.assert_not_called()


# ===========================================================================
# PlatformRoutingDownloader
# ===========================================================================

_INSTAGRAM_URL = "https://www.instagram.com/p/ABC123/"
_YOUTUBE_URL = "https://www.youtube.com/watch?v=XYZ"
_TIKTOK_URL = "https://www.tiktok.com/@user/video/123"


class TestPlatformRoutingDownloaderInstagram:
    """Instagram URLs → InstaLoaderDownloader first."""

    def test_instagram_calls_instaloader_first(self, tmp_path) -> None:
        result = _outcome(media_path="/insta.jpg")
        instaloader = _make_downloader(download_return=result)
        ytdlp = _make_downloader()

        r = PlatformRoutingDownloader(ytdlp=ytdlp, instaloader=instaloader).download(
            _INSTAGRAM_URL, str(tmp_path)
        )

        assert r is result
        instaloader.download.assert_called_once_with(_INSTAGRAM_URL, str(tmp_path))
        ytdlp.download.assert_not_called()

    def test_instagram_reel_falls_back_to_ytdlp(self, tmp_path) -> None:
        # InstaLoaderDownloader raises "no downloadable images found" for pure Reels.
        reel_result = _outcome(media_path="/reel.mp4", media_type=MediaType.VIDEO)
        instaloader = _make_downloader(
            download_raise=IngestError("no downloadable images found for post 'ABC123'", retryable=False)
        )
        ytdlp = _make_downloader(download_return=reel_result)

        r = PlatformRoutingDownloader(ytdlp=ytdlp, instaloader=instaloader).download(
            _INSTAGRAM_URL, str(tmp_path)
        )

        assert r is reel_result
        ytdlp.download.assert_called_once_with(_INSTAGRAM_URL, str(tmp_path))

    def test_instagram_fallback_case_insensitive(self, tmp_path) -> None:
        instaloader = _make_downloader(
            download_raise=IngestError("No Downloadable Images Found", retryable=False)
        )
        ytdlp = _make_downloader(download_return=_outcome())

        PlatformRoutingDownloader(ytdlp=ytdlp, instaloader=instaloader).download(
            _INSTAGRAM_URL, str(tmp_path)
        )

        ytdlp.download.assert_called_once()

    def test_instagram_retryable_error_reraised(self, tmp_path) -> None:
        exc = IngestError("no downloadable images found", retryable=True)
        instaloader = _make_downloader(download_raise=exc)
        ytdlp = _make_downloader()

        with pytest.raises(IngestError) as info:
            PlatformRoutingDownloader(ytdlp=ytdlp, instaloader=instaloader).download(
                _INSTAGRAM_URL, str(tmp_path)
            )

        assert info.value is exc
        ytdlp.download.assert_not_called()

    def test_instagram_non_matching_error_reraised(self, tmp_path) -> None:
        exc = IngestError("rate limit hit", retryable=False)
        instaloader = _make_downloader(download_raise=exc)
        ytdlp = _make_downloader()

        with pytest.raises(IngestError) as info:
            PlatformRoutingDownloader(ytdlp=ytdlp, instaloader=instaloader).download(
                _INSTAGRAM_URL, str(tmp_path)
            )

        assert info.value is exc
        ytdlp.download.assert_not_called()


class TestPlatformRoutingDownloaderNonInstagram:
    """Non-Instagram URLs → YtdlpDownloader directly."""

    def test_youtube_calls_ytdlp_directly(self, tmp_path) -> None:
        result = _outcome(platform=Platform.YOUTUBE, media_path="/yt.mp4")
        ytdlp = _make_downloader(download_return=result)
        instaloader = _make_downloader()

        r = PlatformRoutingDownloader(ytdlp=ytdlp, instaloader=instaloader).download(
            _YOUTUBE_URL, str(tmp_path)
        )

        assert r is result
        ytdlp.download.assert_called_once_with(_YOUTUBE_URL, str(tmp_path))
        instaloader.download.assert_not_called()

    def test_tiktok_calls_ytdlp_directly(self, tmp_path) -> None:
        ytdlp = _make_downloader(download_return=_outcome())
        instaloader = _make_downloader()

        PlatformRoutingDownloader(ytdlp=ytdlp, instaloader=instaloader).download(
            _TIKTOK_URL, str(tmp_path)
        )

        ytdlp.download.assert_called_once()
        instaloader.download.assert_not_called()


class TestPlatformRoutingDownloaderDelegation:
    """list_channel_videos and probe always delegate to yt-dlp."""

    def test_list_channel_videos_delegates_to_ytdlp(self) -> None:
        from vidscope.ports import ChannelEntry

        entries = [ChannelEntry(platform_id=PlatformId("v1"), url="http://v1")]
        ytdlp = _make_downloader(list_return=entries)
        instaloader = _make_downloader()

        result = PlatformRoutingDownloader(ytdlp=ytdlp, instaloader=instaloader).list_channel_videos(
            "http://channel", limit=3
        )

        assert result is entries
        ytdlp.list_channel_videos.assert_called_once_with("http://channel", limit=3)
        instaloader.list_channel_videos.assert_not_called()

    def test_probe_delegates_to_ytdlp(self) -> None:
        probe = ProbeResult(status=ProbeStatus.OK, url="http://x", detail="fine")
        ytdlp = _make_downloader(probe_return=probe)
        instaloader = _make_downloader()

        result = PlatformRoutingDownloader(ytdlp=ytdlp, instaloader=instaloader).probe(
            _INSTAGRAM_URL
        )

        assert result is probe
        ytdlp.probe.assert_called_once_with(_INSTAGRAM_URL)
        instaloader.probe.assert_not_called()
