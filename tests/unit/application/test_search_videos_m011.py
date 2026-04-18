"""SearchVideosUseCase tests — M011/S03 extension (R058).

Adds tests for the 4 new facets on top of the M010 coverage.
These tests are EXPECTED TO FAIL in the RED phase before the implementation
extends SearchFilters and SearchVideosUseCase.
"""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.application.search_videos import SearchFilters, SearchVideosUseCase
from vidscope.application.search_library import SearchLibraryResult
from vidscope.domain import ContentType, TrackingStatus, VideoId, VideoTracking, Tag, Collection


# ---- Fakes ----

@dataclass
class FakeHit:
    video_id: int
    source: str = "transcript"
    rank: float = 0.5
    snippet: str = "..."


class _FakeSearchIndex:
    def __init__(self, hits: list[FakeHit]) -> None:
        self._hits = hits

    def search(self, query: str, *, limit: int = 20):
        return self._hits[:limit]


class _FakeAnalysisRepo:
    def __init__(self, allowed: list[int]) -> None:
        self._allowed = allowed

    def list_by_filters(self, *, content_type=None, min_actionability=None, is_sponsored=None, limit=1000):
        return [VideoId(v) for v in self._allowed]


class _FakeTrackingRepo:
    def __init__(self, by_status: dict[TrackingStatus, list[int]], starred_ids: list[int]) -> None:
        self._by_status = by_status
        self._starred = starred_ids
        self.calls: list[str] = []

    def list_by_status(self, status, *, limit=1000):
        self.calls.append(f"list_by_status({status.value})")
        ids = self._by_status.get(status, [])
        return [
            VideoTracking(video_id=VideoId(i), status=status) for i in ids
        ]

    def list_starred(self, *, limit=1000):
        self.calls.append("list_starred")
        return [
            VideoTracking(video_id=VideoId(i), status=TrackingStatus.NEW, starred=True)
            for i in self._starred
        ]

    def get_for_video(self, video_id): return None
    def upsert(self, tracking): return tracking


class _FakeTagRepo:
    def __init__(self, by_tag: dict[str, list[int]]) -> None:
        self._by_tag = by_tag
        self.calls: list[str] = []

    def list_video_ids_for_tag(self, name, *, limit=1000):
        self.calls.append(f"list_video_ids_for_tag({name})")
        return [VideoId(v) for v in self._by_tag.get(name.lower().strip(), [])]

    def get_or_create(self, name): raise NotImplementedError
    def get_by_name(self, name): return None
    def list_all(self, *, limit=1000): return []
    def list_for_video(self, video_id): return []
    def assign(self, video_id, tag_id): pass
    def unassign(self, video_id, tag_id): pass


class _FakeCollectionRepo:
    def __init__(self, by_coll: dict[str, list[int]]) -> None:
        self._by_coll = by_coll
        self.calls: list[str] = []

    def list_video_ids_for_collection(self, name, *, limit=1000):
        self.calls.append(f"list_video_ids_for_collection({name})")
        return [VideoId(v) for v in self._by_coll.get(name.strip(), [])]

    def create(self, name): raise NotImplementedError
    def get_by_name(self, name): return None
    def list_all(self, *, limit=1000): return []
    def add_video(self, coll_id, video_id): pass
    def remove_video(self, coll_id, video_id): pass
    def list_videos(self, coll_id, *, limit=1000): return []
    def list_collections_for_video(self, video_id): return []


class _FakeUoW:
    def __init__(
        self,
        hits: list[FakeHit],
        analysis_allowed: list[int] | None = None,
        tracking_by_status: dict[TrackingStatus, list[int]] | None = None,
        starred: list[int] | None = None,
        tags: dict[str, list[int]] | None = None,
        collections: dict[str, list[int]] | None = None,
    ) -> None:
        self.search_index = _FakeSearchIndex(hits)
        self.analyses = _FakeAnalysisRepo(analysis_allowed or [])
        self.video_tracking = _FakeTrackingRepo(tracking_by_status or {}, starred or [])
        self.tags = _FakeTagRepo(tags or {})
        self.collections = _FakeCollectionRepo(collections or {})

    def __enter__(self): return self
    def __exit__(self, *args): return None


def _factory(uow):
    def _make(): return uow
    return _make


# ---- SearchFilters tests ----

