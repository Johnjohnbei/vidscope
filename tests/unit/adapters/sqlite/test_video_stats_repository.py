"""Unit tests for VideoStatsRepositorySQLite — append-only invariant + idempotence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from vidscope.adapters.sqlite.video_repository import VideoRepositorySQLite
from vidscope.adapters.sqlite.video_stats_repository import VideoStatsRepositorySQLite
from vidscope.domain import Platform, PlatformId, Video, VideoId, VideoStats


def _persist_video(engine: Engine) -> VideoId:
    """Helper: insert a video and return its DB id."""
    with engine.begin() as conn:
        repo = VideoRepositorySQLite(conn)
        persisted = repo.upsert_by_platform_id(
            Video(platform=Platform.YOUTUBE, platform_id=PlatformId("abc"), url="https://x.y/abc")
        )
        assert persisted.id is not None
        return persisted.id


class TestAppend:
    def test_append_persists_and_returns_id(self, engine: Engine) -> None:
        """Happy path: appending a stats row returns entity with id populated."""
        vid = _persist_video(engine)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            stats = VideoStats(
                video_id=vid,
                captured_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                view_count=100,
                like_count=10,
            )
            result = repo.append(stats)
            assert result.id is not None
            assert result.view_count == 100

    def test_append_is_idempotent_on_same_captured_at(self, engine: Engine) -> None:
        """D-01: UNIQUE(video_id, captured_at) at second resolution — no duplicate."""
        vid = _persist_video(engine)
        t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            repo.append(VideoStats(video_id=vid, captured_at=t, view_count=100))
            repo.append(VideoStats(video_id=vid, captured_at=t, view_count=999))
            rows = repo.list_for_video(vid)
            assert len(rows) == 1

    def test_append_does_not_update_on_conflict(self, engine: Engine) -> None:
        """Append-only (D031): second append with same key does NOT mutate existing row."""
        vid = _persist_video(engine)
        t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            repo.append(VideoStats(video_id=vid, captured_at=t, view_count=100, like_count=5))
            repo.append(VideoStats(video_id=vid, captured_at=t, view_count=999, like_count=888))
            latest = repo.latest_for_video(vid)
            assert latest is not None
            assert latest.view_count == 100  # original preserved
            assert latest.like_count == 5

    def test_different_captured_at_creates_separate_rows(self, engine: Engine) -> None:
        """Two probes at different times create two rows."""
        vid = _persist_video(engine)
        base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            repo.append(VideoStats(video_id=vid, captured_at=base, view_count=100))
            repo.append(VideoStats(video_id=vid, captured_at=base + timedelta(hours=1), view_count=200))
            rows = repo.list_for_video(vid)
            assert len(rows) == 2


class TestListForVideo:
    def test_orders_by_captured_at_asc(self, engine: Engine) -> None:
        """list_for_video returns rows in ascending captured_at order."""
        vid = _persist_video(engine)
        base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            for i in [3, 1, 2]:
                repo.append(VideoStats(
                    video_id=vid,
                    captured_at=base + timedelta(hours=i),
                    view_count=i * 100,
                ))
            rows = repo.list_for_video(vid)
            assert [r.view_count for r in rows] == [100, 200, 300]

    def test_limit_is_respected(self, engine: Engine) -> None:
        """list_for_video respects the limit kwarg (T-INPUT-01)."""
        vid = _persist_video(engine)
        base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            for i in range(5):
                repo.append(VideoStats(
                    video_id=vid,
                    captured_at=base + timedelta(hours=i),
                    view_count=i * 100,
                ))
            rows = repo.list_for_video(vid, limit=3)
            assert len(rows) == 3

    def test_empty_for_unknown_video(self, engine: Engine) -> None:
        """No rows for a video that has no stats."""
        vid = _persist_video(engine)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            assert repo.list_for_video(vid) == []


class TestLatestForVideo:
    def test_returns_most_recent(self, engine: Engine) -> None:
        """latest_for_video returns the snapshot with the highest captured_at."""
        vid = _persist_video(engine)
        base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            repo.append(VideoStats(video_id=vid, captured_at=base, view_count=100))
            repo.append(VideoStats(video_id=vid, captured_at=base + timedelta(hours=1), view_count=200))
            latest = repo.latest_for_video(vid)
            assert latest is not None
            assert latest.view_count == 200

    def test_returns_none_when_empty(self, engine: Engine) -> None:
        """latest_for_video returns None when no snapshots exist."""
        vid = _persist_video(engine)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            assert repo.latest_for_video(vid) is None


class TestHasAnyForVideo:
    def test_false_before_any_append(self, engine: Engine) -> None:
        vid = _persist_video(engine)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            assert repo.has_any_for_video(vid) is False

    def test_true_after_append(self, engine: Engine) -> None:
        vid = _persist_video(engine)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            repo.append(VideoStats(video_id=vid, captured_at=datetime(2026, 1, 1, tzinfo=UTC)))
            assert repo.has_any_for_video(vid) is True


class TestListVideosWithMinSnapshots:
    def test_excludes_videos_below_min(self, engine: Engine) -> None:
        """A video with only 1 snapshot is excluded when min_snapshots=2."""
        vid = _persist_video(engine)
        base = datetime(2026, 1, 1, tzinfo=UTC)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            repo.append(VideoStats(video_id=vid, captured_at=base))
            assert repo.list_videos_with_min_snapshots(2) == []

    def test_includes_videos_at_min(self, engine: Engine) -> None:
        """A video with exactly min_snapshots is included."""
        vid = _persist_video(engine)
        base = datetime(2026, 1, 1, tzinfo=UTC)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            repo.append(VideoStats(video_id=vid, captured_at=base))
            repo.append(VideoStats(video_id=vid, captured_at=base + timedelta(hours=1)))
            ids = repo.list_videos_with_min_snapshots(2)
            assert vid in ids

    def test_limit_respected(self, engine: Engine) -> None:
        """list_videos_with_min_snapshots respects limit (T-INPUT-01)."""
        # Create 3 videos each with 2 snapshots
        vids = []
        for i in range(3):
            with engine.begin() as conn:
                repo_v = VideoRepositorySQLite(conn)
                v = repo_v.upsert_by_platform_id(
                    Video(
                        platform=Platform.YOUTUBE,
                        platform_id=PlatformId(f"vid{i}"),
                        url=f"https://x.y/vid{i}",
                    )
                )
                assert v.id is not None
                vids.append(v.id)

        base = datetime(2026, 1, 1, tzinfo=UTC)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            for vid in vids:
                repo.append(VideoStats(video_id=vid, captured_at=base))
                repo.append(VideoStats(video_id=vid, captured_at=base + timedelta(hours=1)))
            ids = repo.list_videos_with_min_snapshots(2, limit=2)
            assert len(ids) <= 2


class TestNoneCountersRoundtrip:
    def test_none_not_coerced_to_zero(self, engine: Engine) -> None:
        """D-03: None MUST NOT become 0 through persistence roundtrip."""
        vid = _persist_video(engine)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            repo.append(VideoStats(
                video_id=vid,
                captured_at=datetime(2026, 1, 1, tzinfo=UTC),
                view_count=1000,
                like_count=None,
                repost_count=None,
                comment_count=None,
                save_count=None,
            ))
            latest = repo.latest_for_video(vid)
            assert latest is not None
            assert latest.like_count is None
            assert latest.repost_count is None
            assert latest.comment_count is None
            assert latest.save_count is None

    def test_captured_at_is_utc_aware_on_roundtrip(self, engine: Engine) -> None:
        """captured_at must be UTC-aware after roundtrip (D-01)."""
        vid = _persist_video(engine)
        t = datetime(2026, 6, 15, 10, 30, 0, tzinfo=UTC)
        with engine.begin() as conn:
            repo = VideoStatsRepositorySQLite(conn)
            repo.append(VideoStats(video_id=vid, captured_at=t, view_count=500))
            latest = repo.latest_for_video(vid)
            assert latest is not None
            assert latest.captured_at.tzinfo is not None
