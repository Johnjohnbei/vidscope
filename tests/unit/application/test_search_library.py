"""Tests for SearchLibraryUseCase — M007/S04-P01 facets.

Pattern: FakeUoW with controllable fakes for each repository and the
search index. Tests cover each facet in isolation and AND combinations.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import pytest

from vidscope.application.search_library import SearchLibraryResult, SearchLibraryUseCase
from vidscope.domain import Hashtag, Link, Mention, Platform, Video, VideoId
from vidscope.domain.values import PlatformId
from vidscope.ports.pipeline import SearchResult

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeSearchIndex:
    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self._results = results or []
        self.last_query: str | None = None
        self.last_limit: int | None = None

    def search(self, query: str, *, limit: int = 20) -> list[SearchResult]:
        self.last_query = query
        self.last_limit = limit
        return self._results[:limit]

    def index_transcript(self, transcript: Any) -> None:
        pass

    def index_analysis(self, analysis: Any) -> None:
        pass


class FakeHashtagRepo:
    def __init__(self, mapping: dict[str, list[int]] | None = None) -> None:
        # mapping: canonical_tag -> list of video_ids
        self._mapping: dict[str, list[int]] = mapping or {}

    def find_video_ids_by_tag(self, tag: str, *, limit: int = 50) -> list[VideoId]:
        canonical = tag.lower().lstrip("#")
        return [VideoId(v) for v in self._mapping.get(canonical, [])[:limit]]

    def replace_for_video(self, video_id: VideoId, tags: list[str]) -> None:
        pass

    def list_for_video(self, video_id: VideoId) -> list[Hashtag]:
        return []


class FakeMentionRepo:
    def __init__(self, mapping: dict[str, list[int]] | None = None) -> None:
        # mapping: canonical_handle (no @) -> list of video_ids
        self._mapping: dict[str, list[int]] = mapping or {}

    def find_video_ids_by_handle(self, handle: str, *, limit: int = 50) -> list[VideoId]:
        canonical = handle.lower().lstrip("@")
        return [VideoId(v) for v in self._mapping.get(canonical, [])[:limit]]

    def replace_for_video(self, video_id: VideoId, mentions: list[Mention]) -> None:
        pass

    def list_for_video(self, video_id: VideoId) -> list[Mention]:
        return []


class FakeLinkRepo:
    def __init__(self, video_ids_with_link: list[int] | None = None) -> None:
        self._ids = video_ids_with_link or []

    def find_video_ids_with_any_link(self, *, limit: int = 50) -> list[VideoId]:
        return [VideoId(v) for v in self._ids[:limit]]

    def add_many_for_video(
        self, video_id: VideoId, links: list[Link]
    ) -> list[Link]:
        return []

    def list_for_video(
        self, video_id: VideoId, *, source: str | None = None
    ) -> list[Link]:
        return []

    def has_any_for_video(self, video_id: VideoId) -> bool:
        return False


class FakeFrameTextRepo:
    def __init__(self, video_ids_by_query: dict[str, list[int]] | None = None) -> None:
        # mapping: query_string -> list of video_ids
        self._mapping: dict[str, list[int]] = video_ids_by_query or {}

    def find_video_ids_by_text(
        self, query: str, *, limit: int = 50
    ) -> list[VideoId]:
        return [VideoId(v) for v in self._mapping.get(query, [])[:limit]]

    def add_many_for_frame(self, frame_id: int, video_id: VideoId, texts: list) -> list:
        return []

    def list_for_video(self, video_id: VideoId) -> list:
        return []

    def has_any_for_video(self, video_id: VideoId) -> bool:
        return False


def _make_video(
    vid: int, title: str = "Test video", music_track: str | None = None
) -> Video:
    return Video(
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(f"yt{vid}"),
        url=f"https://youtube.com/watch?v=yt{vid}",
        id=VideoId(vid),
        title=title,
        music_track=music_track,
    )


class FakeVideoRepo:
    def __init__(self, videos: list[Video] | None = None) -> None:
        self._videos: list[Video] = videos or []
        self._by_id: dict[int, Video] = {int(v.id): v for v in self._videos if v.id}

    def get(self, video_id: VideoId) -> Video | None:
        return self._by_id.get(int(video_id))

    def list_recent(self, limit: int = 20) -> list[Video]:
        return self._videos[:limit]

    def add(self, video: Video) -> Video:
        return video

    def upsert_by_platform_id(self, video: Video) -> Video:
        return video

    def get_by_platform_id(
        self, platform: Platform, platform_id: PlatformId
    ) -> Video | None:
        return None

    def count(self) -> int:
        return len(self._videos)


class FakeUoW:
    """Minimal UoW with controllable fakes."""

    def __init__(
        self,
        *,
        search_index: FakeSearchIndex | None = None,
        hashtags: FakeHashtagRepo | None = None,
        mentions: FakeMentionRepo | None = None,
        links: FakeLinkRepo | None = None,
        videos: FakeVideoRepo | None = None,
        frame_texts: FakeFrameTextRepo | None = None,
    ) -> None:
        self.search_index = search_index or FakeSearchIndex()
        self.hashtags = hashtags or FakeHashtagRepo()
        self.mentions = mentions or FakeMentionRepo()
        self.links = links or FakeLinkRepo()
        self.videos = videos or FakeVideoRepo()
        self.frame_texts = frame_texts or FakeFrameTextRepo()

    def __enter__(self) -> FakeUoW:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass


def _make_uow_factory(**kwargs: Any) -> Any:
    uow = FakeUoW(**kwargs)

    def _factory() -> FakeUoW:
        return uow

    return _factory


def _make_hit(
    video_id: int, source: str = "transcript", rank: float = 1.0
) -> SearchResult:
    return SearchResult(
        video_id=VideoId(video_id),
        source=source,
        snippet="some text",
        rank=rank,
    )


# ---------------------------------------------------------------------------
# Test 1 — baseline: no facet, FTS5 behaviour preserved
# ---------------------------------------------------------------------------


class TestBaseline:
    def test_baseline_no_facets(self) -> None:
        """execute('cooking') sans facette → résultats FTS5 inchangés."""
        hits = [_make_hit(1), _make_hit(2)]
        factory = _make_uow_factory(search_index=FakeSearchIndex(hits))
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("cooking")

        assert isinstance(result, SearchLibraryResult)
        assert result.query == "cooking"
        assert len(result.hits) == 2
        assert result.hits[0].video_id == VideoId(1)

    def test_baseline_empty_query_no_facets_returns_empty(self) -> None:
        """execute('') sans facette → liste vide (pas d'appel FTS5)."""
        factory = _make_uow_factory(
            search_index=FakeSearchIndex([_make_hit(1)])
        )
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("")

        assert result.hits == ()


# ---------------------------------------------------------------------------
# Test 2 — hashtag facet
# ---------------------------------------------------------------------------


class TestHashtagFacet:
    def test_hashtag_filters_fts_hits(self) -> None:
        """Seuls les hits dont video_id est dans hashtag.find_video_ids() passent."""
        fts_hits = [_make_hit(1), _make_hit(2), _make_hit(3)]
        hashtags = FakeHashtagRepo({"coding": [1, 3]})
        factory = _make_uow_factory(
            search_index=FakeSearchIndex(fts_hits),
            hashtags=hashtags,
        )
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", hashtag="coding")

        assert {int(h.video_id) for h in result.hits} == {1, 3}

    def test_hashtag_canonicalisation(self) -> None:
        """execute('', hashtag='#Coding') == execute('', hashtag='coding')."""
        hashtags = FakeHashtagRepo({"coding": [10]})
        videos = FakeVideoRepo([_make_video(10)])
        factory = _make_uow_factory(hashtags=hashtags, videos=videos)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result_with_hash = uc.execute("", hashtag="#Coding")
        result_canonical = uc.execute("", hashtag="coding")

        assert {int(h.video_id) for h in result_with_hash.hits} == {10}
        assert {int(h.video_id) for h in result_canonical.hits} == {10}


# ---------------------------------------------------------------------------
# Test 4 — mention facet
# ---------------------------------------------------------------------------


class TestMentionFacet:
    def test_mention_filters_hits(self) -> None:
        """execute('', mention='@alice') retourne uniquement les hits de alice."""
        fts_hits = [_make_hit(1), _make_hit(2)]
        mentions = FakeMentionRepo({"alice": [2]})
        factory = _make_uow_factory(
            search_index=FakeSearchIndex(fts_hits),
            mentions=mentions,
        )
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", mention="@alice")

        assert {int(h.video_id) for h in result.hits} == {2}

    def test_mention_case_insensitive(self) -> None:
        """'@Alice' et '@alice' retournent le même résultat."""
        mentions = FakeMentionRepo({"alice": [5]})
        videos = FakeVideoRepo([_make_video(5)])
        factory = _make_uow_factory(mentions=mentions, videos=videos)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result_upper = uc.execute("", mention="@Alice")
        result_lower = uc.execute("", mention="@alice")

        assert {int(h.video_id) for h in result_upper.hits} == {5}
        assert {int(h.video_id) for h in result_lower.hits} == {5}


# ---------------------------------------------------------------------------
# Test 5 — has_link facet
# ---------------------------------------------------------------------------


class TestHasLinkFacet:
    def test_has_link_filters_hits(self) -> None:
        """execute('', has_link=True) retourne uniquement les hits avec lien."""
        fts_hits = [_make_hit(10), _make_hit(20), _make_hit(30)]
        links = FakeLinkRepo([10, 30])
        factory = _make_uow_factory(
            search_index=FakeSearchIndex(fts_hits),
            links=links,
        )
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", has_link=True)

        assert {int(h.video_id) for h in result.hits} == {10, 30}

    def test_has_link_no_query_synthesises_results(self) -> None:
        """has_link=True sans query → synthèse SearchResult par video matchant."""
        links = FakeLinkRepo([7])
        videos = FakeVideoRepo([_make_video(7, "My video with links")])
        factory = _make_uow_factory(links=links, videos=videos)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", has_link=True)

        assert len(result.hits) == 1
        hit = result.hits[0]
        assert int(hit.video_id) == 7
        assert hit.source == "video"
        assert hit.rank == 1.0


# ---------------------------------------------------------------------------
# Test 6 — music_track facet
# ---------------------------------------------------------------------------


class TestMusicTrackFacet:
    def test_music_track_exact_match(self) -> None:
        """execute('', music_track='Original sound') filtre par music_track exact."""
        videos = FakeVideoRepo([
            _make_video(1, music_track="Original sound"),
            _make_video(2, music_track="Other song"),
            _make_video(3, music_track="Original sound"),
        ])
        factory = _make_uow_factory(videos=videos)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", music_track="Original sound")

        assert {int(h.video_id) for h in result.hits} == {1, 3}

    def test_music_track_no_match_returns_empty(self) -> None:
        """Facette music_track sans correspondance → liste vide."""
        videos = FakeVideoRepo([_make_video(1, music_track="Pop song")])
        factory = _make_uow_factory(videos=videos)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", music_track="Nonexistent")

        assert result.hits == ()


# ---------------------------------------------------------------------------
# Test 7 — AND implicite (2 facettes)
# ---------------------------------------------------------------------------


class TestAndImplicite:
    def test_hashtag_and_mention_intersection(self) -> None:
        """execute('', hashtag='coding', mention='@alice') → intersection."""
        hashtags = FakeHashtagRepo({"coding": [1, 2, 3]})
        mentions = FakeMentionRepo({"alice": [2, 3, 4]})
        videos = FakeVideoRepo([_make_video(2), _make_video(3)])
        factory = _make_uow_factory(hashtags=hashtags, mentions=mentions, videos=videos)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", hashtag="coding", mention="@alice")

        assert {int(h.video_id) for h in result.hits} == {2, 3}

    def test_and_with_fts_query(self) -> None:
        """execute('tutorial', hashtag='coding') → FTS5 ∩ hashtag."""
        fts_hits = [_make_hit(1), _make_hit(2), _make_hit(3)]
        hashtags = FakeHashtagRepo({"coding": [2, 3]})
        factory = _make_uow_factory(
            search_index=FakeSearchIndex(fts_hits),
            hashtags=hashtags,
        )
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("tutorial", hashtag="coding")

        assert {int(h.video_id) for h in result.hits} == {2, 3}


# ---------------------------------------------------------------------------
# Test 9 — query vide + facette → synthèse SearchResult
# ---------------------------------------------------------------------------


class TestSyntheticResults:
    def test_empty_query_with_facet_does_not_call_search_index(self) -> None:
        """Quand query est vide, le search_index ne doit pas être appelé."""
        index = FakeSearchIndex([_make_hit(1)])  # would return hit if called
        links = FakeLinkRepo([99])
        videos = FakeVideoRepo([_make_video(99)])
        factory = _make_uow_factory(search_index=index, links=links, videos=videos)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", has_link=True)

        # search_index.search must NOT have been called
        assert index.last_query is None
        assert len(result.hits) == 1

    def test_synthetic_result_uses_title_as_snippet(self) -> None:
        """Le snippet synthétique = titre de la vidéo."""
        links = FakeLinkRepo([5])
        videos = FakeVideoRepo([_make_video(5, "My Amazing Video")])
        factory = _make_uow_factory(links=links, videos=videos)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", has_link=True)

        assert result.hits[0].snippet == "My Amazing Video"


# ---------------------------------------------------------------------------
# Test 10 — facette vide → liste vide
# ---------------------------------------------------------------------------


class TestEmptyFacet:
    def test_facet_with_no_matches_returns_empty(self) -> None:
        """Facette qui retourne [] → SearchResult list vide."""
        hashtags = FakeHashtagRepo({"coding": []})
        factory = _make_uow_factory(hashtags=hashtags)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("anything", hashtag="coding")

        assert result.hits == ()

    def test_no_query_no_facet_returns_empty(self) -> None:
        """Aucune query, aucune facette → liste vide (comportement attendu)."""
        factory = _make_uow_factory()
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("")

        assert result.hits == ()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def test_result_is_frozen_dataclass() -> None:
    """SearchLibraryResult est un frozen dataclass — immutabilité."""
    import dataclasses

    result = SearchLibraryResult(query="x", hits=())
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
        result.query = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# M008 — on_screen_text facet
# ---------------------------------------------------------------------------


class TestOnScreenTextFacet:
    def test_on_screen_text_none_does_not_change_behaviour(self) -> None:
        """on_screen_text=None (default) → comportement inchangé par rapport à M007."""
        hits = [_make_hit(1), _make_hit(2)]
        factory = _make_uow_factory(search_index=FakeSearchIndex(hits))
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("cooking", on_screen_text=None)

        assert len(result.hits) == 2

    def test_on_screen_text_only_returns_matched_video_ids(self) -> None:
        """on_screen_text='promo' sans query → synthèse pour les video_ids matchant."""
        frame_texts = FakeFrameTextRepo({"promo": [1, 2]})
        videos = FakeVideoRepo([_make_video(1, "Video 1"), _make_video(2, "Video 2")])
        factory = _make_uow_factory(frame_texts=frame_texts, videos=videos)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", on_screen_text="promo")

        assert {int(h.video_id) for h in result.hits} == {1, 2}
        # Synthèse SearchResult → source="video"
        assert all(h.source == "video" for h in result.hits)

    def test_on_screen_text_empty_string_returns_no_hits(self) -> None:
        """on_screen_text='   ' (whitespace) → aucun résultat."""
        frame_texts = FakeFrameTextRepo({"promo": [1, 2]})
        videos = FakeVideoRepo([_make_video(1), _make_video(2)])
        factory = _make_uow_factory(frame_texts=frame_texts, videos=videos)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", on_screen_text="   ")

        assert result.hits == ()

    def test_on_screen_text_intersects_with_hashtag(self) -> None:
        """on_screen_text ∩ hashtag → AND implicite."""
        frame_texts = FakeFrameTextRepo({"promo": [1, 2, 3]})
        hashtags = FakeHashtagRepo({"cooking": [2, 3, 4]})
        videos = FakeVideoRepo([_make_video(2), _make_video(3)])
        factory = _make_uow_factory(
            frame_texts=frame_texts, hashtags=hashtags, videos=videos
        )
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("", on_screen_text="promo", hashtag="cooking")

        assert {int(h.video_id) for h in result.hits} == {2, 3}

    def test_on_screen_text_with_fts_query_filters_hits(self) -> None:
        """execute('tutorial', on_screen_text='promo') → FTS5 ∩ on_screen_text."""
        fts_hits = [_make_hit(1), _make_hit(2), _make_hit(3)]
        frame_texts = FakeFrameTextRepo({"promo": [2, 3]})
        factory = _make_uow_factory(
            search_index=FakeSearchIndex(fts_hits),
            frame_texts=frame_texts,
        )
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("tutorial", on_screen_text="promo")

        assert {int(h.video_id) for h in result.hits} == {2, 3}

    def test_on_screen_text_no_match_returns_empty(self) -> None:
        """on_screen_text sans correspondance → liste vide."""
        frame_texts = FakeFrameTextRepo({})  # query "promo" → []
        factory = _make_uow_factory(frame_texts=frame_texts)
        uc = SearchLibraryUseCase(unit_of_work_factory=factory)

        result = uc.execute("anything", on_screen_text="promo")

        assert result.hits == ()
