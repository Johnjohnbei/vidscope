"""Tests for TranscribeStage with a fake Transcriber + real SQLite UoW."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.fs.local_media_storage import LocalMediaStorage
from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    Language,
    MediaType,
    Platform,
    PlatformId,
    Transcript,
    TranscriptionError,
    TranscriptSegment,
    Video,
    VideoId,
)
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.pipeline.stages.transcribe import TranscribeStage
from vidscope.ports import PipelineContext

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeTranscriber:
    """A Transcriber port stand-in.

    Returns a preset Transcript on transcribe(), or raises a preset
    error if `error` is non-None. Records every call.
    """

    transcript: Transcript | None = None
    error: Exception | None = None
    calls: list[str] = field(default_factory=list)

    def transcribe(self, media_path: str) -> Transcript:
        self.calls.append(media_path)
        if self.error is not None:
            raise self.error
        if self.transcript is not None:
            return self.transcript
        # Default empty transcript
        return Transcript(
            video_id=VideoId(0),
            language=Language.ENGLISH,
            full_text="default fake text",
            segments=(TranscriptSegment(0.0, 1.0, "default fake text"),),
        )


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
def media_storage(storage_root: Path) -> LocalMediaStorage:
    return LocalMediaStorage(storage_root)


@pytest.fixture()
def media_file(storage_root: Path) -> str:
    """Create a fake media file under MediaStorage and return its key."""
    key = "videos/youtube/abc123/media.mp4"
    target = storage_root / "videos" / "youtube" / "abc123"
    target.mkdir(parents=True, exist_ok=True)
    (target / "media.mp4").write_bytes(b"fake media content")
    return key


def _seed_video(engine: Engine, media_key: str) -> VideoId:
    with SqliteUnitOfWork(engine) as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("abc123"),
                url="https://www.youtube.com/shorts/abc123",
                title="seeded",
                media_key=media_key,
            )
        )
        assert video.id is not None
        return video.id


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestTranscribeStageHappyPath:
    def test_execute_persists_transcript_and_mutates_context(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        media_file: str,
    ) -> None:
        video_id = _seed_video(engine, media_file)
        ctx = PipelineContext(
            source_url="https://www.youtube.com/shorts/abc123",
            video_id=video_id,
            media_key=media_file,
        )

        transcript = Transcript(
            video_id=VideoId(0),
            language=Language.FRENCH,
            full_text="Bonjour le monde",
            segments=(
                TranscriptSegment(0.0, 1.5, "Bonjour"),
                TranscriptSegment(1.5, 3.0, "le monde"),
            ),
        )
        transcriber = FakeTranscriber(transcript=transcript)
        stage = TranscribeStage(
            transcriber=transcriber, media_storage=media_storage
        )

        with SqliteUnitOfWork(engine) as uow:
            result = stage.execute(ctx, uow)

        assert "transcribed fr" in result.message
        assert "2 segments" in result.message
        assert ctx.transcript_id is not None
        assert ctx.language is Language.FRENCH

        with SqliteUnitOfWork(engine) as uow:
            persisted = uow.transcripts.get_for_video(video_id)
            assert persisted is not None
            assert persisted.video_id == video_id
            assert persisted.language is Language.FRENCH
            assert persisted.full_text == "Bonjour le monde"
            assert len(persisted.segments) == 2

    def test_is_satisfied_false_when_no_transcript(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        media_file: str,
    ) -> None:
        video_id = _seed_video(engine, media_file)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
            media_key=media_file,
        )
        stage = TranscribeStage(
            transcriber=FakeTranscriber(), media_storage=media_storage
        )
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False

    def test_is_satisfied_true_after_first_run(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        media_file: str,
    ) -> None:
        video_id = _seed_video(engine, media_file)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
            media_key=media_file,
        )
        stage = TranscribeStage(
            transcriber=FakeTranscriber(), media_storage=media_storage
        )

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        # Subsequent run sees the transcript and is satisfied
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is True

    def test_is_satisfied_false_when_video_id_missing(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
    ) -> None:
        ctx = PipelineContext(source_url="x")  # no video_id
        stage = TranscribeStage(
            transcriber=FakeTranscriber(), media_storage=media_storage
        )
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestTranscribeStageErrors:
    def test_missing_video_id_raises(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        media_file: str,
    ) -> None:
        ctx = PipelineContext(
            source_url="x",
            media_key=media_file,
        )  # no video_id
        stage = TranscribeStage(
            transcriber=FakeTranscriber(), media_storage=media_storage
        )
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            TranscriptionError, match=r"ctx\.video_id"
        ):
            stage.execute(ctx, uow)

    def test_missing_media_key_raises(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
    ) -> None:
        ctx = PipelineContext(
            source_url="x",
            video_id=VideoId(1),
        )  # no media_key
        stage = TranscribeStage(
            transcriber=FakeTranscriber(), media_storage=media_storage
        )
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            TranscriptionError, match="media_key"
        ):
            stage.execute(ctx, uow)

    def test_missing_media_file_on_disk_raises(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
    ) -> None:
        # Reference a key that doesn't exist on disk
        video_id = _seed_video(engine, "videos/ghost/none/media.mp4")
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
            media_key="videos/ghost/none/media.mp4",
        )
        stage = TranscribeStage(
            transcriber=FakeTranscriber(), media_storage=media_storage
        )
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            TranscriptionError, match="not found"
        ):
            stage.execute(ctx, uow)

    def test_transcriber_failure_propagates(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        media_file: str,
    ) -> None:
        video_id = _seed_video(engine, media_file)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
            media_key=media_file,
        )
        transcriber = FakeTranscriber(
            error=TranscriptionError("audio decode failed")
        )
        stage = TranscribeStage(
            transcriber=transcriber, media_storage=media_storage
        )
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            TranscriptionError, match="audio decode failed"
        ):
            stage.execute(ctx, uow)

    def test_stage_name_matches_enum(
        self, media_storage: LocalMediaStorage
    ) -> None:
        from vidscope.domain import StageName

        stage = TranscribeStage(
            transcriber=FakeTranscriber(), media_storage=media_storage
        )
        assert stage.name == StageName.TRANSCRIBE.value


# ---------------------------------------------------------------------------
# IMAGE / CAROUSEL short-circuit
# ---------------------------------------------------------------------------


class TestTranscribeStageMediaType:
    """is_satisfied must return True immediately for non-video media types
    without touching the DB (no video_id required)."""

    def test_is_satisfied_returns_true_for_image(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
    ) -> None:
        ctx = PipelineContext(
            source_url="https://www.instagram.com/p/img1/",
            media_type=MediaType.IMAGE,
            # Deliberately no video_id — DB must not be queried
        )
        stage = TranscribeStage(
            transcriber=FakeTranscriber(), media_storage=media_storage
        )
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is True

    def test_is_satisfied_returns_true_for_carousel(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
    ) -> None:
        ctx = PipelineContext(
            source_url="https://www.instagram.com/p/carousel1/",
            media_type=MediaType.CAROUSEL,
        )
        stage = TranscribeStage(
            transcriber=FakeTranscriber(), media_storage=media_storage
        )
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is True

    def test_is_satisfied_video_checks_db_and_returns_false_when_no_transcript(
        self,
        engine: Engine,
        media_storage: LocalMediaStorage,
        media_file: str,
    ) -> None:
        """VIDEO media type falls through to the DB query; no transcript → False."""
        video_id = _seed_video(engine, media_file)
        ctx = PipelineContext(
            source_url="https://www.youtube.com/watch?v=abc123",
            video_id=video_id,
            media_key=media_file,
            media_type=MediaType.VIDEO,
        )
        stage = TranscribeStage(
            transcriber=FakeTranscriber(), media_storage=media_storage
        )
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False
