"""Tests for playwright_login adapter (auth extra).

capture_platform_cookies is tested by mocking playwright.sync_api so no
real browser is launched. _write_netscape is a pure function and tested
directly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from vidscope.adapters.auth.playwright_login import (
    SUPPORTED_PLATFORMS,
    _write_netscape,
    capture_platform_cookies,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_playwright_mock(cookies: list[dict[str, Any]]) -> MagicMock:
    """Build a sync_playwright mock that returns *cookies* on first poll."""
    page = MagicMock()

    context = MagicMock()
    context.cookies.return_value = cookies
    context.new_page.return_value = page

    browser = MagicMock()
    browser.new_context.return_value = context

    pw = MagicMock()
    pw.chromium.launch.return_value = browser

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=pw)
    cm.__exit__ = MagicMock(return_value=False)

    return MagicMock(return_value=cm)


def _inject_playwright(monkeypatch: pytest.MonkeyPatch, sync_playwright_mock: MagicMock) -> None:
    """Inject a fake playwright.sync_api into sys.modules."""
    fake_api = MagicMock()
    fake_api.sync_playwright = sync_playwright_mock

    fake_pkg = MagicMock()
    fake_pkg.sync_api = fake_api

    monkeypatch.setitem(sys.modules, "playwright", fake_pkg)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_api)


# ---------------------------------------------------------------------------
# _write_netscape
# ---------------------------------------------------------------------------


class TestWriteNetscape:
    def test_header_present(self, tmp_path: Path) -> None:
        dest = tmp_path / "c.txt"
        _write_netscape([], dest)
        assert dest.read_text(encoding="utf-8").startswith("# Netscape HTTP Cookie File\n")

    def test_empty_cookies_writes_header_only(self, tmp_path: Path) -> None:
        dest = tmp_path / "c.txt"
        _write_netscape([], dest)
        lines = [l for l in dest.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
        assert lines == []

    def test_single_cookie_fields(self, tmp_path: Path) -> None:
        dest = tmp_path / "c.txt"
        _write_netscape([
            {"domain": "instagram.com", "name": "sessionid", "value": "tok",
             "path": "/foo", "secure": True, "expires": 9999999999},
        ], dest)
        lines = [l for l in dest.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
        assert len(lines) == 1
        cols = lines[0].split("\t")
        assert cols[0] == ".instagram.com"   # domain with dot
        assert cols[1] == "TRUE"             # include_subdomains
        assert cols[2] == "/foo"             # path
        assert cols[3] == "TRUE"             # secure
        assert cols[4] == "9999999999"       # expiry
        assert cols[5] == "sessionid"        # name
        assert cols[6] == "tok"              # value

    def test_domain_dot_prefix_not_doubled(self, tmp_path: Path) -> None:
        dest = tmp_path / "c.txt"
        _write_netscape([
            {"domain": ".instagram.com", "name": "x", "value": "y",
             "path": "/", "secure": False, "expires": 0},
        ], dest)
        content = dest.read_text(encoding="utf-8")
        assert "..instagram.com" not in content
        assert ".instagram.com\t" in content

    def test_negative_expiry_becomes_zero(self, tmp_path: Path) -> None:
        dest = tmp_path / "c.txt"
        _write_netscape([
            {"domain": "x.com", "name": "a", "value": "b",
             "path": "/", "secure": False, "expires": -1},
        ], dest)
        lines = [l for l in dest.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
        assert lines[0].split("\t")[4] == "0"

    def test_secure_false(self, tmp_path: Path) -> None:
        dest = tmp_path / "c.txt"
        _write_netscape([
            {"domain": "a.com", "name": "k", "value": "v",
             "path": "/", "secure": False, "expires": 0},
        ], dest)
        lines = [l for l in dest.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
        assert lines[0].split("\t")[3] == "FALSE"

    def test_multiple_cookies(self, tmp_path: Path) -> None:
        dest = tmp_path / "c.txt"
        _write_netscape([
            {"domain": "a.com", "name": "k1", "value": "v1",
             "path": "/", "secure": False, "expires": 0},
            {"domain": "b.com", "name": "k2", "value": "v2",
             "path": "/", "secure": True, "expires": 1},
        ], dest)
        lines = [l for l in dest.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# SUPPORTED_PLATFORMS
# ---------------------------------------------------------------------------


class TestSupportedPlatforms:
    def test_is_tuple(self) -> None:
        assert isinstance(SUPPORTED_PLATFORMS, tuple)

    def test_contains_instagram(self) -> None:
        assert "instagram" in SUPPORTED_PLATFORMS

    def test_contains_tiktok(self) -> None:
        assert "tiktok" in SUPPORTED_PLATFORMS

    def test_contains_youtube(self) -> None:
        assert "youtube" in SUPPORTED_PLATFORMS


# ---------------------------------------------------------------------------
# capture_platform_cookies
# ---------------------------------------------------------------------------


class TestCapturePlatformCookies:
    def test_unknown_platform_raises_key_error(self, tmp_path: Path) -> None:
        with pytest.raises(KeyError):
            capture_platform_cookies("myspace", tmp_path / "c.txt")

    def test_playwright_not_installed_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "playwright", None)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
        with pytest.raises(ImportError, match="playwright is not installed"):
            capture_platform_cookies("instagram", tmp_path / "c.txt")

    def test_success_returns_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cookies = [
            {"name": "sessionid", "value": "tok", "domain": "instagram.com",
             "path": "/", "secure": True, "expires": 9999},
            {"name": "csrftoken", "value": "csrf", "domain": "instagram.com",
             "path": "/", "secure": False, "expires": 0},
        ]
        sp_mock = _make_playwright_mock(cookies)
        _inject_playwright(monkeypatch, sp_mock)

        dest = tmp_path / "cookies.txt"
        count = capture_platform_cookies("instagram", dest, timeout_seconds=30)

        assert count == 2
        assert dest.exists()

    def test_success_writes_netscape_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cookies = [
            {"name": "sessionid", "value": "mytoken", "domain": "instagram.com",
             "path": "/", "secure": True, "expires": 9999},
        ]
        sp_mock = _make_playwright_mock(cookies)
        _inject_playwright(monkeypatch, sp_mock)

        dest = tmp_path / "cookies.txt"
        capture_platform_cookies("instagram", dest, timeout_seconds=30)

        content = dest.read_text(encoding="utf-8")
        assert "# Netscape HTTP Cookie File" in content
        assert "sessionid" in content
        assert "mytoken" in content

    def test_domain_filter_excludes_other_domains(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cookies = [
            {"name": "sessionid", "value": "tok", "domain": "instagram.com",
             "path": "/", "secure": True, "expires": 9999},
            {"name": "other_cookie", "value": "val", "domain": "unrelated.com",
             "path": "/", "secure": False, "expires": 0},
        ]
        sp_mock = _make_playwright_mock(cookies)
        _inject_playwright(monkeypatch, sp_mock)

        dest = tmp_path / "cookies.txt"
        count = capture_platform_cookies("instagram", dest, timeout_seconds=30)

        # Only instagram.com cookies should be written
        assert count == 1
        assert "unrelated.com" not in dest.read_text(encoding="utf-8")

    def test_timeout_raises_runtime_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Return cookies with no sessionid → loop never exits before deadline
        cookies = [
            {"name": "not_session", "value": "x", "domain": "instagram.com",
             "path": "/", "secure": False, "expires": 0},
        ]
        sp_mock = _make_playwright_mock(cookies)
        _inject_playwright(monkeypatch, sp_mock)

        # Patch time.monotonic to make deadline expire immediately
        call_count = 0

        def fake_monotonic() -> float:
            nonlocal call_count
            call_count += 1
            # First call (deadline=...) → 0.0; subsequent → past deadline
            return 0.0 if call_count == 1 else 9999.0

        import vidscope.adapters.auth.playwright_login as mod
        monkeypatch.setattr(mod.time, "monotonic", fake_monotonic)

        with pytest.raises(RuntimeError, match="Login timed out"):
            capture_platform_cookies("instagram", tmp_path / "c.txt", timeout_seconds=1)

    def test_browser_is_launched_non_headless(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cookies = [
            {"name": "sessionid", "value": "t", "domain": "instagram.com",
             "path": "/", "secure": True, "expires": 1},
        ]
        sp_mock = _make_playwright_mock(cookies)
        _inject_playwright(monkeypatch, sp_mock)

        capture_platform_cookies("instagram", tmp_path / "c.txt", timeout_seconds=30)

        # Verify headless=False was passed to chromium.launch
        pw = sp_mock.return_value.__enter__.return_value
        pw.chromium.launch.assert_called_once_with(headless=False)

    def test_tiktok_platform_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cookies = [
            {"name": "sessionid", "value": "tiktok_tok", "domain": "tiktok.com",
             "path": "/", "secure": True, "expires": 9999},
        ]
        sp_mock = _make_playwright_mock(cookies)
        _inject_playwright(monkeypatch, sp_mock)

        dest = tmp_path / "cookies.txt"
        count = capture_platform_cookies("tiktok", dest, timeout_seconds=30)

        assert count == 1
        assert "tiktok_tok" in dest.read_text(encoding="utf-8")
