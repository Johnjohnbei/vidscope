"""Tests for AnalyzeStage with a fake Analyzer + real adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    Analysis,
    AnalysisError,
    Language,
    Platform,
    PlatformId,
    Transcript,
    TranscriptSegment,
    Video,
    VideoId,
)
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.pipeline.stages.analyze import AnalyzeStage
from vidscope.ports import PipelineContext


@dataclass
class FakeAnalyzer:
    """Stand-in for the Analyzer port."""

    provider_name_value: str = "fake"
    error: Exception | None = None
    calls: list[Transcript] = field(default_factory=list)

    @property
    def provider_name(self) -> str:
        return self.provider_name_value

    def analyze(self, transcript: Transcript) -> Analysis:
        self.calls.append(transcript)
        if self.error is not None:
            raise self.error
        return Analysis(
            video_id=transcript.video_id,
            provider=self.provider_name_value,
            language=transcript.language,
            keywords=("fake", "test", "analysis"),
            topics=("fake-topic",),
            score=75.0,
            summary="fake summary from FakeAnalyzer",
        )


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    eng = build_engine(tmp_path / "test.db")
    init_db(eng)
    return eng


def _seed_video_with_transcript(
    engine: Engine, *, with_transcript: bool = True
) -> VideoId:
    with SqliteUnitOfWork(engine) as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("abc"),
                url="https://example.com",
                media_key="videos/youtube/abc/media.mp4",
            )
        )
        assert video.id is not None
        if with_transcript:
            uow.transcripts.add(
                Transcript(
                    video_id=video.id,
                    language=Language.ENGLISH,
                    full_text="some text to analyze",
                    segments=(
                        TranscriptSegment(0.0, 1.0, "some text to analyze"),
                    ),
                )
            )
        return video.id


class TestAnalyzeStageHappyPath:
    def test_persists_analysis_and_mutates_context(
        self, engine: Engine
    ) -> None:
        video_id = _seed_video_with_transcript(engine)
        ctx = PipelineContext(source_url="x", video_id=video_id)
        stage = AnalyzeStage(analyzer=FakeAnalyzer())

        with SqliteUnitOfWork(engine) as uow:
            result = stage.execute(ctx, uow)

        assert "analyzed via fake" in result.message
        assert "3 keywords" in result.message
        assert "score=75" in result.message
        assert ctx.analysis_id is not None

        with SqliteUnitOfWork(engine) as uow:
            persisted = uow.analyses.get_latest_for_video(video_id)
            assert persisted is not None
            assert persisted.provider == "fake"
            assert persisted.video_id == video_id
            assert persisted.score == 75.0
            assert persisted.keywords == ("fake", "test", "analysis")

    def test_is_satisfied_false_when_no_analysis(
        self, engine: Engine
    ) -> None:
        video_id = _seed_video_with_transcript(engine)
        ctx = PipelineContext(source_url="x", video_id=video_id)
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False

    def test_is_satisfied_true_after_first_run(
        self, engine: Engine
    ) -> None:
        video_id = _seed_video_with_transcript(engine)
        ctx = PipelineContext(source_url="x", video_id=video_id)
        stage = AnalyzeStage(analyzer=FakeAnalyzer())

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is True


class TestAnalyzeStageErrors:
    def test_missing_video_id_raises(self, engine: Engine) -> None:
        ctx = PipelineContext(source_url="x")
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            AnalysisError, match="video_id"
        ):
            stage.execute(ctx, uow)

    def test_missing_transcript_raises(self, engine: Engine) -> None:
        # Seed a video WITHOUT a transcript
        video_id = _seed_video_with_transcript(engine, with_transcript=False)
        ctx = PipelineContext(source_url="x", video_id=video_id)
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            AnalysisError, match="transcript"
        ):
            stage.execute(ctx, uow)

    def test_analyzer_failure_propagates(self, engine: Engine) -> None:
        video_id = _seed_video_with_transcript(engine)
        ctx = PipelineContext(source_url="x", video_id=video_id)
        stage = AnalyzeStage(
            analyzer=FakeAnalyzer(error=AnalysisError("provider down"))
        )
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            AnalysisError, match="provider down"
        ):
            stage.execute(ctx, uow)


# ---------------------------------------------------------------------------
# R062 — IMAGE / CAROUSEL OCR fallback
# ---------------------------------------------------------------------------


def _seed_video_without_transcript(
    engine: Engine,
    *,
    platform_id: str = "carousel1",
    media_key: str = "videos/instagram/carousel1/items/0000.jpg",
) -> VideoId:
    """Insert a Video row (no transcript, no analysis, no frame_texts)."""
    with SqliteUnitOfWork(engine) as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.INSTAGRAM,
                platform_id=PlatformId(platform_id),
                url=f"https://www.instagram.com/p/{platform_id}/",
                media_key=media_key,
            )
        )
        assert video.id is not None
        return video.id


class TestAnalyzeStageMediaTypeR062:
    """R062 — is_satisfied no longer short-circuits IMAGE/CAROUSEL.

    Replaces the deleted M010 tests: carousels/images must be analyzed
    when OCR frame_texts exist, so is_satisfied must actually check
    whether an Analysis row exists for the video.
    """

    def test_is_satisfied_false_for_carousel_without_analysis(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import MediaType

        video_id = _seed_video_without_transcript(
            engine, platform_id="carousel_none"
        )
        ctx = PipelineContext(
            source_url="https://www.instagram.com/p/carousel_none/",
            video_id=video_id,
            media_type=MediaType.CAROUSEL,
        )
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False

    def test_is_satisfied_false_for_image_without_analysis(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import MediaType

        video_id = _seed_video_without_transcript(
            engine, platform_id="image_none"
        )
        ctx = PipelineContext(
            source_url="https://www.instagram.com/p/image_none/",
            video_id=video_id,
            media_type=MediaType.IMAGE,
        )
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False

    def test_is_satisfied_true_for_carousel_with_analysis(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import MediaType

        video_id = _seed_video_with_transcript(engine)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
            media_type=MediaType.CAROUSEL,
        )
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        # Seed an existing analysis
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is True

    def test_is_satisfied_false_without_video_id(self, engine: Engine) -> None:
        from vidscope.domain import MediaType

        ctx = PipelineContext(source_url="x", media_type=MediaType.CAROUSEL)
        stage = AnalyzeStage(analyzer=FakeAnalyzer())
        with SqliteUnitOfWork(engine) as uow:
            assert stage.is_satisfied(ctx, uow) is False


# ---------------------------------------------------------------------------
# R062 — execute() OCR fallback
# ---------------------------------------------------------------------------


def _seed_carousel_with_frame_texts(
    engine: Engine,
    *,
    platform_id: str = "carousel_with_ocr",
    texts: tuple[str, ...] = ("Hello world", "Second block"),
) -> VideoId:
    """Insert a Video + 1 Frame + N FrameText rows (no transcript).

    Frames are ordered frame_id ASC (one frame per call), so
    FrameTextRepository.list_for_video returns them in insertion order.
    """
    from vidscope.domain import Frame, FrameText

    with SqliteUnitOfWork(engine) as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.INSTAGRAM,
                platform_id=PlatformId(platform_id),
                url=f"https://www.instagram.com/p/{platform_id}/",
                media_key=f"videos/instagram/{platform_id}/items/0000.jpg",
            )
        )
        assert video.id is not None
        frame = uow.frames.add_many(
            [
                Frame(
                    video_id=video.id,
                    image_key=f"videos/instagram/{platform_id}/items/0000.jpg",
                    timestamp_ms=0,
                    is_keyframe=True,
                )
            ]
        )[0]
        assert frame.id is not None
        uow.frame_texts.add_many_for_frame(
            frame.id,
            video.id,
            [
                FrameText(
                    video_id=video.id,
                    frame_id=frame.id,
                    text=t,
                    confidence=0.95,
                )
                for t in texts
            ],
        )
        return video.id


class TestAnalyzeStageOcrFallback:
    """R062 — execute() falls back to frame_texts when transcript is None."""

    def test_carousel_with_frame_texts_produces_analysis(
        self, engine: Engine
    ) -> None:
        from vidscope.domain import Language, MediaType

        video_id = _seed_carousel_with_frame_texts(
            engine,
            platform_id="carousel_ocr_1",
            texts=("Claude skills for Architects", "Terminal workflow tip"),
        )
        fake = FakeAnalyzer()
        stage = AnalyzeStage(analyzer=fake)
        ctx = PipelineContext(
            source_url="https://www.instagram.com/p/carousel_ocr_1/",
            video_id=video_id,
            media_type=MediaType.CAROUSEL,
        )

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        # Analyzer received a synthetic Transcript
        assert len(fake.calls) == 1
        received = fake.calls[0]
        assert received.video_id == video_id
        assert received.language is Language.UNKNOWN
        # Concatenation preserves order (frame_id ASC, id ASC)
        assert "Claude skills for Architects" in received.full_text
        assert "Terminal workflow tip" in received.full_text
        assert received.full_text.index("Claude") < received.full_text.index(
            "Terminal"
        )
        assert received.segments == ()

        # Analysis was persisted
        assert ctx.analysis_id is not None
        with SqliteUnitOfWork(engine) as uow:
            persisted = uow.analyses.get_latest_for_video(video_id)
            assert persisted is not None
            assert persisted.video_id == video_id

    def test_carousel_without_transcript_and_without_frame_texts_produces_stub(
        self, engine: Engine
    ) -> None:
        """R062 success criteria #4 — no crash, stub Analysis persisted."""
        from vidscope.adapters.heuristic import HeuristicAnalyzer
        from vidscope.domain import MediaType

        video_id = _seed_video_without_transcript(
            engine, platform_id="carousel_empty"
        )
        stage = AnalyzeStage(analyzer=HeuristicAnalyzer())
        ctx = PipelineContext(
            source_url="https://www.instagram.com/p/carousel_empty/",
            video_id=video_id,
            media_type=MediaType.CAROUSEL,
        )

        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)  # must not raise

        with SqliteUnitOfWork(engine) as uow:
            persisted = uow.analyses.get_latest_for_video(video_id)
            assert persisted is not None
            assert persisted.score == 0.0
            assert persisted.summary == "no speech detected"
            assert persisted.keywords == ()

    def test_ocr_concat_filters_empty_and_whitespace_rows(
        self, engine: Engine
    ) -> None:
        """Empty or whitespace-only FrameText.text rows must be filtered
        before concatenation to avoid doubled separators."""
        video_id = _seed_carousel_with_frame_texts(
            engine,
            platform_id="carousel_mixed",
            texts=("Hello", "", "   ", "World"),
        )
        fake = FakeAnalyzer()
        stage = AnalyzeStage(analyzer=fake)
        ctx = PipelineContext(
            source_url="x",
            video_id=video_id,
        )
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        assert len(fake.calls) == 1
        got = fake.calls[0].full_text
        assert got == "Hello World"  # single space, no doubled spacing

    def test_carousel_produces_domain_topics_end_to_end(
        self, engine: Engine
    ) -> None:
        """R062 + R063 integration — real HeuristicAnalyzer returns
        domain tokens from OCR (no French grammar words, proper nouns kept)."""
        from vidscope.adapters.heuristic import HeuristicAnalyzer

        video_id = _seed_carousel_with_frame_texts(
            engine,
            platform_id="carousel_claude_skills",
            texts=(
                "Claude skills for Architects",
                "Terminal workflow with the agent",
                "Claude agent builds skills in the terminal",
            ),
        )
        stage = AnalyzeStage(analyzer=HeuristicAnalyzer())
        ctx = PipelineContext(source_url="x", video_id=video_id)
        with SqliteUnitOfWork(engine) as uow:
            stage.execute(ctx, uow)

        with SqliteUnitOfWork(engine) as uow:
            persisted = uow.analyses.get_latest_for_video(video_id)
            assert persisted is not None
            # Domain tokens present (case-insensitive by tokenizer)
            assert "claude" in persisted.keywords
            assert "skills" in persisted.keywords or "agent" in persisted.keywords
            # Grammar words absent
            assert "the" not in persisted.keywords
            assert "with" not in persisted.keywords
