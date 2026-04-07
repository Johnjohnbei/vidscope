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
