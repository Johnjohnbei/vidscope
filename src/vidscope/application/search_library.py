"""Full-text search + M007 facets — ``vidscope search``."""

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
    no documents matched the query or facets.
    """

    query: str
    hits: tuple[SearchResult, ...]


class SearchLibraryUseCase:
    """Run a FTS5 query + M007 facet filters through the UnitOfWork.

    Facets (per M007 CONTEXT §D-04):

    - ``hashtag``  — exact match after canonicalisation (#Coding == coding)
    - ``mention``  — exact match after canonicalisation (@Alice == alice)
    - ``has_link`` — boolean: at least one extracted URL
    - ``music_track`` — exact match on ``videos.music_track``

    Multi-facet semantics: AND implicite — each facet further narrows
    the result set (set intersection on ``video_id``).

    When ``query`` is empty AND at least one facet is set, the use case
    synthesises :class:`SearchResult` entries (source="video", rank=1.0,
    snippet=<title>) for each matched video so the CLI can still render
    a useful output.
    """

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        query: str,
        *,
        limit: int = 20,
        hashtag: str | None = None,
        mention: str | None = None,
        has_link: bool = False,
        music_track: str | None = None,
    ) -> SearchLibraryResult:
        """Search transcripts + analyses + facets. Returns up to
        ``limit`` matches ranked by BM25 (or facet order when query is
        empty). ``limit`` is clamped to [1, 200].
        """
        limit = max(1, min(limit, 200))
        any_facet = (
            hashtag is not None
            or mention is not None
            or has_link
            or music_track is not None
        )
        query_text = query.strip() if query else ""

        with self._uow_factory() as uow:
            # 1. Collect the candidate video id set per active facet.
            #    Each set is None when the facet is inactive ("no
            #    restriction") — intersection semantics below.
            facet_sets: list[set[int]] = []

            if hashtag is not None:
                ids = uow.hashtags.find_video_ids_by_tag(hashtag, limit=1000)
                facet_sets.append({int(vid) for vid in ids})

            if mention is not None:
                ids = uow.mentions.find_video_ids_by_handle(
                    mention, limit=1000
                )
                facet_sets.append({int(vid) for vid in ids})

            if has_link:
                ids = uow.links.find_video_ids_with_any_link(limit=1000)
                facet_sets.append({int(vid) for vid in ids})

            if music_track is not None:
                # Exact match on videos.music_track. No existing repo
                # method → list_recent + filter in memory. Bounded by
                # 1000 to keep worst case small on libraries with
                # many unrelated videos.
                candidates = uow.videos.list_recent(limit=1000)
                facet_sets.append(
                    {
                        int(v.id)
                        for v in candidates
                        if v.id is not None
                        and v.music_track == music_track
                    }
                )

            # Intersection of all active facet sets. Empty list means
            # no facet was active — no restriction.
            allowed_ids: set[int] | None
            if facet_sets:
                result_set: set[int] = facet_sets[0]
                for s in facet_sets[1:]:
                    result_set = result_set & s
                allowed_ids = result_set
            else:
                allowed_ids = None

            # 2. Dispatch on query presence:
            if query_text:
                # Overfetch a bit so the facet filter still has room to
                # return `limit` results after narrowing.
                raw_hits = uow.search_index.search(
                    query_text, limit=limit * 5 if any_facet else limit
                )
                if allowed_ids is not None:
                    raw_hits = [
                        h for h in raw_hits if int(h.video_id) in allowed_ids
                    ]
                hits = tuple(raw_hits[:limit])
            elif any_facet and allowed_ids is not None:
                # Synthesise SearchResult entries (one per matched
                # video) because the FTS5 index is empty-query-hostile.
                synth: list[SearchResult] = []
                for vid in list(allowed_ids)[:limit]:
                    video = uow.videos.get(VideoId(vid))
                    snippet = (
                        (video.title or f"video #{vid}")
                        if video is not None
                        else f"video #{vid}"
                    )
                    synth.append(
                        SearchResult(
                            video_id=VideoId(vid),
                            source="video",
                            snippet=snippet,
                            rank=1.0,
                        )
                    )
                hits = tuple(synth)
            else:
                hits = ()

        return SearchLibraryResult(query=query_text, hits=hits)
