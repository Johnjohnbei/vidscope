"""Tests for :class:`MentionRepositorySQLite`."""

from __future__ import annotations

from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.mention_repository import MentionRepositorySQLite
from vidscope.adapters.sqlite.video_repository import VideoRepositorySQLite
from vidscope.domain import Mention, Platform, PlatformId, Video, VideoId


def _sample_video(platform_id: str = "vidm001") -> Video:
    return Video(
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(platform_id),
        url=f"https://www.youtube.com/watch?v={platform_id}",
    )


def _make_video(engine: Engine, platform_id: str = "vidm001") -> VideoId:
    """Insert a video row and return its id."""
    with engine.begin() as conn:
        repo = VideoRepositorySQLite(conn)
        stored = repo.add(_sample_video(platform_id))
    assert stored.id is not None
    return stored.id


def _mention(handle: str, platform: Platform | None = None, vid: VideoId | None = None) -> Mention:
    return Mention(
        video_id=vid or VideoId(1),
        handle=handle,
        platform=platform,
    )


class TestMentionRepositoryReplaceAndList:
    def test_replace_inserts_mentions_and_list_returns_them(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine)
        m1 = _mention("alice", vid=vid)
        m2 = _mention("bob", vid=vid)
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            repo.replace_for_video(vid, [m1, m2])
            mentions = repo.list_for_video(vid)
        assert len(mentions) == 2
        assert mentions[0].handle == "alice"
        assert mentions[1].handle == "bob"

    def test_replace_canonicalises_handle_uppercase_at(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            repo.replace_for_video(vid, [_mention("@Alice", vid=vid)])
            mentions = repo.list_for_video(vid)
        assert len(mentions) == 1
        assert mentions[0].handle == "alice"

    def test_replace_is_idempotent_second_call_overwrites(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            repo.replace_for_video(vid, [_mention("alice", vid=vid)])
            repo.replace_for_video(vid, [_mention("bob", vid=vid)])
            mentions = repo.list_for_video(vid)
        assert len(mentions) == 1
        assert mentions[0].handle == "bob"

    def test_replace_with_empty_list_removes_all_mentions(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            repo.replace_for_video(vid, [_mention("alice", vid=vid)])
            repo.replace_for_video(vid, [])
            mentions = repo.list_for_video(vid)
        assert mentions == []

    def test_list_for_nonexistent_video_returns_empty(
        self, engine: Engine
    ) -> None:
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            mentions = repo.list_for_video(VideoId(9999))
        assert mentions == []

    def test_platform_none_round_trips(self, engine: Engine) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            repo.replace_for_video(vid, [_mention("alice", platform=None, vid=vid)])
            mentions = repo.list_for_video(vid)
        assert mentions[0].platform is None

    def test_platform_tiktok_round_trips(self, engine: Engine) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            repo.replace_for_video(
                vid, [_mention("alice", platform=Platform.TIKTOK, vid=vid)]
            )
            mentions = repo.list_for_video(vid)
        assert mentions[0].platform is Platform.TIKTOK

    def test_replace_deduplicates_handle_platform_pair(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine)
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            repo.replace_for_video(
                vid,
                [
                    _mention("alice", vid=vid),
                    _mention("@alice", vid=vid),  # same after canonicalisation
                ],
            )
            mentions = repo.list_for_video(vid)
        assert len(mentions) == 1
        assert mentions[0].handle == "alice"


class TestMentionRepositoryCascadeAndFind:
    def test_cascade_delete_removes_mentions(self, engine: Engine) -> None:
        vid = _make_video(engine, "vidm-cascade")
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            repo.replace_for_video(vid, [_mention("alice", vid=vid)])

        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM videos WHERE id = {int(vid)}"))

        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            mentions = repo.list_for_video(vid)
        assert mentions == []

    def test_find_video_ids_by_handle_returns_matching(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine, "vidm-find-1")
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            repo.replace_for_video(vid, [_mention("alice", vid=vid)])
            result = repo.find_video_ids_by_handle("alice")
        assert vid in result

    def test_find_video_ids_by_handle_canonicalises_input(
        self, engine: Engine
    ) -> None:
        vid = _make_video(engine, "vidm-find-2")
        with engine.begin() as conn:
            repo = MentionRepositorySQLite(conn)
            repo.replace_for_video(vid, [_mention("alice", vid=vid)])
            result_lower = repo.find_video_ids_by_handle("alice")
            result_at = repo.find_video_ids_by_handle("@Alice")
        assert result_lower == result_at
        assert vid in result_lower
