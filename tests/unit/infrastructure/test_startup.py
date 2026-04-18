"""Unit tests for vidscope.infrastructure.startup.

We monkeypatch ``shutil.which`` and ``subprocess.run`` so these tests
run without requiring ffmpeg on the host. yt-dlp is a real runtime
dependency so we exercise the happy path against the real import and
only simulate failures via monkeypatching.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from vidscope.infrastructure import startup


class TestCheckFfmpeg:
    def test_missing_binary_returns_not_ok(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(startup.shutil, "which", lambda _name: None)

        result = startup.check_ffmpeg()

        assert result.ok is False
        assert "not found" in result.version_or_error
        assert "winget" in result.remediation  # Windows hint
        assert "brew" in result.remediation  # macOS hint
        assert "apt" in result.remediation  # Linux hint

    def test_happy_path_returns_first_line_of_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(startup.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

        class FakeCompleted:
            returncode = 0
            stdout = "ffmpeg version 6.1 Copyright (c) 2000-2024\nbuilt with...\n"
            stderr = ""

        def fake_run(*_args: Any, **_kwargs: Any) -> FakeCompleted:
            return FakeCompleted()

        monkeypatch.setattr(startup.subprocess, "run", fake_run)

        result = startup.check_ffmpeg()

        assert result.ok is True
        assert result.version_or_error.startswith("ffmpeg version 6.1")
        assert result.remediation == ""

    def test_subprocess_timeout_is_surfaced(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(startup.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

        def fake_run(*_args: Any, **_kwargs: Any) -> Any:
            raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=5.0)

        monkeypatch.setattr(startup.subprocess, "run", fake_run)

        result = startup.check_ffmpeg()

        assert result.ok is False
        assert "timed out" in result.version_or_error

    def test_subprocess_non_zero_exit_is_surfaced(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(startup.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

        class FakeFailed:
            returncode = 1
            stdout = ""
            stderr = "ffmpeg: some error"

        monkeypatch.setattr(
            startup.subprocess, "run", lambda *a, **kw: FakeFailed()
        )

        result = startup.check_ffmpeg()

        assert result.ok is False
        assert "exited with code 1" in result.version_or_error

    def test_os_error_is_surfaced(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(startup.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

        def fake_run(*_args: Any, **_kwargs: Any) -> Any:
            raise OSError("permission denied")

        monkeypatch.setattr(startup.subprocess, "run", fake_run)

        result = startup.check_ffmpeg()

        assert result.ok is False
        assert "failed to execute" in result.version_or_error


class TestCheckYtdlp:
    def test_happy_path_finds_version(self) -> None:
        # yt-dlp is a real runtime dep so this actually imports it.
        result = startup.check_ytdlp()
        assert result.ok is True
        assert result.version_or_error  # non-empty version string
        assert result.remediation == ""

    def test_missing_version_attribute(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Replace the real yt_dlp module with a stub that has no version.
        import sys
        import types

        fake = types.ModuleType("yt_dlp")
        # No __version__, no version.__version__
        monkeypatch.setitem(sys.modules, "yt_dlp", fake)

        result = startup.check_ytdlp()

        assert result.ok is False
        assert "version attribute missing" in result.version_or_error


class TestCheckMcpSdk:
    """M002/S01/T03: check_mcp_sdk verifies the mcp package is importable."""

    def test_happy_path_returns_version(self) -> None:
        # mcp is a real runtime dep so this actually imports it
        result = startup.check_mcp_sdk()
        assert result.ok is True
        assert result.version_or_error  # non-empty version string
        assert result.remediation == ""

    def test_import_failure_returns_not_ok(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Replace the mcp module with something that raises ImportError
        # when touched. We do this by removing it from sys.modules AND
        # inserting a module-level stub that raises on attribute access.
        import sys

        # Remove any cached mcp from sys.modules so the re-import runs
        monkeypatch.delitem(sys.modules, "mcp", raising=False)

        # Force ImportError by breaking the module finder
        import importlib.machinery

        original_find = importlib.machinery.PathFinder.find_spec

        def blocking_find(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "mcp":
                return None
            return original_find(name, *args, **kwargs)

        monkeypatch.setattr(
            importlib.machinery.PathFinder, "find_spec", blocking_find
        )

        result = startup.check_mcp_sdk()
        assert result.ok is False
        assert "import failed" in result.version_or_error


class TestCheckCookies:
    """S07/T04: cookies check has three states (configured+ok,
    not configured, configured+missing)."""

    def _sandbox(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.infrastructure.config import reset_config_cache

        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("VIDSCOPE_COOKIES_FILE", raising=False)
        reset_config_cache()

    def test_not_configured_is_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._sandbox(tmp_path, monkeypatch)
        result = startup.check_cookies()
        assert result.name == "cookies"
        assert result.ok is True
        assert "not configured" in result.version_or_error
        assert "docs/cookies.md" in result.remediation

    def test_configured_and_present_is_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._sandbox(tmp_path, monkeypatch)
        cookies = tmp_path / "real-cookies.txt"
        cookies.write_text("# Netscape HTTP Cookie File\n")
        monkeypatch.setenv("VIDSCOPE_COOKIES_FILE", str(cookies))

        from vidscope.infrastructure.config import reset_config_cache

        reset_config_cache()

        result = startup.check_cookies()
        assert result.ok is True
        assert "configured at" in result.version_or_error
        assert str(cookies) in result.version_or_error
        assert result.remediation == ""

    def test_configured_but_missing_is_not_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._sandbox(tmp_path, monkeypatch)
        bad_path = tmp_path / "does-not-exist.txt"
        monkeypatch.setenv("VIDSCOPE_COOKIES_FILE", str(bad_path))

        from vidscope.infrastructure.config import reset_config_cache

        reset_config_cache()

        result = startup.check_cookies()
        assert result.ok is False
        assert "missing" in result.version_or_error
        assert "VIDSCOPE_COOKIES_FILE" in result.remediation


class TestCheckAnalyzer:
    def test_default_heuristic_is_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.infrastructure.config import reset_config_cache

        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("VIDSCOPE_ANALYZER", raising=False)
        reset_config_cache()

        result = startup.check_analyzer()
        assert result.ok is True
        assert "heuristic" in result.version_or_error
        assert "default" in result.version_or_error

    def test_stub_is_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.infrastructure.config import reset_config_cache

        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("VIDSCOPE_ANALYZER", "stub")
        reset_config_cache()

        result = startup.check_analyzer()
        assert result.ok is True
        assert "stub" in result.version_or_error

    def test_unknown_analyzer_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.infrastructure.config import reset_config_cache

        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("VIDSCOPE_ANALYZER", "not-a-real-provider")
        reset_config_cache()

        result = startup.check_analyzer()
        assert result.ok is False
        assert "unknown" in result.version_or_error.lower()
        assert "VIDSCOPE_ANALYZER" in result.remediation

    def test_groq_with_key_is_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.infrastructure.config import reset_config_cache

        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("VIDSCOPE_ANALYZER", "groq")
        monkeypatch.setenv("VIDSCOPE_GROQ_API_KEY", "fake-key")
        reset_config_cache()

        result = startup.check_analyzer()
        assert result.ok is True
        assert "groq" in result.version_or_error
        assert "key present" in result.version_or_error

    def test_groq_without_key_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.infrastructure.config import reset_config_cache

        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("VIDSCOPE_ANALYZER", "groq")
        monkeypatch.delenv("VIDSCOPE_GROQ_API_KEY", raising=False)
        reset_config_cache()

        result = startup.check_analyzer()
        assert result.ok is False
        assert "VIDSCOPE_GROQ_API_KEY" in result.version_or_error

    def test_anthropic_with_key_is_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vidscope.infrastructure.config import reset_config_cache

        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("VIDSCOPE_ANALYZER", "anthropic")
        monkeypatch.setenv("VIDSCOPE_ANTHROPIC_API_KEY", "sk-ant-fake")
        reset_config_cache()

        result = startup.check_analyzer()
        assert result.ok is True
        assert "anthropic" in result.version_or_error


class TestRunAllChecks:
    def test_returns_one_result_per_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Sandbox so check_cookies doesn't pick up a real cookies file
        from vidscope.infrastructure.config import reset_config_cache

        monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("VIDSCOPE_COOKIES_FILE", raising=False)
        monkeypatch.delenv("VIDSCOPE_ANALYZER", raising=False)
        reset_config_cache()

        monkeypatch.setattr(startup.shutil, "which", lambda _name: "/usr/bin/ffmpeg")

        class FakeCompleted:
            returncode = 0
            stdout = "ffmpeg version 6.1\n"
            stderr = ""

        monkeypatch.setattr(
            startup.subprocess, "run", lambda *a, **kw: FakeCompleted()
        )

        results = startup.run_all_checks()

        assert len(results) == 5
        names = {r.name for r in results}
        assert names == {"ffmpeg", "yt-dlp", "mcp", "cookies", "analyzer"}
