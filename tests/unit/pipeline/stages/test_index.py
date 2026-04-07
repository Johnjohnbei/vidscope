"""Tests for IndexStage with real SQLite + FTS5."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import (
    Analysis,
    IndexingError,
    Language,
    Platform,
    PlatformId,
    Transcript,
    TranscriptSegment,
    Video,
    VideoId,
)
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.pipeline.stages.index import IndexStage
from vidscope.ports import PipelineContext


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    eng = build_engine(tmp_path / "test.db")
    init_db(eng)
    return eng


def _seed_full_video(
    engine: Engine,
    *,
    transcript_text: str = "the quick brown fox jumps",
    analysis_summary: str = "a video about a fox and its activities",
) -> VideoId:
    with SqliteUnitOfWork(engine) as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("idx-test"),
                url="https://example.com",
                media_key="videos/youtube/idx-test/media.mp4",
            )
        )
        assert video.id is not None
        if transcript_text:
            uow.transcripts.add(
                Transcript(
                    video_id=video.id,
                    language=Language.ENGLISH,
                    full_text=transcript_text,
                    segments=(
                        TranscriptSegment(0.0, 1.0, transcript_text),
                    ),
                )
            )
        if analysis_summary:
            uow.analyses.add(
                Analysis(
                    video_id=video.id,
                    provider="heuristic",
                    language=Language.ENGLISH,
                    keywords=("fox", "video"),
                    topics=("fox",),
                    score=50.0,
                    summary=analysis_summary,
                )
            )
        return video.id


class TestIndexStageHappyPath:
    def test_indexes_transcript_and_analysis(self, engine: Engine) -> None:
        video_id = _seed_full_video(engine)
        ctx = PipelineContext(source_url="x", video_id=video_id)
        stage = IndexStage()

        with SqliteUnitOfWork(engine) as uow:
            result = stage.execute(ctx, uow)

        assert "indexed 2 documents" in result.message

        # Verify search returns hits for both the transcript and analysis
        with SqliteUnitOfWork(engine) as uow:
            transcript_hits = uow.search_index.search("fox")
            assert len(transcript_hits) >= 1
            sources = {hit.source for hit in transcript_hits}
            assert "transcript" in sources or "analysis_summary" in sources

    def test_searches_match_specific_words(self, engine: Engine) -> None:
        video_id = _seed_full_video(
            engine,
            transcript_text="cooking pasta with fresh tomatoes",
            analysis_summary="italian cuisine recipe video",
        )
        ctx = PipelineContext(source_url="x", video_id=video_id)
        with SqliteUnitOfWork(engine) as uow:
            IndexStage().execute(ctx, uow)

        with SqliteUnitOfWork(engine) as uow:
            results = uow.search_index.search("pasta")
            assert any(r.video_id == video_id for r in results)

    def test_indexes_only_transcript_when_no_analysis(
        self, engine: Engine
    ) -> None:
        video_id = _seed_full_video(
            engine,
            transcript_text="hello world",
            analysis_summary="",  # no analysis summary
        )
        ctx = PipelineContext(source_url="x", video_id=video_id)
        with SqliteUnitOfWork(engine) as uow:
            result = IndexStage().execute(ctx, uow)
        assert "indexed 1 documents" in result.message

    def test_indexes_zero_when_no_transcript_and_no_analysis(
        self, engine: Engine
    ) -> None:
        # Seed only the video, no transcript or analysis
        with SqliteUnitOfWork(engine) as uow:
            video = uow.videos.upsert_by_platform_id(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("empty"),
                    url="https://example.com",
                    media_key="videos/youtube/empty/media.mp4",
                )
            )
            assert video.id is not None
            video_id = video.id

        ctx = PipelineContext(source_url="x", video_id=video_id)
        with SqliteUnitOfWork(engine) as uow:
            result = IndexStage().execute(ctx, uow)
        assert "indexed 0 documents" in result.message

    def test_is_satisfied_always_false(self, engine: Engine) -> None:
        ctx = PipelineContext(source_url="x", video_id=VideoId(1))
        with SqliteUnitOfWork(engine) as uow:
            assert IndexStage().is_satisfied(ctx, uow) is False


class TestIndexStageErrors:
    def test_missing_video_id_raises(self, engine: Engine) -> None:
        ctx = PipelineContext(source_url="x")
        with SqliteUnitOfWork(engine) as uow, pytest.raises(
            IndexingError, match="video_id"
        ):
            IndexStage().execute(ctx, uow)
