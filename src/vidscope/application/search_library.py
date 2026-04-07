"""Full-text search over transcripts and analyses — ``vidscope search``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.ports import SearchResult, UnitOfWorkFactory

__all__ = ["SearchLibraryResult", "SearchLibraryUseCase"]


@dataclass(frozen=True, slots=True)
class SearchLibraryResult:
    """Result of :meth:`SearchLibraryUseCase.execute`.

    ``query`` is echoed back so the CLI can display "results for X".
    ``hits`` is ordered by BM25 rank (best match first) and capped at
    the use case's ``limit``. Empty tuple is a valid state and means
    no documents matched the query.
    """

    query: str
    hits: tuple[SearchResult, ...]


class SearchLibraryUseCase:
    """Run a FTS5 query through the :class:`SearchIndex` port."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, query: str, *, limit: int = 20) -> SearchLibraryResult:
        """Search transcripts and analysis summaries for ``query``.

        Returns up to ``limit`` matches ranked by BM25 (best first).
        ``limit`` is clamped to [1, 200] to prevent unbounded result
        sets. The query goes through the :class:`SearchIndex` port so
        the FTS5 backend stays swappable.
        """
        limit = max(1, min(limit, 200))
        with self._uow_factory() as uow:
            hits = tuple(uow.search_index.search(query, limit=limit))
        return SearchLibraryResult(query=query, hits=hits)
