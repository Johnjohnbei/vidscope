"""CLI tests for the `vidscope cookies` sub-application."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from vidscope.cli.app import EXIT_OK, EXIT_USER_ERROR, app
from vidscope.infrastructure.config import reset_config_cache


def _valid_cookies_content() -> str:
    return (
        "# Netscape HTTP Cookie File\n"
        ".instagram.com\tTRUE\t/\tTRUE\t1893456000\tsessionid\tabc123\n"
        ".instagram.com\tTRUE\t/\tFALSE\t1893456000\tcsrftoken\tdef456\n"
    )


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VIDSCOPE_COOKIES_FILE", raising=False)
    reset_config_cache()
    yield
    reset_config_cache()


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# vidscope cookies --help
# ---------------------------------------------------------------------------


class TestCookiesHelp:
    def test_help_lists_subcommands(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["cookies", "--help"])
        assert result.exit_code == EXIT_OK
        for cmd in ("set", "status", "clear", "test"):
            assert cmd in result.stdout


# ---------------------------------------------------------------------------
# vidscope cookies status
# ---------------------------------------------------------------------------


class TestCookiesStatus:
    def test_status_no_cookies(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(app, ["cookies", "status"])
        assert result.exit_code == EXIT_OK
        assert "default path" in result.stdout
        assert "no" in result.stdout  # default exists: no
        assert "cookies feature disabled" in result.stdout

    def test_status_with_valid_cookies(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # Pre-seed a valid cookies file at the canonical location
        (tmp_path / "cookies.txt").write_text(
            _valid_cookies_content(), encoding="utf-8"
        )
        reset_config_cache()  # so config picks up the new file

        result = runner.invoke(app, ["cookies", "status"])
        assert result.exit_code == EXIT_OK
        assert "yes" in result.stdout  # default exists: yes
        assert "2 entries" in result.stdout
        assert "active path" in result.stdout

    def test_status_with_env_override(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Point VIDSCOPE_COOKIES_FILE somewhere else
        elsewhere = tmp_path / "elsewhere.txt"
        elsewhere.write_text(_valid_cookies_content(), encoding="utf-8")
        monkeypatch.setenv("VIDSCOPE_COOKIES_FILE", str(elsewhere))
        reset_config_cache()

        result = runner.invoke(app, ["cookies", "status"])
        assert result.exit_code == EXIT_OK
        assert "env override" in result.stdout
        assert "VIDSCOPE_COOKIES_FILE" in result.stdout
        # Rich Table truncates long Windows paths but the filename
        # always survives.
        assert "elsewhere.txt" in result.stdout


# ---------------------------------------------------------------------------
# vidscope cookies set
# ---------------------------------------------------------------------------


class TestCookiesSet:
    def test_set_valid_file(self, runner: CliRunner, tmp_path: Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text(_valid_cookies_content(), encoding="utf-8")

        result = runner.invoke(app, ["cookies", "set", str(source)])
        assert result.exit_code == EXIT_OK
        assert "copied 2" in result.stdout
        assert (tmp_path / "cookies.txt").exists()

    def test_set_invalid_file_user_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        source = tmp_path / "broken.txt"
        source.write_text("", encoding="utf-8")

        result = runner.invoke(app, ["cookies", "set", str(source)])
        assert result.exit_code == EXIT_USER_ERROR
        assert "invalid" in result.stdout or "empty" in result.stdout

    def test_set_missing_source_user_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app, ["cookies", "set", str(tmp_path / "missing.txt")]
        )
        assert result.exit_code == EXIT_USER_ERROR
        assert "does not exist" in result.stdout

    def test_set_with_env_override_warns(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Env var points elsewhere — set should still install at canonical
        # path but warn the user that yt-dlp will ignore it.
        elsewhere = tmp_path / "elsewhere.txt"
        elsewhere.write_text(_valid_cookies_content(), encoding="utf-8")
        monkeypatch.setenv("VIDSCOPE_COOKIES_FILE", str(elsewhere))
        reset_config_cache()

        source = tmp_path / "source.txt"
        source.write_text(_valid_cookies_content(), encoding="utf-8")

        result = runner.invoke(app, ["cookies", "set", str(source)])
        assert result.exit_code == EXIT_OK
        assert "warning" in result.stdout.lower()
        assert "VIDSCOPE_COOKIES_FILE" in result.stdout


# ---------------------------------------------------------------------------
# vidscope cookies clear
# ---------------------------------------------------------------------------


class TestCookiesProbe:
    def test_probe_ok(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vidscope.adapters.ytdlp.downloader import YtdlpDownloader
        from vidscope.ports import ProbeResult, ProbeStatus

        def fake_probe(self: YtdlpDownloader, url: str) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.OK,
                url=url,
                detail="resolved: Stub Title",
                title="Stub Title",
            )

        monkeypatch.setattr(YtdlpDownloader, "probe", fake_probe)

        result = runner.invoke(
            app, ["cookies", "test", "--url", "https://example.com/x"]
        )
        assert result.exit_code == EXIT_OK
        assert "ok" in result.stdout
        assert "Stub Title" in result.stdout

    def test_probe_auth_required_with_no_cookies(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vidscope.adapters.ytdlp.downloader import YtdlpDownloader
        from vidscope.ports import ProbeResult, ProbeStatus

        def fake_probe(self: YtdlpDownloader, url: str) -> ProbeResult:
            return ProbeResult(
                status=ProbeStatus.AUTH_REQUIRED,
                url=url,
                detail="login required",
            )

        monkeypatch.setattr(YtdlpDownloader, "probe", fake_probe)

        result = runner.invoke(
            app, ["cookies", "test", "--url", "https://www.instagram.com/reel/x"]
        )
        assert result.exit_code == EXIT_USER_ERROR
        assert "auth_required" in result.stdout
        assert "none are configured" in result.stdout

    def test_probe_uses_default_url_when_no_url_arg(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vidscope.adapters.ytdlp.downloader import YtdlpDownloader
        from vidscope.ports import ProbeResult, ProbeStatus

        captured: dict[str, str] = {}

        def fake_probe(self: YtdlpDownloader, url: str) -> ProbeResult:
            captured["url"] = url
            return ProbeResult(
                status=ProbeStatus.OK,
                url=url,
                detail="ok",
                title="x",
            )

        monkeypatch.setattr(YtdlpDownloader, "probe", fake_probe)

        result = runner.invoke(app, ["cookies", "test"])
        assert result.exit_code == EXIT_OK
        # Default URL should be Instagram
        assert "instagram.com" in captured["url"]


class TestCookiesClear:
    def test_clear_removes_file_with_yes_flag(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cookies = tmp_path / "cookies.txt"
        cookies.write_text(_valid_cookies_content(), encoding="utf-8")

        result = runner.invoke(app, ["cookies", "clear", "--yes"])
        assert result.exit_code == EXIT_OK
        assert "removed" in result.stdout
        assert not cookies.exists()

    def test_clear_no_file_user_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(app, ["cookies", "clear", "--yes"])
        assert result.exit_code == EXIT_USER_ERROR
        assert "no cookies file" in result.stdout

    def test_clear_prompt_aborted(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        # Create a file, then answer "n" at the prompt
        cookies = tmp_path / "cookies.txt"
        cookies.write_text(_valid_cookies_content(), encoding="utf-8")

        result = runner.invoke(app, ["cookies", "clear"], input="n\n")
        assert result.exit_code == EXIT_OK
        assert "aborted" in result.stdout
        assert cookies.exists()  # not removed

    def test_clear_prompt_confirmed(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        cookies = tmp_path / "cookies.txt"
        cookies.write_text(_valid_cookies_content(), encoding="utf-8")

        result = runner.invoke(app, ["cookies", "clear"], input="y\n")
        assert result.exit_code == EXIT_OK
        assert "removed" in result.stdout
        assert not cookies.exists()
