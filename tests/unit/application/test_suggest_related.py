"""Tests for SuggestRelatedUseCase."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.application.suggest_related import (
    SuggestRelatedResult,
    SuggestRelatedUseCase,
)
from vidscope.domain import (
    Analysis,
    Language,
    Platform,
    PlatformId,
    Video,
    VideoId,
)
from vidscope.infrastructure.sqlite_engine import build_engine


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    eng = build_engine(tmp_path / "test.db")
    init_db(eng)
    return eng


@pytest.fixture()
def uow_factory(engine: Engine):  # type: ignore[no-untyped-def]
    def _factory():  # type: ignore[no-untyped-def]
        return SqliteUnitOfWork(engine)

    return _factory


def _seed_video_with_keywords(
    engine: Engine,
    *,
    platform_id: str,
    title: str,
    keywords: tuple[str, ...],
    has_analysis: bool = True,
) -> VideoId:
    """Seed one video + one analysis with the given keywords."""
    with SqliteUnitOfWork(engine) as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId(platform_id),
                url=f"https://example.com/{platform_id}",
                title=title,
                media_key=f"videos/youtube/{platform_id}/media.mp4",
            )
        )
        assert video.id is not None
        if has_analysis:
            uow.analyses.add(
                Analysis(
                    video_id=video.id,
                    provider="heuristic",
                    language=Language.ENGLISH,
                    keywords=keywords,
                    topics=keywords[:3],
                    score=50.0,
                    summary=f"about {' '.join(keywords)}",
                )
            )
        return video.id


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSuggestRelatedHappyPath:
    def test_returns_related_video_ranked_by_overlap(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        source_id = _seed_video_with_keywords(
            engine,
            platform_id="source",
            title="Python cooking tips",
            keywords=("python", "cooking", "recipe", "tips"),
        )
        # High overlap: 3/5 keywords match
        _seed_video_with_keywords(
            engine,
            platform_id="high",
            title="Python recipe book",
            keywords=("python", "recipe", "tips", "food"),
        )
        # Low overlap: 1/7 keywords match
        _seed_video_with_keywords(
            engine,
            platform_id="low",
            title="Gardening basics",
            keywords=("gardening", "plants", "soil", "water", "tips"),
        )
        # Zero overlap: excluded
        _seed_video_with_keywords(
            engine,
            platform_id="none",
            title="Dog training",
            keywords=("dog", "training", "leash"),
        )

        use_case = SuggestRelatedUseCase(unit_of_work_factory=uow_factory)
        result = use_case.execute(int(source_id), limit=10)

        assert isinstance(result, SuggestRelatedResult)
        assert result.source_found is True
        assert result.source_title == "Python cooking tips"
        assert len(result.suggestions) == 2
        # High-overlap video ranked first
        assert result.suggestions[0].title == "Python recipe book"
        assert result.suggestions[0].score > result.suggestions[1].score
        assert "python" in result.suggestions[0].matched_keywords

    def test_limit_clamps_results(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        source_id = _seed_video_with_keywords(
            engine,
            platform_id="source",
            title="source",
            keywords=("a", "b", "c", "d"),
        )
        for i in range(5):
            _seed_video_with_keywords(
                engine,
                platform_id=f"match{i}",
                title=f"match{i}",
                keywords=("a", "b"),  # partial overlap with source
            )

        use_case = SuggestRelatedUseCase(unit_of_work_factory=uow_factory)
        result = use_case.execute(int(source_id), limit=3)
        assert len(result.suggestions) == 3

    def test_source_video_excluded_from_results(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        source_id = _seed_video_with_keywords(
            engine,
            platform_id="source",
            title="source",
            keywords=("shared",),
        )
        # One other video with the exact same keyword
        _seed_video_with_keywords(
            engine,
            platform_id="other",
            title="other",
            keywords=("shared",),
        )

        result = SuggestRelatedUseCase(
            unit_of_work_factory=uow_factory
        ).execute(int(source_id))
        # Source video is NEVER in suggestions
        assert all(s.video_id != source_id for s in result.suggestions)
        assert len(result.suggestions) == 1
        assert result.suggestions[0].title == "other"

    def test_matched_keywords_are_only_the_intersection(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        source_id = _seed_video_with_keywords(
            engine,
            platform_id="source",
            title="source",
            keywords=("a", "b", "c"),
        )
        _seed_video_with_keywords(
            engine,
            platform_id="other",
            title="other",
            keywords=("b", "c", "d"),
        )

        result = SuggestRelatedUseCase(
            unit_of_work_factory=uow_factory
        ).execute(int(source_id))
        assert len(result.suggestions) == 1
        assert result.suggestions[0].matched_keywords == ("b", "c")


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


class TestSuggestRelatedEdgeCases:
    def test_missing_source_returns_not_found(
        self,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        result = SuggestRelatedUseCase(
            unit_of_work_factory=uow_factory
        ).execute(999)
        assert result.source_found is False
        assert result.suggestions == ()
        assert "no video with id 999" in result.reason

    def test_source_with_no_analysis_returns_empty(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        source_id = _seed_video_with_keywords(
            engine,
            platform_id="source",
            title="source",
            keywords=(),
            has_analysis=False,
        )
        result = SuggestRelatedUseCase(
            unit_of_work_factory=uow_factory
        ).execute(int(source_id))
        assert result.source_found is True
        assert result.suggestions == ()
        assert "no analysis keywords" in result.reason

    def test_source_with_empty_keywords_returns_empty(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        source_id = _seed_video_with_keywords(
            engine,
            platform_id="source",
            title="source",
            keywords=(),  # analysis exists but no keywords
        )
        result = SuggestRelatedUseCase(
            unit_of_work_factory=uow_factory
        ).execute(int(source_id))
        assert result.suggestions == ()
        assert "no analysis keywords" in result.reason

    def test_library_with_only_source_returns_empty(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        source_id = _seed_video_with_keywords(
            engine,
            platform_id="only",
            title="only video",
            keywords=("lonely",),
        )
        result = SuggestRelatedUseCase(
            unit_of_work_factory=uow_factory
        ).execute(int(source_id))
        assert result.suggestions == ()
        assert "no candidates share keywords" in result.reason

    def test_candidates_without_analyses_are_skipped(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        source_id = _seed_video_with_keywords(
            engine,
            platform_id="source",
            title="source",
            keywords=("shared", "more"),
        )
        # Matching candidate with analysis
        _seed_video_with_keywords(
            engine,
            platform_id="with-analysis",
            title="with analysis",
            keywords=("shared", "extra"),
        )
        # Candidate without analysis (has_analysis=False)
        _seed_video_with_keywords(
            engine,
            platform_id="no-analysis",
            title="no analysis",
            keywords=(),
            has_analysis=False,
        )

        result = SuggestRelatedUseCase(
            unit_of_work_factory=uow_factory
        ).execute(int(source_id))
        assert len(result.suggestions) == 1
        assert result.suggestions[0].title == "with analysis"

    def test_invalid_limit_is_clamped(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        source_id = _seed_video_with_keywords(
            engine,
            platform_id="source",
            title="source",
            keywords=("a",),
        )
        for i in range(3):
            _seed_video_with_keywords(
                engine,
                platform_id=f"m{i}",
                title=f"m{i}",
                keywords=("a",),
            )

        # Negative limit → clamped to 1
        result = SuggestRelatedUseCase(
            unit_of_work_factory=uow_factory
        ).execute(int(source_id), limit=-5)
        assert len(result.suggestions) == 1

        # Huge limit → returns everything available
        result2 = SuggestRelatedUseCase(
            unit_of_work_factory=uow_factory
        ).execute(int(source_id), limit=9999)
        assert len(result2.suggestions) == 3


# ---------------------------------------------------------------------------
# Score ordering
# ---------------------------------------------------------------------------


class TestJaccardOrdering:
    def test_full_overlap_beats_partial(
        self,
        engine: Engine,
        uow_factory,  # type: ignore[no-untyped-def]
    ) -> None:
        source_id = _seed_video_with_keywords(
            engine,
            platform_id="source",
            title="source",
            keywords=("a", "b", "c"),
        )
        _seed_video_with_keywords(
            engine,
            platform_id="partial",
            title="partial",
            keywords=("a", "b", "x"),
        )
        _seed_video_with_keywords(
            engine,
            platform_id="full",
            title="full",
            keywords=("a", "b", "c"),  # exact same keyword set
        )

        result = SuggestRelatedUseCase(
            unit_of_work_factory=uow_factory
        ).execute(int(source_id))
        assert len(result.suggestions) == 2
        # 'full' has Jaccard 1.0, 'partial' has 2/4 = 0.5
        assert result.suggestions[0].title == "full"
        assert result.suggestions[0].score == pytest.approx(1.0)
        assert result.suggestions[1].title == "partial"
        assert result.suggestions[1].score == pytest.approx(0.5)
