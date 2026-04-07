"""Full-text search over transcripts and analyses — ``vidscope search``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.ports import SearchResult, UnitOfWorkFactory

__all__ = ["SearchLibraryResult", "SearchLibraryUseCase"]


@dataclass(frozen=True, slots=True)
class SearchLibraryResult:
    query: str
    hits: tuple[SearchResult, ...]


class SearchLibraryUseCase:
    """Run a FTS5 query through the :class:`SearchIndex` port."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, query: str, *, limit: int = 20) -> SearchLibraryResult:
        limit = max(1, min(limit, 200))
        with self._uow_factory() as uow:
            hits = tuple(uow.search_index.search(query, limit=limit))
        return SearchLibraryResult(query=query, hits=hits)
