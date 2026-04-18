"""SearchVideosUseCase -- M010 extension of search_library with facet filters.

Adds optional filters on content_type, min_actionability, and is_sponsored.
When any filter is set, the use case first narrows the candidate video_ids
via AnalysisRepository.list_by_filters, then runs the FTS5 query and keeps
only hits that belong to the allowed set. When no filter is set, the use
case behaves exactly like SearchLibraryUseCase (pure FTS5 passthrough).
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.application.search_library import SearchLibraryResult
from vidscope.domain import ContentType
from vidscope.ports import SearchResult, UnitOfWorkFactory

__all__ = ["SearchFilters", "SearchVideosUseCase"]


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Facet filters applied to the search result.

    All fields default to ``None`` -- a ``SearchFilters()`` instance with
    every field ``None`` means "no filter".

    Fields
    ------
    content_type:
        When set, only videos whose latest analysis has this
        ``content_type`` are returned.
    min_actionability:
        When set, only videos whose latest analysis has
        ``actionability >= min_actionability`` (NOT NULL) are returned.
    is_sponsored:
        When ``True``: only sponsored videos. When ``False``: only
        non-sponsored videos (NULL excluded). ``None``: no filter.
    """

    content_type: ContentType | None = None
    min_actionability: float | None = None
    is_sponsored: bool | None = None

    def is_empty(self) -> bool:
        return (
            self.content_type is None
            and self.min_actionability is None
            and self.is_sponsored is None
        )


class SearchVideosUseCase:
    """Run an FTS5 query with optional facet filters on the analysis."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        query: str,
        *,
        limit: int = 20,
        filters: SearchFilters | None = None,
    ) -> SearchLibraryResult:
        limit = max(1, min(limit, 200))
        filters = filters or SearchFilters()

        with self._uow_factory() as uow:
            if filters.is_empty():
                hits = tuple(uow.search_index.search(query, limit=limit))
                return SearchLibraryResult(query=query, hits=hits)

            allowed_video_ids = set(
                int(v)
                for v in uow.analyses.list_by_filters(
                    content_type=filters.content_type,
                    min_actionability=filters.min_actionability,
                    is_sponsored=filters.is_sponsored,
                    limit=1000,
                )
            )
            if not allowed_video_ids:
                return SearchLibraryResult(query=query, hits=())

            # Oversample FTS5 hits so we can filter without losing too many
            # -- cap by a reasonable multiplier.
            raw_hits = uow.search_index.search(query, limit=max(limit, limit * 5))
            filtered: list[SearchResult] = []
            for hit in raw_hits:
                if int(hit.video_id) in allowed_video_ids:
                    filtered.append(hit)
                    if len(filtered) >= limit:
                        break
            return SearchLibraryResult(query=query, hits=tuple(filtered))
