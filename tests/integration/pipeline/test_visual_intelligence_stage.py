"""Integration tests for VisualIntelligenceStage (M008/S02-P01 T03 + S03-P01 T03).

Uses the real SqliteUnitOfWork + in-memory engine + stubbed OcrEngine and
FaceCounter (we don't want to depend on rapidocr/opencv being installed in
the test env). Verifies the full persistence path: FrameText rows land in
the DB with FK cascade, FTS5 rows exist, OCR-sourced Link rows are written
with source='ocr' and position_ms, and (S03) thumbnail_key + content_shape
columns are persisted on the videos row.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.adapters.text import RegexLinkExtractor
from vidscope.domain import (
    Frame,
    Platform,
    PlatformId,
    Video,
)
from vidscope.pipeline.stages import VisualIntelligenceStage
from vidscope.ports import PipelineContext
from vidscope.ports.ocr_engine import OcrLine


class _StubOcr:
    def __init__(self, mapping: dict[str, list[OcrLine]]) -> None:
        self._mapping = mapping
        self._unavailable = False

    def extract_text(
        self, image_path: str, *, min_confidence: float = 0.5
    ) -> list[OcrLine]:
        return [
            line for line in self._mapping.get(image_path, [])
            if line.confidence >= min_confidence
        ]


class _StubFaceCounter:
    def __init__(self, mapping: dict[str, int] | None = None) -> None:
        self._mapping = mapping or {}

    def count_faces(self, image_path: str) -> int:
        return self._mapping.get(image_path, 0)


class _LocalMediaStorage:
    """Minimal MediaStorage stub: resolve() returns base/key, store() copies."""

    def __init__(self, base: Path) -> None:
        self._base = base

    def resolve(self, key: str) -> Path:
        return self._base / key

    def store(self, key: str, source_path: Path) -> str:
        dest = self._base / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(source_path, dest)
        return key


@pytest.mark.integration
class TestVisualIntelligenceIntegration:
    def test_persists_frame_texts_and_ocr_links(self, tmp_path: Path) -> None:
        # 1. Build a real SQLite UoW.
        engine = create_engine("sqlite:///:memory:")
        init_db(engine)

        # 2. Seed the DB with a video + frames.
        with SqliteUnitOfWork(engine) as uow:
            video = uow.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("test-id-1"),
                    url="https://youtube.com/shorts/test-id-1",
                )
            )
            assert video.id is not None
            vid_id = video.id
            frame_a = Path("frames/a.jpg")
            frame_b = Path("frames/b.jpg")
            uow.frames.add_many(
                [
                    Frame(video_id=vid_id, image_key=str(frame_a), timestamp_ms=1000),
                    Frame(video_id=vid_id, image_key=str(frame_b), timestamp_ms=3000),
                ]
            )

        # 3. Create minimal frame files so store() can copy them.
        (tmp_path / "frames").mkdir(parents=True, exist_ok=True)
        (tmp_path / "frames" / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
        (tmp_path / "frames" / "b.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")

        # 4. Build the stage with stubbed OcrEngine keyed by resolved paths.
        resolved_a = str(tmp_path / "frames/a.jpg")
        resolved_b = str(tmp_path / "frames/b.jpg")
        stub = _StubOcr(
            {
                resolved_a: [OcrLine(text="Visit example.com for promo", confidence=0.9)],
                resolved_b: [OcrLine(text="Follow @alice", confidence=0.9)],
            }
        )
        stage = VisualIntelligenceStage(
            ocr_engine=stub,
            face_counter=_StubFaceCounter(),
            link_extractor=RegexLinkExtractor(),
            media_storage=_LocalMediaStorage(tmp_path),
        )

        # 5. Execute the stage in its own UoW transaction.
        ctx = PipelineContext(source_url="https://youtube.com/shorts/test-id-1")
        ctx.video_id = vid_id
        ctx.platform = Platform.YOUTUBE
        ctx.platform_id = PlatformId("test-id-1")
        with SqliteUnitOfWork(engine) as uow:
            result = stage.execute(ctx, uow)

        assert result.skipped is False

        # 6. Verify persisted rows (open a fresh UoW).
        with SqliteUnitOfWork(engine) as uow:
            texts = uow.frame_texts.list_for_video(vid_id)
            assert len(texts) == 2
            text_values = {t.text for t in texts}
            assert "Visit example.com for promo" in text_values
            assert "Follow @alice" in text_values

            ocr_links = uow.links.list_for_video(vid_id, source="ocr")
            assert len(ocr_links) == 1
            assert "example.com" in ocr_links[0].normalized_url
            assert ocr_links[0].position_ms == 1000

        # 7. Verify FTS5 sync on frame_texts_fts.
        with engine.begin() as conn:
            count = conn.execute(
                text(
                    "SELECT count(*) FROM frame_texts_fts "
                    "WHERE video_id = :v"
                ),
                {"v": int(vid_id)},
            ).scalar()
            assert count == 2

    def test_is_satisfied_after_execute(self, tmp_path: Path) -> None:
        engine = create_engine("sqlite:///:memory:")
        init_db(engine)
        with SqliteUnitOfWork(engine) as uow:
            video = uow.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("test-id-2"),
                    url="https://youtube.com/shorts/x",
                )
            )
            assert video.id is not None
            vid_id = video.id
            uow.frames.add_many(
                [Frame(video_id=vid_id, image_key="frames/x.jpg", timestamp_ms=0)]
            )

        # Create frame file so store() can copy.
        (tmp_path / "frames").mkdir(parents=True, exist_ok=True)
        (tmp_path / "frames" / "x.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")

        stub = _StubOcr(
            {
                str(tmp_path / "frames/x.jpg"): [
                    OcrLine(text="Any text", confidence=0.9)
                ]
            }
        )
        stage = VisualIntelligenceStage(
            ocr_engine=stub,
            face_counter=_StubFaceCounter(),
            link_extractor=RegexLinkExtractor(),
            media_storage=_LocalMediaStorage(tmp_path),
        )
        ctx = PipelineContext(source_url="x")
        ctx.video_id = vid_id
        ctx.platform = Platform.YOUTUBE
        ctx.platform_id = PlatformId("test-id-2")

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        # S03: compound is_satisfied requires frame_texts + thumbnail_key + content_shape
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is True


@pytest.mark.integration
class TestVisualIntelligenceIntegrationS03:
    def test_thumbnail_and_content_shape_persisted(self, tmp_path: Path) -> None:
        """End-to-end: thumbnail file on disk + videos row has both columns."""
        engine = create_engine("sqlite:///:memory:")
        init_db(engine)

        # Write minimal JPG bytes — file existence is what matters for store().
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        jpg_bytes = b"\xff\xd8\xff\xe0fake-jpg"
        frame_paths = []
        for i in range(3):
            p = frames_dir / f"{i}.jpg"
            p.write_bytes(jpg_bytes)
            frame_paths.append(p)

        from vidscope.adapters.fs.local_media_storage import LocalMediaStorage

        media = LocalMediaStorage(tmp_path)

        with SqliteUnitOfWork(engine) as uow:
            video = uow.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("vid-42"),
                    url="https://youtube.com/shorts/vid-42",
                )
            )
            assert video.id is not None
            vid_id = video.id
            uow.frames.add_many(
                [
                    Frame(video_id=vid_id, image_key=f"frames/{i}.jpg", timestamp_ms=i * 1000)
                    for i in range(3)
                ]
            )

        # Stub OcrEngine and FaceCounter — deterministic inputs.
        # 2/3 frames have faces = 66.7% ≥ 40% → talking_head
        stub_ocr = _StubOcr(
            {str(frame_paths[1]): [OcrLine(text="Visit example.com", confidence=0.9)]}
        )
        stub_face = _StubFaceCounter(
            {
                str(frame_paths[0]): 1,
                str(frame_paths[1]): 1,
                str(frame_paths[2]): 0,
            }
        )
        stage = VisualIntelligenceStage(
            ocr_engine=stub_ocr,
            face_counter=stub_face,
            link_extractor=RegexLinkExtractor(),
            media_storage=media,
        )

        ctx = PipelineContext(source_url="x")
        ctx.video_id = vid_id
        ctx.platform = Platform.YOUTUBE
        ctx.platform_id = PlatformId("vid-42")

        with SqliteUnitOfWork(engine) as uow:
            result = stage.execute(ctx, uow)
        assert result.skipped is False

        # Assert persisted state on the videos row.
        with SqliteUnitOfWork(engine) as uow:
            v = uow.videos.get(vid_id)
            assert v is not None
            assert v.content_shape == "talking_head"
            assert v.thumbnail_key == "videos/youtube/vid-42/thumb.jpg"

        # Assert thumbnail file exists on disk at the canonical path.
        thumb_disk = tmp_path / "videos" / "youtube" / "vid-42" / "thumb.jpg"
        assert thumb_disk.exists()
        assert thumb_disk.read_bytes() == jpg_bytes

    def test_is_satisfied_after_full_execution(self, tmp_path: Path) -> None:
        """is_satisfied returns True only after all three outputs are in place."""
        engine = create_engine("sqlite:///:memory:")
        init_db(engine)

        frames_dir = tmp_path / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        (frames_dir / "0.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpg")

        from vidscope.adapters.fs.local_media_storage import LocalMediaStorage

        media = LocalMediaStorage(tmp_path)

        with SqliteUnitOfWork(engine) as uow:
            video = uow.videos.add(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("vid-99"),
                    url="https://youtube.com/shorts/vid-99",
                )
            )
            assert video.id is not None
            vid_id = video.id
            uow.frames.add_many(
                [Frame(video_id=vid_id, image_key="frames/0.jpg", timestamp_ms=0)]
            )

        frame_path = str(frames_dir / "0.jpg")
        stub_ocr = _StubOcr(
            {frame_path: [OcrLine(text="Hello world", confidence=0.9)]}
        )
        stage = VisualIntelligenceStage(
            ocr_engine=stub_ocr,
            face_counter=_StubFaceCounter({frame_path: 1}),
            link_extractor=RegexLinkExtractor(),
            media_storage=media,
        )

        ctx = PipelineContext(source_url="x")
        ctx.video_id = vid_id
        ctx.platform = Platform.YOUTUBE
        ctx.platform_id = PlatformId("vid-99")

        # Before execute: not satisfied.
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False

        # After execute: fully satisfied.
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is True
