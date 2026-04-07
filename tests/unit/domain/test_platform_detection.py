"""Unit tests for :func:`vidscope.domain.detect_platform`.

Pure-Python assertions. Zero I/O, zero third-party deps beyond pytest.
"""

from __future__ import annotations

import pytest

from vidscope.domain import IngestError, Platform, detect_platform


class TestYouTube:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=xyz",
            "https://m.youtube.com/watch?v=abc",
            "https://music.youtube.com/watch?v=def",
            "https://youtu.be/abc123",
            "http://www.youtube.com/watch?v=http-works-too",
            "https://www.youtube.com/shorts/abc",
        ],
    )
    def test_resolves_to_youtube(self, url: str) -> None:
        assert detect_platform(url) is Platform.YOUTUBE

    def test_case_insensitive_host(self) -> None:
        assert (
            detect_platform("https://WWW.YouTube.com/watch?v=abc")
            is Platform.YOUTUBE
        )


class TestTikTok:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.tiktok.com/@user/video/1234567890",
            "https://tiktok.com/@user/video/1234567890",
            "https://m.tiktok.com/@user/video/1234567890",
            "https://vm.tiktok.com/abc",
        ],
    )
    def test_resolves_to_tiktok(self, url: str) -> None:
        assert detect_platform(url) is Platform.TIKTOK


class TestInstagram:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.instagram.com/reel/Cabc/",
            "https://instagram.com/p/Cabc/",
            "https://www.instagram.com/stories/user/1234/",
        ],
    )
    def test_resolves_to_instagram(self, url: str) -> None:
        assert detect_platform(url) is Platform.INSTAGRAM


class TestRejections:
    def test_empty_url_raises(self) -> None:
        with pytest.raises(IngestError, match="empty"):
            detect_platform("")

    def test_whitespace_url_raises(self) -> None:
        with pytest.raises(IngestError, match="empty"):
            detect_platform("   ")

    def test_none_url_raises(self) -> None:
        with pytest.raises(IngestError, match="None"):
            detect_platform(None)  # type: ignore[arg-type]

    def test_javascript_url_rejected(self) -> None:
        with pytest.raises(IngestError, match="http or https"):
            detect_platform("javascript:alert('xss')")

    def test_file_url_rejected(self) -> None:
        with pytest.raises(IngestError, match="http or https"):
            detect_platform("file:///etc/passwd")

    def test_ftp_url_rejected(self) -> None:
        with pytest.raises(IngestError, match="http or https"):
            detect_platform("ftp://example.com/video.mp4")

    def test_bare_word_rejected(self) -> None:
        with pytest.raises(IngestError):
            detect_platform("not a url")

    def test_unsupported_platform_rejected(self) -> None:
        with pytest.raises(IngestError, match="unsupported platform"):
            detect_platform("https://vimeo.com/12345")

    def test_another_unsupported_platform_rejected(self) -> None:
        with pytest.raises(IngestError, match="unsupported platform"):
            detect_platform("https://www.dailymotion.com/video/x8abc")

    def test_subdomain_of_unsupported_rejected(self) -> None:
        with pytest.raises(IngestError, match="unsupported platform"):
            detect_platform("https://video.example.com/foo")

    def test_error_lists_supported_platforms(self) -> None:
        with pytest.raises(IngestError) as exc_info:
            detect_platform("https://vimeo.com/12345")
        message = str(exc_info.value)
        assert "instagram" in message
        assert "tiktok" in message
        assert "youtube" in message

    def test_lookalike_host_suffix_rejected(self) -> None:
        """A host that ends in 'youtube.com' but is actually a different
        domain (e.g. evilyoutube.com) must not match. Our suffix check
        requires either an exact host match or a '.youtube.com' suffix."""
        with pytest.raises(IngestError, match="unsupported platform"):
            detect_platform("https://evilyoutube.com/watch?v=x")


class TestErrorProperties:
    def test_errors_are_not_retryable(self) -> None:
        with pytest.raises(IngestError) as exc_info:
            detect_platform("https://vimeo.com/foo")
        assert exc_info.value.retryable is False

    def test_errors_preserve_stage(self) -> None:
        from vidscope.domain import StageName

        with pytest.raises(IngestError) as exc_info:
            detect_platform("")
        assert exc_info.value.stage is StageName.INGEST
