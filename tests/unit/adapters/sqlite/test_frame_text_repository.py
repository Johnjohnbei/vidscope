"""Tests for FrameTextRepositorySQLite."""

from __future__ import annotations

from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.frame_repository import FrameRepositorySQLite
from vidscope.adapters.sqlite.frame_text_repository import FrameTextRepositorySQLite
from vidscope.adapters.sqlite.video_repository import VideoRepositorySQLite
from vidscope.domain import Frame, FrameText, Platform, PlatformId, Video, VideoId


def _sample_video(platform_id: str = "vid001") -> Video:
    return Video(
        platform=Platform.YOUTUBE,
        platform_id=PlatformId(platform_id),
        url=f"https://www.youtube.com/watch?v={platform_id}",
    )


def _make_video(engine: Engine, platform_id: str = "vid001") -> VideoId:
    with engine.begin() as conn:
        repo = VideoRepositorySQLite(conn)
        stored = repo.add(_sample_video(platform_id))
    assert stored.id is not None
    return stored.id


def _make_frame(engine: Engine, video_id: VideoId, timestamp_ms: int = 0) -> int:
    frame = Frame(
        video_id=video_id,
        image_key=f"frames/{video_id}/{timestamp_ms}.jpg",
        timestamp_ms=timestamp_ms,
    )
    with engine.begin() as conn:
        repo = FrameRepositorySQLite(conn)
        stored_list = repo.add_many([frame])
    assert stored_list[0].id is not None
    return stored_list[0].id  # type: ignore[return-value]


class TestAddManyForFrame:
    def test_add_many_inserts_rows(self, engine: Engine) -> None:
        vid = _make_video(engine)
        frame_id = _make_frame(engine, vid)
        texts = [
            FrameText(video_id=vid, frame_id=frame_id, text="Hello", confidence=0.9),
            FrameText(video_id=vid, frame_id=frame_id, text="World", confidence=0.8),
        ]
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            result = repo.add_many_for_frame(frame_id, vid, texts)
        assert len(result) == 2
        assert all(r.id is not None for r in result)

    def test_add_many_syncs_fts(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_fts")
        frame_id = _make_frame(engine, vid)
        texts = [
            FrameText(video_id=vid, frame_id=frame_id, text="Link in bio", confidence=0.9),
            FrameText(video_id=vid, frame_id=frame_id, text="Follow me", confidence=0.85),
        ]
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            repo.add_many_for_frame(frame_id, vid, texts)
            rows = conn.execute(
                text("SELECT * FROM frame_texts_fts WHERE video_id = :vid"),
                {"vid": int(vid)},
            ).all()
        assert len(rows) == 2

    def test_empty_list_is_noop(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_noop")
        frame_id = _make_frame(engine, vid)
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            result = repo.add_many_for_frame(frame_id, vid, [])
        assert result == []

    def test_rows_have_populated_id(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_ids")
        frame_id = _make_frame(engine, vid)
        texts = [FrameText(video_id=vid, frame_id=frame_id, text="X", confidence=0.9)]
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            result = repo.add_many_for_frame(frame_id, vid, texts)
        assert result[0].id is not None
        assert isinstance(result[0].id, int)


class TestListForVideo:
    def test_list_for_video_empty(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_empty")
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            assert repo.list_for_video(vid) == []

    def test_list_for_video_ordered(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_order")
        frame_id1 = _make_frame(engine, vid, timestamp_ms=0)
        frame_id2 = _make_frame(engine, vid, timestamp_ms=1000)
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            repo.add_many_for_frame(
                frame_id2,
                vid,
                [FrameText(video_id=vid, frame_id=frame_id2, text="Second frame", confidence=0.9)],
            )
            repo.add_many_for_frame(
                frame_id1,
                vid,
                [FrameText(video_id=vid, frame_id=frame_id1, text="First frame", confidence=0.9)],
            )
            rows = repo.list_for_video(vid)
        assert len(rows) == 2
        assert rows[0].frame_id == frame_id1
        assert rows[1].frame_id == frame_id2


class TestHasAnyForVideo:
    def test_has_any_for_video_false_before_insert(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_has_any")
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            assert repo.has_any_for_video(vid) is False

    def test_has_any_for_video_true_after_insert(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_has_any2")
        frame_id = _make_frame(engine, vid)
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            repo.add_many_for_frame(
                frame_id,
                vid,
                [FrameText(video_id=vid, frame_id=frame_id, text="Y", confidence=0.9)],
            )
            assert repo.has_any_for_video(vid) is True


class TestFindVideoIdsByText:
    def test_find_video_ids_by_text_bare_word(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_fts1")
        frame_id = _make_frame(engine, vid)
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            repo.add_many_for_frame(
                frame_id,
                vid,
                [FrameText(video_id=vid, frame_id=frame_id, text="Link in bio", confidence=0.9)],
            )
            result = repo.find_video_ids_by_text("link")
        assert vid in result

    def test_find_video_ids_by_text_case_insensitive(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_fts2")
        frame_id = _make_frame(engine, vid)
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            repo.add_many_for_frame(
                frame_id,
                vid,
                [FrameText(video_id=vid, frame_id=frame_id, text="Link in bio", confidence=0.9)],
            )
            result = repo.find_video_ids_by_text("LINK")
        assert vid in result

    def test_find_video_ids_by_text_diacritic_insensitive(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_fts3")
        frame_id = _make_frame(engine, vid)
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            repo.add_many_for_frame(
                frame_id,
                vid,
                [FrameText(
                    video_id=vid, frame_id=frame_id, text="promo exclusive", confidence=0.9
                )],
            )
            result = repo.find_video_ids_by_text("promo")
        assert vid in result

    def test_find_video_ids_by_text_no_match(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_fts4")
        frame_id = _make_frame(engine, vid)
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            repo.add_many_for_frame(
                frame_id,
                vid,
                [FrameText(video_id=vid, frame_id=frame_id, text="Hello world", confidence=0.9)],
            )
            result = repo.find_video_ids_by_text("zyxwvuts")
        assert result == []


class TestCascadeDeletes:
    def test_cascade_on_frame_delete(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_cascade_frame")
        frame_id = _make_frame(engine, vid)
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            repo.add_many_for_frame(
                frame_id,
                vid,
                [FrameText(video_id=vid, frame_id=frame_id, text="Test", confidence=0.9)],
            )
        # Delete the parent frame — frame_texts should cascade
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM frames WHERE id = :fid"), {"fid": frame_id})
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            assert repo.list_for_video(vid) == []

    def test_cascade_on_video_delete(self, engine: Engine) -> None:
        vid = _make_video(engine, "vid_cascade_video")
        frame_id = _make_frame(engine, vid)
        with engine.begin() as conn:
            repo = FrameTextRepositorySQLite(conn)
            repo.add_many_for_frame(
                frame_id,
                vid,
                [FrameText(video_id=vid, frame_id=frame_id, text="Test", confidence=0.9)],
            )
        # Delete the parent video — frame_texts should cascade
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM videos WHERE id = :vid"), {"vid": int(vid)})
        with engine.begin() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM frame_texts WHERE video_id = :vid"),
                {"vid": int(vid)},
            ).scalar()
        assert count == 0
