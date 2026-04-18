"""CLI smoke tests using Typer's CliRunner.

Every test runs against a fresh tmp data dir via the
``VIDSCOPE_DATA_DIR`` env var. The CLI itself creates the DB on first
use, so we don't pre-seed anything — each test starts from a clean
state.

Tests that exercise ``vidscope add`` stub out yt_dlp.YoutubeDL via the
``stub_pipeline`` fixture so the real network is never touched. Live
ingest is covered in ``tests/integration/test_ingest_live.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from vidscope.adapters.ytdlp import downloader as downloader_module
from vidscope.cli.app import EXIT_OK, EXIT_USER_ERROR, app
from vidscope.infrastructure.config import reset_config_cache


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    reset_config_cache()
    yield
    reset_config_cache()


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def stub_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub every external dependency the pipeline calls during a CLI
    `vidscope add` test:

    - **yt_dlp.YoutubeDL** → fake that writes a dummy file and returns
      a valid info_dict
    - **faster_whisper.WhisperModel** → fake that returns a single
      stub segment so transcription completes without downloading the
      ~150MB model

    Together these let CLI tests exercise the full real container path
    (Typer → use case → runner → ingest stage → transcribe stage) with
    zero network access.
    """

    # ----- yt_dlp -----
    class FakeYoutubeDL:
        def __init__(self, options: dict[str, Any]) -> None:
            self._options = options

        def __enter__(self) -> FakeYoutubeDL:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def extract_info(
            self, url: str, *, download: bool = True
        ) -> dict[str, Any]:
            outtmpl = str(self._options.get("outtmpl", ""))
            platform_id = "cli-stub"
            dest = Path(outtmpl.replace("%(id)s", platform_id).replace(
                "%(ext)s", "mp4"
            ))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"fake cli stub content")
            return {
                "id": platform_id,
                "extractor_key": "Youtube",
                "webpage_url": url,
                "title": "Fake CLI Video",
                "uploader": "Fake Author",
                "duration": 12.5,
                "upload_date": "20260401",
                "view_count": 42,
                "requested_downloads": [{"filepath": str(dest)}],
            }

    monkeypatch.setattr(
        downloader_module.yt_dlp, "YoutubeDL", FakeYoutubeDL
    )

    # ----- faster_whisper -----
    class FakeSegment:
        def __init__(self, start: float, end: float, text: str) -> None:
            self.start = start
            self.end = end
            self.text = text

    class FakeInfo:
        language = "en"
        language_probability = 0.99

    class FakeWhisperModel:
        def __init__(self, model_name: str, **kwargs: Any) -> None:
            self._model_name = model_name

        def transcribe(
            self, media_path: str, **kwargs: Any
        ) -> tuple[Any, FakeInfo]:
            return (
                iter([FakeSegment(0.0, 1.0, "hello world")]),
                FakeInfo(),
            )

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeWhisperModel)

    # ----- ffmpeg subprocess -----
    from vidscope.adapters.ffmpeg import frame_extractor as fe_module

    monkeypatch.setattr(
        fe_module.shutil, "which", lambda _name: "/fake/ffmpeg"
    )

    class FakeFFmpegCompleted:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_ffmpeg_run(cmd: list[str], **_kwargs: Any) -> FakeFFmpegCompleted:
        out_template = cmd[-1]
        out_dir = Path(out_template).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        for i in range(1, 4):
            (out_dir / f"frame_{i:04d}.jpg").write_bytes(b"fake jpg")
        return FakeFFmpegCompleted()

    monkeypatch.setattr(fe_module.subprocess, "run", fake_ffmpeg_run)


