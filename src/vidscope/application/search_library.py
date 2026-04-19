"""Full-text search over transcripts and analyses — ``vidscope search``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import VideoId
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
    """Run a FTS5 query with optional facet filters through the :class:`SearchIndex` port."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        query: str,
        *,
        limit: int = 20,
        hashtag: str | None = None,
        mention: str | None = None,
        has_link: bool | None = None,
        music_track: str | None = None,
        on_screen_text: str | None = None,
    ) -> SearchLibraryResult:
        """Search with optional facets.

        Facets are combined with AND (intersection). When ``query`` is empty
        and at least one facet is active, results are synthesised from the
        facet set without calling the FTS5 index.

        Parameters
        ----------
        query: FTS5 text query. Empty string skips the FTS5 call.
        hashtag: Filter to videos tagged with this hashtag (lowercased, # stripped).
        mention: Filter to videos mentioning this handle (@-stripped, lowercased).
        has_link: When True, filter to videos with at least one link.
        music_track: Filter to videos whose music_track exactly matches.
        on_screen_text: Filter to videos whose frames contain this text (FTS5 on frame_texts).
        limit: Max results, clamped to [1, 200].
        """
        limit = max(1, min(limit, 200))

        with self._uow_factory() as uow:
            # --- Build per-facet candidate sets ---
            candidate_sets: list[set[int]] = []

            if hashtag is not None:
                canonical = hashtag.lower().lstrip("#")
                ids = uow.hashtags.find_video_ids_by_tag(canonical, limit=limit)
                candidate_sets.append({int(v) for v in ids})

            if mention is not None:
                canonical_handle = mention.lower().lstrip("@")
                ids = uow.mentions.find_video_ids_by_handle(canonical_handle, limit=limit)
                candidate_sets.append({int(v) for v in ids})

            if has_link:
                ids = uow.links.find_video_ids_with_any_link(limit=limit)
                candidate_sets.append({int(v) for v in ids})

            if on_screen_text is not None and on_screen_text.strip():
                ids = uow.frame_texts.find_video_ids_by_text(
                    on_screen_text.strip(), limit=limit
                )
                candidate_sets.append({int(v) for v in ids})

            # --- FTS5 path ---
            has_facets = bool(candidate_sets) or music_track is not None
            fts_hits: list[SearchResult] = []
            if query.strip():
                fts_hits = uow.search_index.search(query, limit=limit)

            # --- Combine ---
            if not query.strip() and not has_facets:
                return SearchLibraryResult(query=query, hits=())

            if query.strip() and not has_facets and music_track is None:
                return SearchLibraryResult(query=query, hits=tuple(fts_hits))

            # Intersect FTS hits with facet candidates
            if query.strip() and candidate_sets:
                intersection = set.intersection(*candidate_sets)
                fts_hits = [h for h in fts_hits if int(h.video_id) in intersection]
                candidate_sets = []  # already applied

            if query.strip() and music_track is not None:
                # Apply music_track filter on top of FTS hits
                filtered: list[SearchResult] = []
                for h in fts_hits:
                    video = uow.videos.get(VideoId(int(h.video_id)))
                    if video is not None and video.music_track == music_track:
                        filtered.append(h)
                return SearchLibraryResult(query=query, hits=tuple(filtered))

            if query.strip() and not candidate_sets:
                return SearchLibraryResult(query=query, hits=tuple(fts_hits))

            # Pure facet path (no FTS query or remaining candidate sets)
            if candidate_sets:
                intersection = set.intersection(*candidate_sets)
            else:
                intersection = set()

            if music_track is not None:
                # music_track is not yet a DB column (schema migration pending).
                # _row_to_video always returns music_track=None, so music_ids
                # will always be empty until the column is added to videos_table.
                recent = uow.videos.list_recent(limit=1000)
                music_ids = {
                    int(v.id) for v in recent
                    if v.music_track == music_track and v.id is not None
                }
                if intersection:
                    intersection &= music_ids
                else:
                    intersection = music_ids

            if not intersection:
                return SearchLibraryResult(query=query, hits=())

            # Synthesise SearchResult for each matched video
            hits: list[SearchResult] = []
            for vid_int in sorted(intersection)[:limit]:
                video = uow.videos.get(VideoId(vid_int))
                hits.append(
                    SearchResult(
                        video_id=VideoId(vid_int),
                        source="video",
                        snippet=video.title or "" if video else "",
                        rank=1.0,
                    )
                )

        return SearchLibraryResult(query=query, hits=tuple(hits))
