"""Tests for :class:`IngestStage`.

Uses a fake Downloader, a real LocalMediaStorage under tmp_path, and
a real SqliteUnitOfWork against an in-memory schema. The goal is to
exercise the full wiring the stage relies on — ports to adapters —
without calling yt-dlp or touching the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.fs.local_media_storage import LocalMediaStorage
from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    IngestError,
    Platform,
    PlatformId,
)
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.pipeline.stages.ingest import IngestStage
from vidscope.ports import IngestOutcome, PipelineContext

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeDownloader:
    """A Downloader that writes a fake file and returns a preset outcome.

    ``outcome_factory`` is called with the destination dir so the fake
    can write the file at the same path it reports.
    """

    outcome_factory: object  # Callable[[str], IngestOutcome]
    error: Exception | None = None
    calls: list[tuple[str, str]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.calls = []

    def download(self, url: str, destination_dir: str) -> IngestOutcome:
        self.calls.append((url, destination_dir))
        if self.error is not None:
            raise self.error
        return self.outcome_factory(destination_dir)  # type: ignore[operator]


def _youtube_outcome_factory(platform_id: str = "abc123"):  # type: ignore[no-untyped-def]
    """Return a function that writes a fake mp4 and builds an outcome."""

    def build(destination_dir: str) -> IngestOutcome:
        dest = Path(destination_dir) / f"{platform_id}.mp4"
        dest.write_bytes(b"fake mp4 content")
        return IngestOutcome(
            platform=Platform.YOUTUBE,
            platform_id=PlatformId(platform_id),
            url=f"https://www.youtube.com/watch?v={platform_id}",
            media_path=str(dest),
            title="Fake video title",
            author="Fake Channel",
            duration=42.0,
            upload_date="20260401",
            view_count=1000,
        )

    return build


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    db_path = tmp_path / "stage.db"
    eng = build_engine(db_path)
    init_db(eng)
    return eng


@pytest.fixture()
def storage_root(tmp_path: Path) -> Path:
    root = tmp_path / "storage"
    root.mkdir()
    return root


@pytest.fixture()
def cache_dir(tmp_path: Path) -> Path:
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache


@pytest.fixture()
def media_storage(storage_root: Path) -> LocalMediaStorage:
    return LocalMediaStorage(storage_root)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_execute_writes_video_row_and_stores_media(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
        storage_root: Path,
    ) -> None:
        downloader = FakeDownloader(
            outcome_factory=_youtube_outcome_factory("abc123")
        )
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx = PipelineContext(
            source_url="https://www.youtube.com/watch?v=abc123"
        )

        with SqliteUnitOfWork(engine) as uow:
            result = stage.execute(ctx, uow)

        # 1. Stage result reflects success
        assert result.skipped is False
        assert "ingested" in result.message
        assert "youtube" in result.message
        assert "Fake video title" in result.message

        # 2. Context is populated with everything downstream stages need
        assert ctx.video_id is not None
        assert ctx.platform is Platform.YOUTUBE
        assert ctx.platform_id == PlatformId("abc123")
        assert ctx.media_key == "videos/youtube/abc123/media.mp4"

        # 3. Videos row exists with every metadata field
        with SqliteUnitOfWork(engine) as uow:
            video = uow.videos.get(ctx.video_id)  # type: ignore[arg-type]
            assert video is not None
            assert video.title == "Fake video title"
            assert video.author == "Fake Channel"
            assert video.duration == 42.0
            assert video.upload_date == "20260401"
            assert video.view_count == 1000
            assert video.media_key == "videos/youtube/abc123/media.mp4"

        # 4. Media file is at the expected location in storage
        stored_path = storage_root / "videos" / "youtube" / "abc123" / "media.mp4"
        assert stored_path.exists()
        assert stored_path.read_bytes() == b"fake mp4 content"

        # 5. Downloader was called exactly once with the URL
        assert len(downloader.calls) == 1
        assert downloader.calls[0][0] == (
            "https://www.youtube.com/watch?v=abc123"
        )

    def test_re_execute_upserts_existing_row(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        """Running the stage twice on the same URL should update the
        existing videos row (idempotent at the DB level) without
        producing a duplicate."""
        downloader = FakeDownloader(
            outcome_factory=_youtube_outcome_factory("dup123")
        )
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx1 = PipelineContext(
            source_url="https://www.youtube.com/watch?v=dup123"
        )
        ctx2 = PipelineContext(
            source_url="https://www.youtube.com/watch?v=dup123"
        )

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx1, uow)
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx2, uow)

        with SqliteUnitOfWork(engine) as uow:
            assert uow.videos.count() == 1
        # Downloader called twice (D025: no is_satisfied short-circuit yet)
        assert len(downloader.calls) == 2

    def test_is_satisfied_always_returns_false(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        stage = IngestStage(
            downloader=FakeDownloader(
                outcome_factory=_youtube_outcome_factory()
            ),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx = PipelineContext(source_url="https://www.youtube.com/watch?v=x")
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False


class TestErrorPaths:
    def test_invalid_url_raises_before_calling_downloader(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        downloader = FakeDownloader(
            outcome_factory=_youtube_outcome_factory()
        )
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx = PipelineContext(source_url="https://vimeo.com/12345")

        with SqliteUnitOfWork(engine) as uow, pytest.raises(IngestError):
            stage.execute(ctx, uow)

        # Downloader was never called — URL validation happens first
        assert len(downloader.calls) == 0

    def test_downloader_failure_propagates(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        downloader = FakeDownloader(
            outcome_factory=_youtube_outcome_factory(),
            error=IngestError("simulated yt-dlp failure", retryable=True),
        )
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx = PipelineContext(
            source_url="https://www.youtube.com/watch?v=broken"
        )

        with SqliteUnitOfWork(engine) as uow, pytest.raises(IngestError) as exc_info:
            stage.execute(ctx, uow)
        assert "simulated yt-dlp failure" in str(exc_info.value)
        assert exc_info.value.retryable is True

    def test_platform_mismatch_between_url_and_downloader_raises(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        """If the URL parser says YouTube but yt-dlp claims TikTok,
        surface the mismatch instead of silently trusting yt-dlp."""

        def mismatch_factory(destination_dir: str) -> IngestOutcome:
            dest = Path(destination_dir) / "mismatch.mp4"
            dest.write_bytes(b"fake")
            return IngestOutcome(
                platform=Platform.TIKTOK,  # but URL is a YouTube URL
                platform_id=PlatformId("mismatch"),
                url="https://www.youtube.com/watch?v=mismatch",
                media_path=str(dest),
                title="Wrong",
                author="Wrong",
                duration=10.0,
            )

        downloader = FakeDownloader(outcome_factory=mismatch_factory)
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx = PipelineContext(
            source_url="https://www.youtube.com/watch?v=mismatch"
        )

        with SqliteUnitOfWork(engine) as uow, pytest.raises(IngestError) as exc_info:
            stage.execute(ctx, uow)
        assert "platform mismatch" in str(exc_info.value)
        assert exc_info.value.retryable is False

    def test_missing_media_file_after_download_raises(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        """Downloader reports a path but doesn't actually create the file."""

        def ghost_factory(destination_dir: str) -> IngestOutcome:
            return IngestOutcome(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("ghost"),
                url="https://www.youtube.com/watch?v=ghost",
                media_path=str(Path(destination_dir) / "nonexistent.mp4"),
                title="Ghost",
                author="Nobody",
                duration=1.0,
            )

        downloader = FakeDownloader(outcome_factory=ghost_factory)
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx = PipelineContext(
            source_url="https://www.youtube.com/watch?v=ghost"
        )

        with SqliteUnitOfWork(engine) as uow, pytest.raises(IngestError) as exc_info:
            stage.execute(ctx, uow)
        assert "file does not exist" in str(exc_info.value)


class TestStageIdentity:
    def test_name_matches_stage_name_enum(
        self,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        from vidscope.domain import StageName

        stage = IngestStage(
            downloader=FakeDownloader(
                outcome_factory=_youtube_outcome_factory()
            ),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        assert stage.name == StageName.INGEST.value

    def test_tempdir_is_cleaned_up_after_execute(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        """After a successful execute, the tempdir the downloader wrote
        to should no longer exist."""
        captured: list[str] = []

        def capturing_factory(destination_dir: str) -> IngestOutcome:
            captured.append(destination_dir)
            dest = Path(destination_dir) / "clean.mp4"
            dest.write_bytes(b"fake")
            return IngestOutcome(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("clean"),
                url="https://www.youtube.com/watch?v=clean",
                media_path=str(dest),
                title="Clean",
                author="Clean",
                duration=10.0,
            )

        downloader = FakeDownloader(outcome_factory=capturing_factory)
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx = PipelineContext(
            source_url="https://www.youtube.com/watch?v=clean"
        )
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        assert len(captured) == 1
        assert not Path(captured[0]).exists()
