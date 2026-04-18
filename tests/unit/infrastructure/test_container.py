"""Unit tests for vidscope.infrastructure.container."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.infrastructure.config import Config, reset_config_cache
from vidscope.infrastructure.container import (
    Container,
    SystemClock,
    build_container,
)
from vidscope.ports import Clock, MediaStorage, UnitOfWork


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    reset_config_cache()
    yield
    reset_config_cache()


class TestBuildContainer:
    def test_returns_a_container_with_every_field_populated(self) -> None:
        container = build_container()

        assert isinstance(container, Container)
        assert isinstance(container.config, Config)
        assert isinstance(container.engine, Engine)
        assert isinstance(container.clock, SystemClock)
        # media_storage is a Protocol — use runtime_checkable isinstance.
        assert isinstance(container.media_storage, MediaStorage)
        assert callable(container.unit_of_work)
        # S02 additions: downloader + pipeline_runner are wired.
        assert container.downloader is not None
        assert container.pipeline_runner is not None
        assert hasattr(container.pipeline_runner, "run")
        # S03 additions: transcriber wired + transcribe stage registered
        assert container.transcriber is not None
        # S04 additions: frame_extractor + frames stage
        assert container.frame_extractor is not None
        # S05 additions: analyzer + analyze stage
        assert container.analyzer is not None
        assert container.analyzer.provider_name == "heuristic"
        # M008/S02-P01: visual_intelligence stage inserted between analyze and metadata_extract
        assert container.pipeline_runner.stage_names == (
            "ingest",
            "transcribe",
            "frames",
            "analyze",
            "visual_intelligence",
            "metadata_extract",
            "index",
        )

    def test_config_points_at_sandboxed_data_dir(self, tmp_path: Path) -> None:
        container = build_container()
        assert container.config.data_dir == tmp_path.resolve()

    def test_engine_is_bound_to_configured_db_path(self, tmp_path: Path) -> None:
        container = build_container()
        expected_url = f"sqlite:///{tmp_path.resolve() / 'vidscope.db'}"
        rendered = str(container.engine.url)
        assert rendered == expected_url

    def test_schema_is_initialized_on_build(self) -> None:
        """The container must leave the DB with every expected table."""
        from sqlalchemy import inspect

        container = build_container()
        names = inspect(container.engine).get_table_names()
        assert {
            "videos",
            "transcripts",
            "frames",
            "analyses",
            "pipeline_runs",
        }.issubset(set(names))
        # FTS5 virtual table exposes its name plus internal shadow tables.
        assert "search_index" in names

    def test_unit_of_work_is_usable(self) -> None:
        container = build_container()
        # Opening and closing a UoW on a fresh DB must not raise.
        with container.unit_of_work() as uow:
            assert isinstance(uow, UnitOfWork)
            assert uow.videos.count() == 0
            assert uow.pipeline_runs.count() == 0

    def test_accepts_an_explicit_config(self, tmp_path: Path) -> None:
        explicit = Config(
            data_dir=tmp_path,
            cache_dir=tmp_path / "cache",
            db_path=tmp_path / "vidscope.db",
            downloads_dir=tmp_path / "downloads",
            frames_dir=tmp_path / "frames",
            models_dir=tmp_path / "models",
        )
        for d in (
            explicit.cache_dir,
            explicit.downloads_dir,
            explicit.frames_dir,
            explicit.models_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

        container = build_container(explicit)
        assert container.config is explicit

    def test_container_is_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        container = build_container()
        with pytest.raises(FrozenInstanceError):
            container.engine = None  # type: ignore[misc]


class TestSystemClock:
    def test_now_returns_utc_aware_datetime(self) -> None:
        clock = SystemClock()
        now = clock.now()
        assert isinstance(now, datetime)
        assert now.tzinfo is not None
        # UTC offset must be zero
        assert now.utcoffset() is not None
        assert now.utcoffset().total_seconds() == 0  # type: ignore[union-attr]

    def test_system_clock_conforms_to_clock_protocol(self) -> None:
        clock = SystemClock()
        assert isinstance(clock, Clock)


class TestPragmaEnforcement:
    """Smoke test: the engine the container returns must have FK and WAL
    pragmas applied on new connections."""

    def test_foreign_keys_are_enabled(self) -> None:
        container = build_container()
        with container.engine.connect() as conn:
            from sqlalchemy import text

            result = conn.execute(text("PRAGMA foreign_keys")).scalar()
            assert result == 1

    def test_wal_journal_mode(self) -> None:
        container = build_container()
        with container.engine.connect() as conn:
            from sqlalchemy import text

            result = conn.execute(text("PRAGMA journal_mode")).scalar()
            assert isinstance(result, str)
            assert result.lower() == "wal"


class TestCookiesIntegration:
    """S07/T03: build_container reads config.cookies_file and passes
    it to the YtdlpDownloader."""

    def test_no_cookies_file_works_as_before(self) -> None:
        """Default sandbox has no cookies; container builds cleanly."""
        container = build_container()
        assert container.config.cookies_file is None
        # Downloader's private attribute should also be None
        assert container.downloader._cookies_file is None

    def test_cookies_file_propagates_to_downloader(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When VIDSCOPE_COOKIES_FILE points at a real file, the
        downloader receives the resolved path."""
        from vidscope.infrastructure.config import reset_config_cache

        cookies = tmp_path / "real-cookies.txt"
        cookies.write_text("# Netscape HTTP Cookie File\n")
        monkeypatch.setenv("VIDSCOPE_COOKIES_FILE", str(cookies))
        reset_config_cache()

        container = build_container()
        assert container.config.cookies_file == cookies.resolve()
        assert (
            container.downloader._cookies_file
            == cookies.resolve()
        )

    def test_misconfigured_cookies_file_fails_build_container(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bad VIDSCOPE_COOKIES_FILE causes build_container to fail
        loud at startup with a typed IngestError. This is the
        fail-fast behavior the rest of the system relies on."""
        from vidscope.domain import IngestError
        from vidscope.infrastructure.config import reset_config_cache

        bad_path = tmp_path / "definitely-not-here.txt"
        monkeypatch.setenv("VIDSCOPE_COOKIES_FILE", str(bad_path))
        reset_config_cache()

        with pytest.raises(IngestError) as exc_info:
            build_container()
        assert "cookies file not found" in str(exc_info.value)
        assert exc_info.value.retryable is False
