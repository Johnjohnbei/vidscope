"""SearchVideosUseCase — M010+M011 facetted search across the library.

M010 facets (analysis): content_type, min_actionability, is_sponsored.
M011 facets (workflow): status, starred, tag, collection.

Strategy (D5 M011 RESEARCH): keep the two-phase approach —
narrow candidate video_ids via AND intersection across source
repositories, then filter FTS5 hits. This avoids the need for a
single JOIN through the FTS5 virtual table (which does not cooperate
with standard SQLAlchemy joins cleanly).

Backward compatibility: all new SearchFilters fields default to None,
`is_empty()` covers every field. A call `SearchFilters()` without
arguments preserves the pre-M011 fast-path (pure FTS5).
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.application.search_library import SearchLibraryResult
from vidscope.domain import ContentType, TrackingStatus
from vidscope.ports import SearchResult, UnitOfWorkFactory

__all__ = ["SearchFilters", "SearchVideosUseCase"]


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Facet filters applied to the search result.

    All fields default to ``None``. ``SearchFilters()`` is a no-op
    filter — the use case takes the fast path (pure FTS5).

    M010 fields (analysis — NE PAS MODIFIER):
        content_type: Latest analysis must have this content_type.
        min_actionability: Latest analysis.actionability >= value (NOT NULL).
        is_sponsored: Latest analysis.is_sponsored strictly equals the bool.

    M011 fields (workflow):
        status: video_tracking.status equals the enum.
        starred: True = starred only. False = non-starred (complement).
        tag: Video has this tag (lowercased).
        collection: Video is in this collection (case-preserved).
    """

    content_type: ContentType | None = None
    min_actionability: float | None = None
    is_sponsored: bool | None = None
    status: TrackingStatus | None = None
    starred: bool | None = None
    tag: str | None = None
    collection: str | None = None

    def is_empty(self) -> bool:
        return (
            self.content_type is None
            and self.min_actionability is None
            and self.is_sponsored is None
            and self.status is None
            and self.starred is None
            and self.tag is None
            and self.collection is None
        )


class SearchVideosUseCase:
    """Run an FTS5 query with optional multi-facet filters (AND semantics)."""

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

            # Gather allowed_video_ids sources (positive constraints).
            sources: list[set[int]] = []

            # M010 analysis facets (combined in ONE call to list_by_filters).
            if (
                filters.content_type is not None
                or filters.min_actionability is not None
                or filters.is_sponsored is not None
            ):
                analysis_ids = {
                    int(v)
                    for v in uow.analyses.list_by_filters(
                        content_type=filters.content_type,
                        min_actionability=filters.min_actionability,
                        is_sponsored=filters.is_sponsored,
                        limit=10_000,
                    )
                }
                sources.append(analysis_ids)

            # M011 status facet.
            if filters.status is not None:
                status_ids = {
                    int(t.video_id)
                    for t in uow.video_tracking.list_by_status(
                        filters.status, limit=10_000,
                    )
                }
                sources.append(status_ids)

            # M011 starred facet — True adds positive constraint,
            # False adds NEGATIVE constraint (excluded_starred).
            excluded_starred: set[int] | None = None
            if filters.starred is True:
                starred_ids = {
                    int(t.video_id)
                    for t in uow.video_tracking.list_starred(limit=10_000)
                }
                sources.append(starred_ids)
            elif filters.starred is False:
                excluded_starred = {
                    int(t.video_id)
                    for t in uow.video_tracking.list_starred(limit=10_000)
                }

            # M011 tag facet.
            if filters.tag is not None:
                tag_ids = {
                    int(v)
                    for v in uow.tags.list_video_ids_for_tag(
                        filters.tag, limit=10_000,
                    )
                }
                sources.append(tag_ids)

            # M011 collection facet.
            if filters.collection is not None:
                coll_ids = {
                    int(v)
                    for v in uow.collections.list_video_ids_for_collection(
                        filters.collection, limit=10_000,
                    )
                }
                sources.append(coll_ids)

            # AND intersection across sources.
            allowed: set[int] | None
            if sources:
                allowed = set.intersection(*sources) if len(sources) > 1 else sources[0]
            else:
                allowed = None  # only --unstarred was set (excluded_starred only)

            if allowed is not None and not allowed:
                return SearchLibraryResult(query=query, hits=())

            # Oversample FTS5 so we still return `limit` after post-filter.
            raw_hits = uow.search_index.search(query, limit=max(limit, limit * 5))
            filtered: list[SearchResult] = []
            for hit in raw_hits:
                vid = int(hit.video_id)
                if allowed is not None and vid not in allowed:
                    continue
                if excluded_starred is not None and vid in excluded_starred:
                    continue
                filtered.append(hit)
                if len(filtered) >= limit:
                    break
            return SearchLibraryResult(query=query, hits=tuple(filtered))
