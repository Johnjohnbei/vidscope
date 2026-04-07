"""Tests for the cookies management use cases.

Use cases take simple ``data_dir: Path`` (and optionally
``configured_cookies_file: Path | None``) so they don't need a Config
fixture and stay decoupled from infrastructure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vidscope.application.cookies import (
    ClearCookiesUseCase,
    CookiesProbeUseCase,
    GetCookiesStatusUseCase,
    SetCookiesUseCase,
)
from vidscope.ports import ChannelEntry, IngestOutcome, ProbeResult, ProbeStatus


class _FakeDownloader:
    """Stub Downloader for the cookies test probe.

    Only ``probe()`` is exercised by CookiesProbeUseCase. The other
    methods raise to make accidental calls obvious.
    """

    def __init__(self, probe_result: ProbeResult) -> None:
        self._probe_result = probe_result
        self.calls: list[str] = []

    def probe(self, url: str) -> ProbeResult:
        self.calls.append(url)
        return self._probe_result

    def download(self, url: str, destination_dir: str) -> IngestOutcome:
        raise NotImplementedError

    def list_channel_videos(
        self, url: str, *, limit: int = 10
    ) -> list[ChannelEntry]:
        raise NotImplementedError


def _valid_cookies_content() -> str:
    return (
        "# Netscape HTTP Cookie File\n"
        ".instagram.com\tTRUE\t/\tTRUE\t1893456000\tsessionid\tabc123\n"
        ".instagram.com\tTRUE\t/\tFALSE\t1893456000\tcsrftoken\tdef456\n"
    )


# ---------------------------------------------------------------------------
# SetCookiesUseCase
# ---------------------------------------------------------------------------


class TestSetCookies:
    def test_copies_valid_file(self, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text(_valid_cookies_content(), encoding="utf-8")
        data_dir = tmp_path / "data"

        result = SetCookiesUseCase(data_dir=data_dir).execute(source)

        assert result.success is True
        assert result.destination == data_dir / "cookies.txt"
        assert result.entries_count == 2
        assert (data_dir / "cookies.txt").exists()
        assert "copied 2" in result.message

    def test_invalid_source_does_not_overwrite(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        existing = data_dir / "cookies.txt"
        existing.write_text(_valid_cookies_content(), encoding="utf-8")

        source = tmp_path / "broken.txt"
        source.write_text("", encoding="utf-8")

        result = SetCookiesUseCase(data_dir=data_dir).execute(source)

        assert result.success is False
        assert "invalid" in result.message
        # Existing file is untouched
        assert existing.read_text(encoding="utf-8") == _valid_cookies_content()

    def test_missing_source_fails_cleanly(self, tmp_path: Path) -> None:
        result = SetCookiesUseCase(data_dir=tmp_path).execute(
            tmp_path / "missing.txt"
        )

        assert result.success is False
        assert "does not exist" in result.message

    def test_overwrites_when_destination_exists(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "cookies.txt").write_text("# old\n", encoding="utf-8")

        source = tmp_path / "new.txt"
        source.write_text(_valid_cookies_content(), encoding="utf-8")

        result = SetCookiesUseCase(data_dir=data_dir).execute(source)

        assert result.success is True
        assert (data_dir / "cookies.txt").read_text(encoding="utf-8") == _valid_cookies_content()

    def test_creates_data_dir_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "nested" / "data"
        source = tmp_path / "source.txt"
        source.write_text(_valid_cookies_content(), encoding="utf-8")

        result = SetCookiesUseCase(data_dir=nested).execute(source)

        assert result.success is True
        assert (nested / "cookies.txt").exists()


# ---------------------------------------------------------------------------
# GetCookiesStatusUseCase
# ---------------------------------------------------------------------------


class TestGetCookiesStatus:
    def test_no_cookies_file(self, tmp_path: Path) -> None:
        result = GetCookiesStatusUseCase(
            data_dir=tmp_path,
            configured_cookies_file=None,
        ).execute()

        assert result.default_path == tmp_path / "cookies.txt"
        assert result.default_exists is False
        assert result.size_bytes == 0
        assert result.modified_at is None
        assert result.validation.ok is False
        assert result.env_override_path is None
        assert result.active_path is None

    def test_valid_cookies_file_present(self, tmp_path: Path) -> None:
        cookies = tmp_path / "cookies.txt"
        cookies.write_text(_valid_cookies_content(), encoding="utf-8")

        result = GetCookiesStatusUseCase(
            data_dir=tmp_path,
            configured_cookies_file=cookies,
        ).execute()

        assert result.default_exists is True
        assert result.size_bytes > 0
        assert result.modified_at is not None
        assert result.validation.ok is True
        assert result.validation.entries_count == 2

    def test_env_override_when_pointing_elsewhere(self, tmp_path: Path) -> None:
        elsewhere = tmp_path / "elsewhere.txt"
        elsewhere.write_text(_valid_cookies_content(), encoding="utf-8")

        result = GetCookiesStatusUseCase(
            data_dir=tmp_path,
            configured_cookies_file=elsewhere,  # env override target
        ).execute()

        assert result.env_override_path == elsewhere
        assert result.active_path == elsewhere
        assert result.default_exists is False

    def test_no_env_override_when_active_equals_default(
        self, tmp_path: Path
    ) -> None:
        cookies = tmp_path / "cookies.txt"
        cookies.write_text(_valid_cookies_content(), encoding="utf-8")

        result = GetCookiesStatusUseCase(
            data_dir=tmp_path,
            configured_cookies_file=cookies,  # active == default
        ).execute()

        assert result.env_override_path is None
        assert result.active_path == cookies


# ---------------------------------------------------------------------------
# ClearCookiesUseCase
# ---------------------------------------------------------------------------


class TestClearCookies:
    def test_removes_existing_file(self, tmp_path: Path) -> None:
        cookies = tmp_path / "cookies.txt"
        cookies.write_text(_valid_cookies_content(), encoding="utf-8")

        result = ClearCookiesUseCase(data_dir=tmp_path).execute()

        assert result.success is True
        assert result.removed_path == cookies
        assert not cookies.exists()

    def test_returns_failure_when_no_file(self, tmp_path: Path) -> None:
        result = ClearCookiesUseCase(data_dir=tmp_path).execute()

        assert result.success is False
        assert result.removed_path is None
        assert "no cookies file" in result.message

    def test_only_touches_default_path(self, tmp_path: Path) -> None:
        # Even if env override points elsewhere, clear must only
        # remove the canonical path, never the override file.
        elsewhere = tmp_path / "elsewhere.txt"
        elsewhere.write_text(_valid_cookies_content(), encoding="utf-8")

        result = ClearCookiesUseCase(data_dir=tmp_path).execute()

        # No file at the canonical path → fail
        assert result.success is False
        # Override file is NOT touched (clear only knows about data_dir)
        assert elsewhere.exists()

    def test_unlink_failure_returns_error_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cookies = tmp_path / "cookies.txt"
        cookies.write_text(_valid_cookies_content(), encoding="utf-8")

        def fake_unlink(self: Path) -> None:
            raise PermissionError("denied")

        monkeypatch.setattr(Path, "unlink", fake_unlink)

        result = ClearCookiesUseCase(data_dir=tmp_path).execute()

        assert result.success is False
        assert "denied" in result.message


# ---------------------------------------------------------------------------
# CookiesProbeUseCase (probe)
# ---------------------------------------------------------------------------


class TestCookiesProbe:
    def test_ok_with_cookies_configured(self) -> None:
        downloader = _FakeDownloader(
            ProbeResult(
                status=ProbeStatus.OK,
                url="https://example.com/reel/abc",
                detail="resolved: My Test Reel",
                title="My Test Reel",
            )
        )
        result = CookiesProbeUseCase(
            downloader=downloader,
            cookies_configured=True,
        ).execute()

        assert result.probe.status == ProbeStatus.OK
        assert "cookies work" in result.interpretation
        assert "My Test Reel" in result.interpretation
        # Default URL was used
        assert len(downloader.calls) == 1

    def test_ok_without_cookies_configured(self) -> None:
        downloader = _FakeDownloader(
            ProbeResult(
                status=ProbeStatus.OK,
                url="https://www.youtube.com/shorts/abc",
                detail="resolved: A Public Short",
                title="A Public Short",
            )
        )
        result = CookiesProbeUseCase(
            downloader=downloader,
            cookies_configured=False,
        ).execute(url="https://www.youtube.com/shorts/abc")

        assert result.probe.status == ProbeStatus.OK
        assert "no cookies needed" in result.interpretation
        assert downloader.calls == ["https://www.youtube.com/shorts/abc"]

    def test_auth_required_with_cookies_says_expired(self) -> None:
        downloader = _FakeDownloader(
            ProbeResult(
                status=ProbeStatus.AUTH_REQUIRED,
                url="https://www.instagram.com/reel/xyz",
                detail="login required",
            )
        )
        result = CookiesProbeUseCase(
            downloader=downloader,
            cookies_configured=True,
        ).execute()

        assert result.probe.status == ProbeStatus.AUTH_REQUIRED
        assert "expired" in result.interpretation
        assert "vidscope cookies set" in result.interpretation

    def test_auth_required_without_cookies_says_install(self) -> None:
        downloader = _FakeDownloader(
            ProbeResult(
                status=ProbeStatus.AUTH_REQUIRED,
                url="https://www.instagram.com/reel/xyz",
                detail="login required",
            )
        )
        result = CookiesProbeUseCase(
            downloader=downloader,
            cookies_configured=False,
        ).execute()

        assert result.probe.status == ProbeStatus.AUTH_REQUIRED
        assert "none are configured" in result.interpretation
        assert "docs/cookies.md" in result.interpretation

    def test_not_found(self) -> None:
        downloader = _FakeDownloader(
            ProbeResult(
                status=ProbeStatus.NOT_FOUND,
                url="https://www.instagram.com/reel/dead",
                detail="video unavailable",
            )
        )
        result = CookiesProbeUseCase(
            downloader=downloader,
            cookies_configured=True,
        ).execute()

        assert result.probe.status == ProbeStatus.NOT_FOUND
        assert "not found" in result.interpretation

    def test_network_error(self) -> None:
        downloader = _FakeDownloader(
            ProbeResult(
                status=ProbeStatus.NETWORK_ERROR,
                url="https://example.com/x",
                detail="connection refused",
            )
        )
        result = CookiesProbeUseCase(
            downloader=downloader,
            cookies_configured=False,
        ).execute()

        assert result.probe.status == ProbeStatus.NETWORK_ERROR
        assert "network" in result.interpretation

    def test_unsupported(self) -> None:
        downloader = _FakeDownloader(
            ProbeResult(
                status=ProbeStatus.UNSUPPORTED,
                url="https://example.com/foo",
                detail="unsupported url",
            )
        )
        result = CookiesProbeUseCase(
            downloader=downloader,
            cookies_configured=True,
        ).execute()

        assert result.probe.status == ProbeStatus.UNSUPPORTED
        assert "unsupported" in result.interpretation

    def test_default_url_used_when_url_arg_is_none(self) -> None:
        downloader = _FakeDownloader(
            ProbeResult(
                status=ProbeStatus.OK,
                url="dummy",
                detail="ok",
                title="dummy",
            )
        )
        CookiesProbeUseCase(
            downloader=downloader,
            cookies_configured=True,
        ).execute(None)

        # Default URL should hit instagram.com
        assert len(downloader.calls) == 1
        assert "instagram.com" in downloader.calls[0]
