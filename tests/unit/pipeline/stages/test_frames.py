"""Tests for FramesStage with a fake FrameExtractor + real adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.fs.local_media_storage import LocalMediaStorage
from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    Frame,
    FrameExtractionError,
    Platform,
    PlatformId,
    Video,
    VideoId,
)
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.pipeline.stages.frames import FramesStage
from vidscope.ports import PipelineContext

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeFrameExtractor:
    """Stand-in for the FrameExtractor port.

    On extract_frames(), creates `frame_count` real .jpg files in the
    output_dir and returns Frame entities pointing at them. Or raises
    a preset error.
    """

    frame_count: int = 5
    error: Exception | None = None
    calls: list[tuple[str, str, int]] = field(default_factory=list)

    def extract_frames(
        self,
        media_path: str,
        output_dir: str,
        *,
        max_frames: int = 30,
    ) -> list[Frame]:
        self.calls.append((media_path, output_dir, max_frames))
        if self.error is not None:
            raise self.error

        frames: list[Frame] = []
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for i in range(self.frame_count):
            file_path = out / f"frame_{i:04d}.jpg"
            file_path.write_bytes(f"fake jpg {i}".encode())
            frames.append(
                Frame(
                    video_id=VideoId(0),
                    image_key=str(file_path),
                    timestamp_ms=i * 5000,
                    is_keyframe=(i == 0),
                )
            )
        return frames


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    eng = build_engine(tmp_path / "test.db")
    init_db(eng)
    return eng


@pytest.fixture()
def storage_root(tmp_path: Path) -> Path:
    root = tmp_path / "storage"
    root.mkdir()
    return root


@pytest.fixture()
def cache_dir(tmp_path: Path) -> Path:
    c = tmp_path / "cache"
    c.mkdir()
    return c


@pytest.fixture()
def media_storage(storage_root: Path) -> LocalMediaStorage:
    return LocalMediaStorage(storage_root)


@pytest.fixture()
def media_file(storage_root: Path) -> str:
    """Create a fake media file under storage and return the key."""
    key = "videos/youtube/abc123/media.mp4"
    target = storage_root / "videos" / "youtube" / "abc123"
    target.mkdir(parents=True, exist_ok=True)
    (target / "media.mp4").write_bytes(b"fake media")
    return key


def _seed_video(engine: Engine, media_key: str) -> VideoId:
    with SqliteUnitOfWork(engine) as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("abc123"),
                url="https://example.com",
                media_key=media_key,
            )
        )
        assert video.id is not None
        return video.id


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestFramesStageHappyPath:
    def test_extracts_and_persists_frames(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        media_file: str,
        cache_dir: Path,
        storage_root: Path,
    ) -> None:
        video_id = _seed_video(engine, media_file)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc123"),
            media_key=media_file,
        )
        stage = FramesStage(
            frame_extractor=FakeFrameExtractor(frame_count=4),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )

        with SqliteUnitOfWork(engine) as uow:
            result = stage.execute(ctx, uow)

        assert "extracted 4 frames" in result.message
        assert len(ctx.frame_ids) == 4

        with SqliteUnitOfWork(engine) as uow:
            persisted = uow.frames.list_for_video(video_id)
            assert len(persisted) == 4
            for idx, frame in enumerate(persisted):
                assert frame.image_key == (
                    f"videos/youtube/abc123/frames/{idx:04d}.jpg"
                )
                assert frame.timestamp_ms == idx * 5000

        # Verify the actual files landed in MediaStorage
        for idx in range(4):
            stored = storage_root / "videos" / "youtube" / "abc123" / "frames" / f"{idx:04d}.jpg"
            assert stored.exists()

    def test_is_satisfied_false_when_no_frames(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
        media_file: str,
    ) -> None:
        video_id = _seed_video(engine, media_file)
        ctx = PipelineContext(source_url="x", video_id=video_id)
        stage = FramesStage(
            frame_extractor=FakeFrameExtractor(),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False

    def test_is_satisfied_true_after_first_run(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
        media_file: str,
    ) -> None:
        video_id = _seed_video(engine, media_file)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc123"),
            media_key=media_file,
        )
        stage = FramesStage(
            frame_extractor=FakeFrameExtractor(frame_count=2),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is True


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestFramesStageErrors:
    def test_missing_video_id_raises(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
        media_file: str,
    ) -> None:
        ctx = PipelineContext(source_url="x", media_key=media_file)
        stage = FramesStage(
            frame_extractor=FakeFrameExtractor(),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            FrameExtractionError, match=r"video_id"
        ):
            stage.execute(ctx, uow)

    def test_missing_media_key_raises(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
    ) -> None:
        ctx = PipelineContext(source_url="x", video_id=VideoId(1))
        stage = FramesStage(
            frame_extractor=FakeFrameExtractor(),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            FrameExtractionError, match=r"media_key"
        ):
            stage.execute(ctx, uow)

    def test_extractor_failure_propagates(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
        media_file: str,
    ) -> None:
        video_id = _seed_video(engine, media_file)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc123"),
            media_key=media_file,
        )
        extractor = FakeFrameExtractor(
            error=FrameExtractionError("ffmpeg crashed")
        )
        stage = FramesStage(
            frame_extractor=extractor,
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            FrameExtractionError, match="ffmpeg crashed"
        ):
            stage.execute(ctx, uow)

    def test_no_frames_returned_raises(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        cache_dir: Path,
        media_file: str,
    ) -> None:
        video_id = _seed_video(engine, media_file)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
            platform=Platform.YOUTUBE,
            platform_id=PlatformId("abc123"),
            media_key=media_file,
        )
        stage = FramesStage(
            frame_extractor=FakeFrameExtractor(frame_count=0),
            media_storage=media_storage,
            cache_dir=cache_dir,
        )
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            FrameExtractionError, match="no frames"
        ):
            stage.execute(ctx, uow)
