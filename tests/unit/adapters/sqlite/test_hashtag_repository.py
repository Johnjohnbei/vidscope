"""Tests for :class:`HashtagRepositorySQLite`."""

from __future__ import annotations

from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.hashtag_repository import HashtagRepositorySQLite
from vidscope.adapters.sqlite.video_repository import VideoRepositorySQLite
from vidscope.domain import Platform, PlatformId, Video, VideoId


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


class TestHashtagRepositoryReplaceAndList:
    def test_replace_inserts_tags_and_list_returns_them(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = HashtagRepositorySQLite(conn)
            repo.replace_for_video(vid, ["cooking", "recipes"])
            tags = repo.list_for_video(vid)
        assert len(tags) == 2
        assert tags[0].tag == "cooking"
        assert tags[1].tag == "recipes"

    def test_replace_canonicalises_tag_uppercase_hash(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = HashtagRepositorySQLite(conn)
            repo.replace_for_video(vid, ["#Coding"])
            tags = repo.list_for_video(vid)
        assert len(tags) == 1
        assert tags[0].tag == "coding"

    def test_replace_is_idempotent_second_call_overwrites(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = HashtagRepositorySQLite(conn)
            repo.replace_for_video(vid, ["a"])
            repo.replace_for_video(vid, ["b"])
            tags = repo.list_for_video(vid)
        assert len(tags) == 1
        assert tags[0].tag == "b"

    def test_replace_with_empty_list_removes_all_tags(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = HashtagRepositorySQLite(conn)
            repo.replace_for_video(vid, ["cooking"])
            repo.replace_for_video(vid, [])
            tags = repo.list_for_video(vid)
        assert tags == []

    def test_list_for_nonexistent_video_returns_empty(
        self, engine: Engine
    ) -> None:
        with engine.begin() as conn:
            repo = HashtagRepositorySQLite(conn)
            tags = repo.list_for_video(VideoId(9999))
        assert tags == []

    def test_replace_deduplicates_tags_within_call(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = HashtagRepositorySQLite(conn)
            repo.replace_for_video(vid, ["cooking", "cooking", "#cooking"])
            tags = repo.list_for_video(vid)
        assert len(tags) == 1
        assert tags[0].tag == "cooking"


class TestHashtagRepositoryCascadeAndFind:
    def test_cascade_delete_removes_hashtags(self, engine: Engine) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = HashtagRepositorySQLite(conn)
            repo.replace_for_video(vid, ["cooking"])

        # Delete the parent video row — FK CASCADE should remove hashtags.
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM videos WHERE id = {int(vid)}"))

        with engine.begin() as conn:
            repo = HashtagRepositorySQLite(conn)
            tags = repo.list_for_video(vid)
        assert tags == []

    def test_find_video_ids_by_tag_returns_matching_video(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine, "vid-find-1")
        with engine.begin() as conn:
            repo = HashtagRepositorySQLite(conn)
            repo.replace_for_video(vid, ["cooking"])
            result = repo.find_video_ids_by_tag("cooking")
        assert vid in result

    def test_find_video_ids_by_tag_canonicalises_input(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine, "vid-find-2")
        with engine.begin() as conn:
            repo = HashtagRepositorySQLite(conn)
            repo.replace_for_video(vid, ["cooking"])
            result_lower = repo.find_video_ids_by_tag("cooking")
            result_hash = repo.find_video_ids_by_tag("#Cooking")
        assert result_lower == result_hash
        assert vid in result_lower
