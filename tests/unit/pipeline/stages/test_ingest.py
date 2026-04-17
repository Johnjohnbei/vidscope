"""Tests for :class:`IngestStage`.

Uses a fake Downloader, a real LocalMediaStorage under tmp_path, and
a real SqliteUnitOfWork against an in-memory schema. The goal is to
exercise the full wiring the stage relies on — ports to adapters —
without calling yt-dlp or touching the network.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.fs.local_media_storage import LocalMediaStorage
from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    Creator,
    IngestError,
    Platform,
    PlatformId,
    PlatformUserId,
)
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.pipeline.stages.ingest import IngestStage
from vidscope.ports import CreatorInfo, IngestOutcome, PipelineContext

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


# ---------------------------------------------------------------------------
# M006/S02-P03 — Creator wiring (D-01, D-02, D-03, D-04)
# ---------------------------------------------------------------------------


def _youtube_outcome_with_creator_factory(
    platform_id: str = "abc123",
    *,
    creator_info: CreatorInfo | None = None,
):  # type: ignore[no-untyped-def]
    """Same as _youtube_outcome_factory but allows injecting a CreatorInfo."""

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
            creator_info=creator_info,
        )

    return build


def _sample_creator_info(uploader_id: str = "UC_fake") -> CreatorInfo:
    return CreatorInfo(
        platform_user_id=uploader_id,
        handle="Fake Channel",
        display_name="Fake Channel",
        profile_url=f"https://youtube.com/c/{uploader_id}",
        avatar_url="https://yt3.ggpht.com/fake.jpg",
        follower_count=12345,
        is_verified=False,
    )


class TestCreatorWiring:
    """IngestStage integration with the Creator foundation from S01.

    - D-01: creator_info present → creator upsert + video.creator_id
    - D-02: creator_info None → ingest OK, creator_id=NULL, WARNING log
    - D-03: re-ingest → creator row refreshed, no duplicate
    - D-04: single UoW transaction, rollback on video failure
    """

    def test_execute_with_creator_info_upserts_creator_and_links_video(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        """D-01 happy path: outcome carries creator_info → creator row
        written, video.creator_id set, video.author from D-03 write-through."""
        downloader = FakeDownloader(
            outcome_factory=_youtube_outcome_with_creator_factory(
                "vid_d01",
                creator_info=_sample_creator_info("UC_d01"),
            )
        )
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx = PipelineContext(
            source_url="https://www.youtube.com/watch?v=vid_d01"
        )

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        with SqliteUnitOfWork(engine) as uow:
            assert uow.creators.count() == 1
            creator = uow.creators.find_by_platform_user_id(
                Platform.YOUTUBE, PlatformUserId("UC_d01")
            )
            assert creator is not None
            assert creator.display_name == "Fake Channel"
            assert creator.follower_count == 12345

            video = uow.videos.get(ctx.video_id)  # type: ignore[arg-type]
            assert video is not None
            assert video.author == "Fake Channel"
            from sqlalchemy import text
            creator_id = uow._connection.execute(  # type: ignore[attr-defined]
                text("SELECT creator_id FROM videos WHERE id = :id"),
                {"id": int(video.id)},  # type: ignore[arg-type]
            ).scalar()
            assert creator_id is not None
            assert int(creator_id) == int(creator.id)  # type: ignore[arg-type]

    def test_execute_without_creator_info_saves_video_with_null_creator_id(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """D-02: creator_info None → ingest succeeds, creator_id=NULL,
        WARNING logged with the video URL."""
        downloader = FakeDownloader(
            outcome_factory=_youtube_outcome_with_creator_factory(
                "vid_d02",
                creator_info=None,
            )
        )
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        url = "https://www.youtube.com/watch?v=vid_d02"
        ctx = PipelineContext(source_url=url)

        with (
            caplog.at_level(
                logging.WARNING, logger="vidscope.pipeline.stages.ingest"
            ),
            SqliteUnitOfWork(engine) as uow,
        ):
            stage.execute(ctx, uow)

        with SqliteUnitOfWork(engine) as uow:
            assert uow.creators.count() == 0

            video = uow.videos.get(ctx.video_id)  # type: ignore[arg-type]
            assert video is not None
            assert video.author == "Fake Channel"
            from sqlalchemy import text
            creator_id = uow._connection.execute(  # type: ignore[attr-defined]
                text("SELECT creator_id FROM videos WHERE id = :id"),
                {"id": int(video.id)},  # type: ignore[arg-type]
            ).scalar()
            assert creator_id is None

        warning_records = [
            r for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert len(warning_records) >= 1
        assert any(url in r.getMessage() for r in warning_records), (
            f"expected WARNING to include the URL {url!r}, got: "
            f"{[r.getMessage() for r in warning_records]}"
        )

    def test_re_execute_with_updated_follower_count_refreshes_creator(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        """D-03 idempotent: second ingest with updated follower_count
        refreshes the creator row in-place (no duplicate, fresh value)."""
        stage = IngestStage(
            downloader=FakeDownloader(
                outcome_factory=_youtube_outcome_with_creator_factory(
                    "vid_d03",
                    creator_info=_sample_creator_info("UC_d03"),
                )
            ),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx1 = PipelineContext(
            source_url="https://www.youtube.com/watch?v=vid_d03"
        )
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx1, uow)

        updated_info = CreatorInfo(
            platform_user_id="UC_d03",
            handle="Fake Channel",
            display_name="Fake Channel",
            profile_url="https://youtube.com/c/UC_d03",
            avatar_url="https://yt3.ggpht.com/fake.jpg",
            follower_count=99999,
            is_verified=True,
        )
        stage2 = IngestStage(
            downloader=FakeDownloader(
                outcome_factory=_youtube_outcome_with_creator_factory(
                    "vid_d03",
                    creator_info=updated_info,
                )
            ),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx2 = PipelineContext(
            source_url="https://www.youtube.com/watch?v=vid_d03"
        )
        with SqliteUnitOfWork(engine) as uow:
            stage2.execute(ctx2, uow)

        with SqliteUnitOfWork(engine) as uow:
            assert uow.creators.count() == 1
            creator = uow.creators.find_by_platform_user_id(
                Platform.YOUTUBE, PlatformUserId("UC_d03")
            )
            assert creator is not None
            assert creator.follower_count == 99999
            assert creator.is_verified is True
            assert uow.videos.count() == 1

    def test_video_upsert_failure_rolls_back_creator(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """D-04: single transaction — if uow.videos.upsert_by_platform_id
        raises, the creator upsert is rolled back too."""
        downloader = FakeDownloader(
            outcome_factory=_youtube_outcome_with_creator_factory(
                "vid_d04",
                creator_info=_sample_creator_info("UC_d04_rollback"),
            )
        )
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx = PipelineContext(
            source_url="https://www.youtube.com/watch?v=vid_d04"
        )

        from vidscope.adapters.sqlite.video_repository import (
            VideoRepositorySQLite,
        )

        def _boom(
            self: object, video: object, creator: object = None
        ) -> None:
            raise RuntimeError("simulated video upsert failure")

        monkeypatch.setattr(
            VideoRepositorySQLite, "upsert_by_platform_id", _boom
        )

        with pytest.raises(RuntimeError, match="simulated"), SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        with SqliteUnitOfWork(engine) as uow:
            assert uow.creators.count() == 0
            assert uow.videos.count() == 0

    def test_two_videos_same_creator_share_one_creator_row(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        """Two different videos from the same uploader → one creator
        row, two videos both linking to it."""
        info = _sample_creator_info("UC_shared")
        stage = IngestStage(
            downloader=FakeDownloader(
                outcome_factory=_youtube_outcome_with_creator_factory(
                    "vid_shared_1", creator_info=info
                )
            ),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx1 = PipelineContext(
            source_url="https://www.youtube.com/watch?v=vid_shared_1"
        )
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx1, uow)

        stage2 = IngestStage(
            downloader=FakeDownloader(
                outcome_factory=_youtube_outcome_with_creator_factory(
                    "vid_shared_2", creator_info=info
                )
            ),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx2 = PipelineContext(
            source_url="https://www.youtube.com/watch?v=vid_shared_2"
        )
        with SqliteUnitOfWork(engine) as uow:
            stage2.execute(ctx2, uow)

        with SqliteUnitOfWork(engine) as uow:
            assert uow.creators.count() == 1
            assert uow.videos.count() == 2
            creator = uow.creators.find_by_platform_user_id(
                Platform.YOUTUBE, PlatformUserId("UC_shared")
            )
            assert creator is not None
            from sqlalchemy import text
            rows = uow._connection.execute(  # type: ignore[attr-defined]
                text(
                    "SELECT creator_id FROM videos "
                    "WHERE platform_id IN ('vid_shared_1', 'vid_shared_2')"
                )
            ).all()
            creator_ids = {r[0] for r in rows}
            assert creator_ids == {int(creator.id)}  # type: ignore[arg-type]

    def test_existing_happy_path_still_works_with_none_creator_info(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        """Regression: original _youtube_outcome_factory (no creator_info)
        still produces a valid ingest via the D-02 code path."""
        downloader = FakeDownloader(
            outcome_factory=_youtube_outcome_factory("regression_abc")
        )
        stage = IngestStage(
            downloader=downloader,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        ctx = PipelineContext(
            source_url="https://www.youtube.com/watch?v=regression_abc"
        )

        with SqliteUnitOfWork(engine) as uow:
            result = stage.execute(ctx, uow)

        assert result.skipped is False
        with SqliteUnitOfWork(engine) as uow:
            assert uow.videos.count() == 1
            assert uow.creators.count() == 0

    def test_creator_from_info_constructs_domain_creator(self) -> None:
        """_creator_from_info (private helper) builds a Creator from a
        CreatorInfo without I/O."""
        from vidscope.pipeline.stages.ingest import _creator_from_info

        info = _sample_creator_info("UC_pure")
        creator = _creator_from_info(info, Platform.TIKTOK)

        assert isinstance(creator, Creator)
        assert creator.platform is Platform.TIKTOK
        assert creator.platform_user_id == "UC_pure"
        assert creator.handle == "Fake Channel"
        assert creator.display_name == "Fake Channel"
        assert creator.follower_count == 12345
        assert creator.is_orphan is False
        assert creator.id is None
