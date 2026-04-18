"""Unit tests for SearchVideosUseCase -- filter logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

from vidscope.application.search_videos import (
    SearchFilters,
    SearchVideosUseCase,
)
from vidscope.domain import ContentType


@dataclass(frozen=True)
class _FakeHit:
    """Minimal SearchResult-shaped record."""
    video_id: int
    source: str
    rank: float
    snippet: str


def _make_factory(*, hits: list, allowed_ids: list[int] | None = None) -> Any:
    class _UoW:
        def __init__(self) -> None:
            self.search_index = MagicMock()
            self.search_index.search = MagicMock(return_value=hits)
            self.analyses = MagicMock()
            self.analyses.list_by_filters = MagicMock(return_value=allowed_ids or [])

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    return lambda: _UoW()


class TestSearchFiltersIsEmpty:
    def test_all_none_is_empty(self) -> None:
        assert SearchFilters().is_empty() is True

    def test_any_set_not_empty(self) -> None:
        assert SearchFilters(content_type=ContentType.TUTORIAL).is_empty() is False
        assert SearchFilters(min_actionability=70.0).is_empty() is False
        assert SearchFilters(is_sponsored=True).is_empty() is False


class TestSearchVideosWithoutFilters:
    def test_no_filters_passes_through_search_index(self) -> None:
        hits = [_FakeHit(1, "transcript", 0.9, "...")]
        uc = SearchVideosUseCase(unit_of_work_factory=_make_factory(hits=hits))
        result = uc.execute("python")
        assert result.query == "python"
        assert len(result.hits) == 1
        assert result.hits[0].video_id == 1

    def test_empty_filters_behaves_like_no_filters(self) -> None:
        hits = [_FakeHit(1, "transcript", 0.9, "...")]
        uc = SearchVideosUseCase(unit_of_work_factory=_make_factory(hits=hits))
        result = uc.execute("python", filters=SearchFilters())
        assert len(result.hits) == 1


class TestSearchVideosWithFilters:
    def test_filters_restrict_to_allowed_ids(self) -> None:
        hits = [
            _FakeHit(1, "transcript", 0.9, "...a..."),
            _FakeHit(2, "transcript", 0.8, "...b..."),
            _FakeHit(3, "transcript", 0.7, "...c..."),
        ]
        uc = SearchVideosUseCase(unit_of_work_factory=_make_factory(
            hits=hits, allowed_ids=[1, 3],
        ))
        result = uc.execute(
            "python",
            filters=SearchFilters(content_type=ContentType.TUTORIAL),
        )
        ids = [h.video_id for h in result.hits]
        assert 1 in ids
        assert 3 in ids
        assert 2 not in ids

    def test_no_allowed_ids_returns_empty_hits(self) -> None:
        hits = [_FakeHit(1, "transcript", 0.9, "...")]
        uc = SearchVideosUseCase(unit_of_work_factory=_make_factory(
            hits=hits, allowed_ids=[],
        ))
        result = uc.execute("python",
                            filters=SearchFilters(content_type=ContentType.TUTORIAL))
        assert result.hits == ()

    def test_limit_respected_with_filters(self) -> None:
        hits = [_FakeHit(i, "transcript", 0.5, "...") for i in range(1, 20)]
        uc = SearchVideosUseCase(unit_of_work_factory=_make_factory(
            hits=hits, allowed_ids=list(range(1, 20)),
        ))
        result = uc.execute("python", limit=3,
                            filters=SearchFilters(is_sponsored=False))
        assert len(result.hits) <= 3

    def test_filters_combine_all_three(self) -> None:
        hits = [_FakeHit(1, "transcript", 0.9, "...")]
        fake_uow = _make_factory(hits=hits, allowed_ids=[1])
        uc = SearchVideosUseCase(unit_of_work_factory=fake_uow)
        result = uc.execute(
            "x",
            filters=SearchFilters(
                content_type=ContentType.TUTORIAL,
                min_actionability=70.0,
                is_sponsored=False,
            ),
        )
        # Le resultat principal: filtrage correct
        assert result.hits[0].video_id == 1


class TestNoInfrastructureImport:
    """application-has-no-adapters contract sanity check."""

    def test_module_has_no_adapter_or_infra_imports(self) -> None:
        src = open(
            "src/vidscope/application/search_videos.py",
            encoding="utf-8",
        ).read()
        for forbidden in (
            "from vidscope.adapters",
            "from vidscope.infrastructure",
            "import yaml",
            "import sqlalchemy",
            "import httpx",
        ):
            assert forbidden not in src, f"unexpected import: {forbidden}"
