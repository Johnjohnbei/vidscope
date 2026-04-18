"""Integration tests for VisualIntelligenceStage (M008/S02-P01 T03).

Uses the real SqliteUnitOfWork + in-memory engine + a stubbed
OcrEngine (we don't want to depend on rapidocr being installed in
the test env). Verifies the full persistence path: FrameText rows
land in the DB with FK cascade, FTS5 rows exist, and OCR-sourced
Link rows are written to the links table with source='ocr' and
position_ms correctly set.
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


class _LocalMediaStorage:
    def __init__(self, base: Path) -> None:
        self._base = base

    def resolve(self, key: str) -> Path:
        return self._base / key


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

        # 3. Build the stage with stubbed OcrEngine keyed by resolved paths.
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
            link_extractor=RegexLinkExtractor(),
            media_storage=_LocalMediaStorage(tmp_path),
        )

        # 4. Execute the stage in its own UoW transaction.
        ctx = PipelineContext(source_url="https://youtube.com/shorts/test-id-1")
        ctx.video_id = vid_id
        ctx.platform = Platform.YOUTUBE
        with SqliteUnitOfWork(engine) as uow:
            result = stage.execute(ctx, uow)

        assert result.skipped is False

        # 5. Verify persisted rows (open a fresh UoW).
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

        # 6. Verify FTS5 sync on frame_texts_fts.
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

        stub = _StubOcr(
            {
                str(tmp_path / "frames/x.jpg"): [
                    OcrLine(text="Any text", confidence=0.9)
                ]
            }
        )
        stage = VisualIntelligenceStage(
            ocr_engine=stub,
            link_extractor=RegexLinkExtractor(),
            media_storage=_LocalMediaStorage(tmp_path),
        )
        ctx = PipelineContext(source_url="x")
        ctx.video_id = vid_id

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is True