class TestSearchFiltersExtended:
    def test_default_is_empty(self) -> None:
        assert SearchFilters().is_empty() is True

    def test_status_makes_non_empty(self) -> None:
        assert SearchFilters(status=TrackingStatus.SAVED).is_empty() is False

    def test_starred_true_non_empty(self) -> None:
        assert SearchFilters(starred=True).is_empty() is False

    def test_starred_false_non_empty(self) -> None:
        assert SearchFilters(starred=False).is_empty() is False

    def test_starred_none_empty_if_others_none(self) -> None:
        assert SearchFilters(starred=None).is_empty() is True

    def test_tag_makes_non_empty(self) -> None:
        assert SearchFilters(tag="x").is_empty() is False

    def test_collection_makes_non_empty(self) -> None:
        assert SearchFilters(collection="y").is_empty() is False

    def test_m010_facets_still_work(self) -> None:
        assert SearchFilters(content_type=ContentType.TUTORIAL).is_empty() is False


# ---- Backward-compat tests ----

class TestBackwardCompat:
    def test_empty_filters_pure_fts5_path(self) -> None:
        hits = [FakeHit(video_id=1), FakeHit(video_id=2)]
        uow = _FakeUoW(hits)
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q")
        assert isinstance(result, SearchLibraryResult)
        assert len(result.hits) == 2
        # No workflow repo was called
        assert uow.video_tracking.calls == []
        assert uow.tags.calls == []
        assert uow.collections.calls == []


# ---- M011 facet path tests ----

class TestStatusFacet:
    def test_filters_by_status(self) -> None:
        hits = [FakeHit(video_id=1), FakeHit(video_id=2), FakeHit(video_id=3)]
        uow = _FakeUoW(
            hits,
            tracking_by_status={TrackingStatus.SAVED: [2, 3]},
        )
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(status=TrackingStatus.SAVED))
        ids = [h.video_id for h in result.hits]
        assert 2 in ids
        assert 3 in ids
        assert 1 not in ids


class TestStarredFacet:
    def test_starred_true(self) -> None:
        hits = [FakeHit(video_id=1), FakeHit(video_id=2), FakeHit(video_id=3)]
        uow = _FakeUoW(hits, starred=[1, 3])
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(starred=True))
        assert {h.video_id for h in result.hits} == {1, 3}

    def test_starred_false_excludes(self) -> None:
        hits = [FakeHit(video_id=1), FakeHit(video_id=2), FakeHit(video_id=3)]
        uow = _FakeUoW(hits, starred=[1, 3])
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(starred=False))
        assert {h.video_id for h in result.hits} == {2}


class TestTagFacet:
    def test_filters_by_tag(self) -> None:
        hits = [FakeHit(video_id=i) for i in range(1, 6)]
        uow = _FakeUoW(hits, tags={"idea": [2, 4]})
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(tag="Idea"))
        # Tag normalization happens inside repo fake (lowercase)
        assert {h.video_id for h in result.hits} == {2, 4}


class TestCollectionFacet:
    def test_filters_by_collection(self) -> None:
        hits = [FakeHit(video_id=i) for i in range(1, 6)]
        uow = _FakeUoW(hits, collections={"MyCol": [3]})
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(collection="MyCol"))
        assert {h.video_id for h in result.hits} == {3}


class TestMultiFacetIntersection:
    def test_status_and_tag_and_collection(self) -> None:
        hits = [FakeHit(video_id=i) for i in range(1, 11)]
        uow = _FakeUoW(
            hits,
            tracking_by_status={TrackingStatus.SAVED: [2, 3, 5, 7]},
            tags={"idea": [3, 5, 8]},
            collections={"MyCol": [3, 5, 9]},
        )
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute(
            "q",
            filters=SearchFilters(
                status=TrackingStatus.SAVED, tag="idea", collection="MyCol",
            ),
        )
        # Intersection: {2,3,5,7} ∩ {3,5,8} ∩ {3,5,9} = {3, 5}
        assert {h.video_id for h in result.hits} == {3, 5}

    def test_empty_intersection_returns_no_hits(self) -> None:
        hits = [FakeHit(video_id=i) for i in range(1, 6)]
        uow = _FakeUoW(
            hits,
            tags={"idea": [1, 2]},
            collections={"Other": [4, 5]},
        )
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(tag="idea", collection="Other"))
        assert result.hits == ()

    def test_starred_false_alone_excludes_starred(self) -> None:
        """starred=False alone: allowed=None but excluded_starred filters complement."""
        hits = [FakeHit(video_id=1), FakeHit(video_id=2), FakeHit(video_id=3)]
        uow = _FakeUoW(hits, starred=[1, 3])
        uc = SearchVideosUseCase(unit_of_work_factory=_factory(uow))
        result = uc.execute("q", filters=SearchFilters(starred=False))
        # Only video_id=2 is not starred
        assert {h.video_id for h in result.hits} == {2}