class TestHelpAndVersion:
    def test_help_lists_every_command(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == EXIT_OK
        for cmd in (
            "add",
            "show",
            "list",
            "search",
            "status",
            "doctor",
            "suggest",
            "mcp",
            "watch",
            "cookies",
        ):
            assert cmd in result.stdout

    def test_version_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == EXIT_OK
        assert "vidscope" in result.stdout


class TestStatus:
    def test_empty_db_returns_zero_counts(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["status"])
        assert result.exit_code == EXIT_OK
        assert "videos: 0" in result.stdout
        assert "pipeline runs: 0" in result.stdout

    def test_after_add_shows_runs_for_each_stage(
        self, runner: CliRunner, stub_pipeline: None
    ) -> None:
        """After S06 the pipeline has FIVE stages (ingest, transcribe,
        frames, analyze, index), so a single `vidscope add` produces
        five pipeline_runs."""
        add_result = runner.invoke(
            app, ["add", "https://www.youtube.com/watch?v=cli-stub"]
        )
        assert add_result.exit_code == EXIT_OK

        status_result = runner.invoke(app, ["status"])
        assert status_result.exit_code == EXIT_OK
        # Five pipeline_runs: one per stage
        assert "pipeline runs: 5" in status_result.stdout
        assert "ingest" in status_result.stdout
        assert "transcribe" in status_result.stdout
        assert "frames" in status_result.stdout
        assert "analyze" in status_result.stdout
        assert "index" in status_result.stdout
        assert "ok" in status_result.stdout.lower()


class TestAdd:
    def test_happy_path_ingests_with_stubbed_downloader(
        self, runner: CliRunner, stub_pipeline: None
    ) -> None:
        result = runner.invoke(
            app, ["add", "https://www.youtube.com/watch?v=cli-stub"]
        )
        assert result.exit_code == EXIT_OK
        assert "ingest OK" in result.stdout
        assert "Fake CLI Video" in result.stdout
        assert "Fake Author" in result.stdout
        assert "youtube" in result.stdout

    def test_empty_url_fails_with_user_error(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["add", "   "])
        assert result.exit_code == EXIT_USER_ERROR
        assert "error" in result.stdout.lower()
        assert "empty" in result.stdout

    def test_unsupported_url_fails_with_user_error(
        self, runner: CliRunner
    ) -> None:
        """A non-supported platform URL should be rejected before any
        network call is even attempted."""
        result = runner.invoke(app, ["add", "https://vimeo.com/12345"])
        assert result.exit_code == EXIT_USER_ERROR
        assert (
            "unsupported platform" in result.stdout.lower()
            or "unsupported" in result.stdout.lower()
        )


class TestList:
    def test_empty_list(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["list"])
        assert result.exit_code == EXIT_OK
        assert "total videos: 0" in result.stdout


class TestSearch:
    def test_empty_query_returns_no_matches(self, runner: CliRunner) -> None:
        # Empty index — any query returns zero hits
        result = runner.invoke(app, ["search", "hello"])
        assert result.exit_code == EXIT_OK
        assert "hits: 0" in result.stdout


class TestShow:
    def test_missing_id_fails_with_user_error(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["show", "999"])
        assert result.exit_code == EXIT_USER_ERROR
        assert "no video with id" in result.stdout


class TestDoctor:
    def test_runs_and_prints_a_table(self, runner: CliRunner) -> None:
        # doctor may exit 0 or 2 depending on whether ffmpeg is on PATH.
        # We only verify the report prints both check names.
        result = runner.invoke(app, ["doctor"])
        assert "ffmpeg" in result.stdout
        assert "yt-dlp" in result.stdout
        assert "mcp" in result.stdout
        # Exit code is either 0 (both ok) or 2 (at least one failed)
        assert result.exit_code in (0, 2)


class TestSuggest:
    def test_missing_source_fails_with_user_error(
        self, runner: CliRunner
    ) -> None:
        # Empty library: video 999 does not exist
        result = runner.invoke(app, ["suggest", "999"])
        assert result.exit_code == EXIT_USER_ERROR
        assert "no video with id 999" in result.stdout

    def test_help_shows_limit_option(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["suggest", "--help"])
        assert result.exit_code == EXIT_OK
        assert "--limit" in result.stdout
        assert "-n" in result.stdout


class TestMcp:
    def test_mcp_subapp_lists_serve(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["mcp", "--help"])
        assert result.exit_code == EXIT_OK
        assert "serve" in result.stdout


class TestWatch:
    def test_watch_subapp_help_lists_commands(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["watch", "--help"])
        assert result.exit_code == EXIT_OK
        assert "add" in result.stdout
        assert "list" in result.stdout
        assert "remove" in result.stdout
        assert "refresh" in result.stdout

    def test_watch_list_empty(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["watch", "list"])
        assert result.exit_code == EXIT_OK
        assert "watched accounts: 0" in result.stdout
        assert "No accounts yet" in result.stdout

    def test_watch_add_persists_account(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(
            app, ["watch", "add", "https://www.youtube.com/@YouTube"]
        )
        assert result.exit_code == EXIT_OK
        assert "added" in result.stdout
        assert "@YouTube" in result.stdout

        list_result = runner.invoke(app, ["watch", "list"])
        assert list_result.exit_code == EXIT_OK
        assert "watched accounts: 1" in list_result.stdout
        assert "@YouTube" in list_result.stdout

    def test_watch_add_duplicate_returns_user_error(
        self, runner: CliRunner
    ) -> None:
        runner.invoke(app, ["watch", "add", "https://www.youtube.com/@YouTube"])
        result = runner.invoke(
            app, ["watch", "add", "https://www.youtube.com/@YouTube"]
        )
        assert result.exit_code == EXIT_USER_ERROR
        assert "already" in result.stdout

    def test_watch_add_invalid_url_fails(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["watch", "add", "not a url"])
        assert result.exit_code == EXIT_USER_ERROR

    def test_watch_remove_by_handle(self, runner: CliRunner) -> None:
        runner.invoke(app, ["watch", "add", "https://www.youtube.com/@YouTube"])
        result = runner.invoke(app, ["watch", "remove", "@YouTube"])
        assert result.exit_code == EXIT_OK
        assert "removed" in result.stdout

        list_result = runner.invoke(app, ["watch", "list"])
        assert "watched accounts: 0" in list_result.stdout

    def test_watch_remove_with_explicit_platform(
        self, runner: CliRunner
    ) -> None:
        runner.invoke(app, ["watch", "add", "https://www.youtube.com/@YouTube"])
        result = runner.invoke(
            app, ["watch", "remove", "@YouTube", "--platform", "youtube"]
        )
        assert result.exit_code == EXIT_OK

    def test_watch_remove_unknown_platform_fails(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(
            app, ["watch", "remove", "@x", "--platform", "myspace"]
        )
        assert result.exit_code == EXIT_USER_ERROR
        assert "unknown platform" in result.stdout

    def test_watch_remove_missing_fails(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["watch", "remove", "@nope"])
        assert result.exit_code == EXIT_USER_ERROR
        assert "no watched account" in result.stdout

    def test_watch_refresh_with_no_accounts(
        self, runner: CliRunner, stub_pipeline: None
    ) -> None:
        # Stub yt-dlp is on so list_channel_videos won't go to network
        # if it ever does get called (it shouldn't here — empty watchlist)
        result = runner.invoke(app, ["watch", "refresh"])
        assert result.exit_code == EXIT_OK
        assert "checked 0 accounts" in result.stdout
        assert "0" in result.stdout

    def test_watch_refresh_with_one_account(
        self,
        runner: CliRunner,
        stub_pipeline: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """End-to-end CLI refresh: add an account, then refresh.

        We patch list_channel_videos directly on the YtdlpDownloader
        class because the standard stub_pipeline only stubs the
        ``YoutubeDL.extract_info`` path used by ``download``. The
        listing path uses a different code path that we override here.
        """
        from vidscope.adapters.ytdlp.downloader import YtdlpDownloader
        from vidscope.domain import PlatformId
        from vidscope.ports import ChannelEntry

        def fake_list_channel_videos(
            self: YtdlpDownloader, url: str, *, limit: int = 10
        ) -> list[ChannelEntry]:
            return [
                ChannelEntry(
                    platform_id=PlatformId("cli-stub"),
                    url="https://www.youtube.com/watch?v=cli-stub",
                ),
            ]

        monkeypatch.setattr(
            YtdlpDownloader, "list_channel_videos", fake_list_channel_videos
        )

        # Add an account
        runner.invoke(app, ["watch", "add", "https://www.youtube.com/@YouTube"])

        # Refresh — should ingest 1 new video via the stubbed pipeline
        result = runner.invoke(app, ["watch", "refresh"])
        assert result.exit_code == EXIT_OK
        assert "checked 1 accounts" in result.stdout
        assert "1" in result.stdout  # one new video

        # Second refresh: 0 new (idempotent)
        again = runner.invoke(app, ["watch", "refresh"])
        assert again.exit_code == EXIT_OK
        assert "checked 1 accounts" in again.stdout
