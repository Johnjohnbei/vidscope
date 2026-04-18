"""Unit tests for VideoTrackingRepositorySQLite (M011/S01/R056)."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.video_tracking_repository import (
    VideoTrackingRepositorySQLite,
)
from vidscope.domain import TrackingStatus, VideoId, VideoTracking


def _insert_video(engine: Engine, platform_id: str) -> int:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO videos (platform, platform_id, url, created_at) "
                "VALUES (:p, :pid, :u, :c)"
            ),
            {
                "p": "youtube",
                "pid": platform_id,
                "u": f"https://y.be/{platform_id}",
                "c": datetime.now(UTC),
            },
        )
        return int(
            conn.execute(
                text("SELECT id FROM videos WHERE platform_id=:pid"),
                {"pid": platform_id},
            ).scalar()
        )


class TestMigration:
    def test_table_exists_after_init_db(self, engine: Engine) -> None:
        with engine.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            }
        assert "video_tracking" in names

    def test_table_has_expected_columns(self, engine: Engine) -> None:
        with engine.connect() as conn:
            cols = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(video_tracking)"))
            }
        assert {
            "id", "video_id", "status", "starred", "notes",
            "created_at", "updated_at",
        }.issubset(cols)

    def test_indexes_exist(self, engine: Engine) -> None:
        with engine.connect() as conn:
            idx_rows = list(conn.execute(text("PRAGMA index_list('video_tracking')")))
        idx_names = {row[1] for row in idx_rows}
        assert "idx_video_tracking_status" in idx_names
        assert "idx_video_tracking_starred" in idx_names

    def test_unique_video_id_enforced(self, engine: Engine) -> None:
        # The UNIQUE constraint exists — upsert relies on it.
        # SQLite may name the auto-index "sqlite_autoindex_video_tracking_1"
        # or use the explicit constraint name — both are acceptable.
        with engine.connect() as conn:
            idx_rows = list(conn.execute(text("PRAGMA index_list('video_tracking')")))
        # row[2] == 1 means unique in PRAGMA index_list
        has_unique = any(row[2] == 1 for row in idx_rows)
        assert has_unique, f"UNIQUE video_id constraint missing: indexes={idx_rows}"

    def test_ensure_table_idempotent(self, engine: Engine) -> None:
        from vidscope.adapters.sqlite.schema import _ensure_video_tracking_table

        with engine.begin() as conn:
            _ensure_video_tracking_table(conn)
            _ensure_video_tracking_table(conn)
        # No error = idempotent


class TestUpsertInsert:
    def test_upsert_creates_row_with_id_populated(self, engine: Engine) -> None:
        vid = _insert_video(engine, "tup1")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            tracking = VideoTracking(
                video_id=VideoId(vid),
                status=TrackingStatus.SAVED,
                starred=True,
                notes="cool hook",
            )
            persisted = repo.upsert(tracking)

        assert persisted.id is not None
        assert persisted.video_id == VideoId(vid)
        assert persisted.status is TrackingStatus.SAVED
        assert persisted.starred is True
        assert persisted.notes == "cool hook"
        assert persisted.created_at is not None
        assert persisted.created_at.tzinfo is not None
        assert persisted.updated_at is not None

    def test_upsert_existing_row_replaces_fields(self, engine: Engine) -> None:
        vid = _insert_video(engine, "tup2")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            first = repo.upsert(
                VideoTracking(
                    video_id=VideoId(vid), status=TrackingStatus.NEW, notes="initial",
                )
            )
        time.sleep(0.01)
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            second = repo.upsert(
                VideoTracking(
                    video_id=VideoId(vid),
                    status=TrackingStatus.ACTIONED,
                    starred=True,
                    notes="updated",
                )
            )
        assert first.id == second.id  # same row
        assert second.status is TrackingStatus.ACTIONED
        assert second.starred is True
        assert second.notes == "updated"
        assert second.updated_at is not None and first.updated_at is not None
        assert second.updated_at >= first.updated_at

    def test_second_upsert_does_not_raise(self, engine: Engine) -> None:
        """Pitfall 3: ON CONFLICT DO UPDATE prevents IntegrityError."""
        vid = _insert_video(engine, "tup3")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            repo.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.NEW))
            repo.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.REVIEWED))
            repo.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.SAVED))


class TestReads:
    def test_get_for_video_none_when_absent(self, engine: Engine) -> None:
        with engine.connect() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            assert repo.get_for_video(VideoId(99999)) is None

    def test_get_for_video_returns_entity(self, engine: Engine) -> None:
        vid = _insert_video(engine, "tr1")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            repo.upsert(
                VideoTracking(
                    video_id=VideoId(vid), status=TrackingStatus.SAVED, starred=True,
                )
            )
        with engine.connect() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            got = repo.get_for_video(VideoId(vid))
        assert got is not None
        assert got.status is TrackingStatus.SAVED
        assert got.starred is True

    def test_list_by_status_filters_and_orders(self, engine: Engine) -> None:
        # Three videos, two with status SAVED, one with NEW.
        vids = [_insert_video(engine, f"tb{i}") for i in range(3)]
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            repo.upsert(VideoTracking(video_id=VideoId(vids[0]), status=TrackingStatus.SAVED))
            time.sleep(0.01)
            repo.upsert(VideoTracking(video_id=VideoId(vids[1]), status=TrackingStatus.NEW))
            time.sleep(0.01)
            repo.upsert(VideoTracking(video_id=VideoId(vids[2]), status=TrackingStatus.SAVED))

        with engine.connect() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            saved = repo.list_by_status(TrackingStatus.SAVED)
        assert len(saved) == 2
        assert all(t.status is TrackingStatus.SAVED for t in saved)
        # Ordered by updated_at DESC -> vids[2] first
        assert int(saved[0].video_id) == vids[2]

    def test_list_starred_filters(self, engine: Engine) -> None:
        v1 = _insert_video(engine, "ts1")
        v2 = _insert_video(engine, "ts2")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            repo.upsert(VideoTracking(video_id=VideoId(v1), status=TrackingStatus.NEW, starred=True))
            repo.upsert(VideoTracking(video_id=VideoId(v2), status=TrackingStatus.NEW, starred=False))
        with engine.connect() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            starred = repo.list_starred()
        assert len(starred) == 1
        assert int(starred[0].video_id) == v1


class TestCascade:
    def test_delete_video_cascades_to_tracking(self, engine: Engine) -> None:
        vid = _insert_video(engine, "tc1")
        with engine.begin() as conn:
            repo = VideoTrackingRepositorySQLite(conn)
            repo.upsert(VideoTracking(video_id=VideoId(vid), status=TrackingStatus.SAVED))
        # Enable FK enforcement for this connection then delete.
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("DELETE FROM videos WHERE id=:v"), {"v": vid})
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM video_tracking WHERE video_id=:v"),
                {"v": vid},
            ).scalar()
        assert row == 0


class TestUoWExposure:
    def test_uow_exposes_video_tracking(self, engine: Engine) -> None:
        from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork

        with SqliteUnitOfWork(engine) as uow:
            assert isinstance(uow.video_tracking, VideoTrackingRepositorySQLite)
