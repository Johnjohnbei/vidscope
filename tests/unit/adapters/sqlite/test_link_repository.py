"""Tests for :class:`LinkRepositorySQLite`."""

from __future__ import annotations

from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.link_repository import LinkRepositorySQLite
from vidscope.adapters.sqlite.video_repository import VideoRepositorySQLite
from vidscope.domain import Link, Platform, PlatformId, Video, VideoId


def _sample_video(platform_id: str = "vid001") -> Video:
    return Video(
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(platform_id),
        url=f"https://www.youtube.com/watch?v={platform_id}",
    )


def _make_video(engine: Engine, platform_id: str = "vid001") -> VideoId:
    """Insert a video row and return its id."""
    with engine.begin() as conn:
        repo = VideoRepositorySQLite(conn)
        stored = repo.add(_sample_video(platform_id))
    assert stored.id is not None
    return stored.id


def _link(
    video_id: VideoId,
    url: str = "https://example.com",
    normalized_url: str = "https://example.com",
    source: str = "description",
    position_ms: int | None = None,
) -> Link:
    return Link(
        video_id=video_id,
        url=url,
        normalized_url=normalized_url,
        source=source,
        position_ms=position_ms,
    )


class TestLinkRepositoryAddAndList:
    def test_add_one_link_and_list_returns_it_with_id(
        self, engine: Engine
    ) -> None:
        """Test 1: add_many_for_video inserts 1 row; list_for_video returns it with id populated."""
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            result = repo.add_many_for_video(
                vid,
                [_link(vid, url="https://a.com", normalized_url="https://a.com")],
            )
        assert len(result) == 1
        assert result[0].id is not None
        assert result[0].url == "https://a.com"
        assert result[0].normalized_url == "https://a.com"
        assert result[0].source == "description"

    def test_dedup_within_same_call_by_normalized_url_and_source(
        self, engine: Engine
    ) -> None:
        """Test 2: two identical (normalized_url, source) pairs → only 1 row inserted."""
        vid = _make_video(engine, "vid002")
        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            result = repo.add_many_for_video(
                vid,
                [
                    _link(vid, url="https://a.com", normalized_url="https://a.com"),
                    _link(vid, url="https://a.com", normalized_url="https://a.com"),
                ],
            )
        assert len(result) == 1

    def test_same_url_different_sources_creates_two_rows(
        self, engine: Engine
    ) -> None:
        """Test 3: same normalized_url via description + transcript = 2 distinct rows."""
        vid = _make_video(engine, "vid003")
        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            result = repo.add_many_for_video(
                vid,
                [
                    _link(
                        vid,
                        url="https://a.com",
                        normalized_url="https://a.com",
                        source="description",
                    ),
                    _link(
                        vid,
                        url="https://a.com",
                        normalized_url="https://a.com",
                        source="transcript",
                    ),
                ],
            )
        assert len(result) == 2
        sources = {ln.source for ln in result}
        assert sources == {"description", "transcript"}

    def test_list_for_video_filters_by_source(self, engine: Engine) -> None:
        """Test 4: list_for_video(source="description") only returns description rows."""
        vid = _make_video(engine, "vid004")
        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            repo.add_many_for_video(
                vid,
                [
                    _link(
                        vid,
                        url="https://a.com",
                        normalized_url="https://a.com",
                        source="description",
                    ),
                    _link(
                        vid,
                        url="https://b.com",
                        normalized_url="https://b.com",
                        source="transcript",
                    ),
                ],
            )
            desc_links = repo.list_for_video(vid, source="description")
            transcript_links = repo.list_for_video(vid, source="transcript")
        assert len(desc_links) == 1
        assert desc_links[0].source == "description"
        assert len(transcript_links) == 1
        assert transcript_links[0].source == "transcript"

    def test_list_for_video_without_filter_returns_all_ordered_by_id(
        self, engine: Engine
    ) -> None:
        """Test 5: list_for_video (no filter) returns all in insertion order (id asc)."""
        vid = _make_video(engine, "vid005")
        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            repo.add_many_for_video(
                vid,
                [
                    _link(
                        vid,
                        url="https://first.com",
                        normalized_url="https://first.com",
                        source="description",
                    ),
                    _link(
                        vid,
                        url="https://second.com",
                        normalized_url="https://second.com",
                        source="description",
                    ),
                ],
            )
            all_links = repo.list_for_video(vid)
        assert len(all_links) == 2
        assert all_links[0].url == "https://first.com"
        assert all_links[1].url == "https://second.com"
        assert all_links[0].id < all_links[1].id  # type: ignore[operator]

    def test_has_any_for_video_true_after_insert_false_without(
        self, engine: Engine
    ) -> None:
        """Test 6: has_any_for_video returns True after insert, False for video with none."""
        vid_with = _make_video(engine, "vid006a")
        vid_without = _make_video(engine, "vid006b")
        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            repo.add_many_for_video(
                vid_with,
                [_link(vid_with)],
            )
            assert repo.has_any_for_video(vid_with) is True
            assert repo.has_any_for_video(vid_without) is False

    def test_cascade_delete_removes_links_when_video_deleted(
        self, engine: Engine
    ) -> None:
        """Test 7: deleting the parent video row removes all child links (ON DELETE CASCADE)."""
        vid = _make_video(engine, "vid007")
        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            repo.add_many_for_video(vid, [_link(vid)])

        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM videos WHERE id = {int(vid)}"))

        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            links = repo.list_for_video(vid)
        assert links == []

    def test_position_ms_nullable_round_trip(self, engine: Engine) -> None:
        """Test 8: position_ms None and positive integer both round-trip correctly."""
        vid = _make_video(engine, "vid008")
        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            result = repo.add_many_for_video(
                vid,
                [
                    _link(
                        vid,
                        url="https://a.com",
                        normalized_url="https://a.com",
                        source="description",
                        position_ms=None,
                    ),
                    _link(
                        vid,
                        url="https://b.com",
                        normalized_url="https://b.com",
                        source="transcript",
                        position_ms=42_000,
                    ),
                ],
            )
        positions = {ln.normalized_url: ln.position_ms for ln in result}
        assert positions["https://a.com"] is None
        assert positions["https://b.com"] == 42_000

    def test_find_video_ids_with_any_link_returns_correct_ids(
        self, engine: Engine
    ) -> None:
        """Test 9: find_video_ids_with_any_link(limit=10) returns ids with ≥1 link."""
        vid_a = _make_video(engine, "vid009a")
        vid_b = _make_video(engine, "vid009b")
        vid_empty = _make_video(engine, "vid009c")

        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            repo.add_many_for_video(vid_a, [_link(vid_a)])
            repo.add_many_for_video(vid_b, [_link(vid_b, normalized_url="https://b.com", url="https://b.com")])
            result = repo.find_video_ids_with_any_link(limit=10)

        assert vid_a in result
        assert vid_b in result
        assert vid_empty not in result

    def test_add_many_empty_list_is_noop(self, engine: Engine) -> None:
        """Test 10: add_many_for_video(vid, []) is a no-op (returns [])."""
        vid = _make_video(engine, "vid010")
        with engine.begin() as conn:
            repo = LinkRepositorySQLite(conn)
            result = repo.add_many_for_video(vid, [])
            links = repo.list_for_video(vid)
        assert result == []
        assert links == []
