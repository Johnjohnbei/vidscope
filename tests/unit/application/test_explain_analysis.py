"""Unit tests for ExplainAnalysisUseCase."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from vidscope.application.explain_analysis import (
    ExplainAnalysisResult,
    ExplainAnalysisUseCase,
)
from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    Platform,
    PlatformId,
    SentimentLabel,
    Video,
    VideoId,
)


def _make_video(vid: int = 1) -> Video:
    return Video(
        id=VideoId(vid),
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"p{vid}"),
        url=f"https://y.be/{vid}",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _make_analysis(vid: int = 1) -> Analysis:
    return Analysis(
        video_id=VideoId(vid),
        provider="heuristic",
        language=Language.ENGLISH,
        score=70.0,
        information_density=72.0,
        actionability=85.0,
        sentiment=SentimentLabel.POSITIVE,
        content_type=ContentType.TUTORIAL,
        reasoning="Clear tutorial.",
    )


def _make_uow_factory(*, video: Video | None, analysis: Analysis | None) -> Any:
    class _UoW:
        def __init__(self) -> None:
            self.videos = MagicMock()
            self.videos.get = MagicMock(return_value=video)
            self.analyses = MagicMock()
            self.analyses.get_latest_for_video = MagicMock(return_value=analysis)

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    return lambda: _UoW()


class TestExplainAnalysisHappyPath:
    def test_found_video_with_analysis(self) -> None:
        video = _make_video(1)
        analysis = _make_analysis(1)
        uc = ExplainAnalysisUseCase(unit_of_work_factory=_make_uow_factory(
            video=video, analysis=analysis,
        ))
        result = uc.execute(1)
        assert result.found is True
        assert result.video is video
        assert result.analysis is analysis

    def test_video_missing(self) -> None:
        uc = ExplainAnalysisUseCase(unit_of_work_factory=_make_uow_factory(
            video=None, analysis=None,
        ))
        result = uc.execute(999)
        assert result.found is False
        assert result.video is None
        assert result.analysis is None

    def test_video_present_no_analysis(self) -> None:
        video = _make_video(1)
        uc = ExplainAnalysisUseCase(unit_of_work_factory=_make_uow_factory(
            video=video, analysis=None,
        ))
        result = uc.execute(1)
        assert result.found is True
        assert result.video is video
        assert result.analysis is None
