"""TagRepositorySQLite (M011/S02/R057)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.tag_repository import TagRepositorySQLite
from vidscope.domain import VideoId
from vidscope.domain.errors import StorageError


def _insert_video(engine: Engine, platform_id: str) -> int:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO videos (platform, platform_id, url, created_at) "
                 "VALUES ('youtube', :pid, :u, :c)"),
            {"pid": platform_id, "u": f"https://y.be/{platform_id}",
             "c": datetime.now(UTC)},
        )
        return int(conn.execute(
            text("SELECT id FROM videos WHERE platform_id=:pid"),
            {"pid": platform_id},
        ).scalar())


class TestTagMigration:
    def test_tables_exist(self, engine: Engine) -> None:
        with engine.connect() as conn:
            names = {row[0] for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )}
        assert "tags" in names
        assert "tag_assignments" in names

    def test_idempotent_migration(self, engine: Engine) -> None:
        from vidscope.adapters.sqlite.schema import _ensure_tags_collections_tables
        with engine.begin() as conn:
            _ensure_tags_collections_tables(conn)
            _ensure_tags_collections_tables(conn)


class TestGetOrCreate:
    def test_creates_new(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t = repo.get_or_create("idea")
        assert t.name == "idea"
        assert t.id is not None

    def test_normalizes_case_and_whitespace(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t1 = repo.get_or_create("Idea")
            t2 = repo.get_or_create("IDEA")
            t3 = repo.get_or_create("  idea  ")
        assert t1.id == t2.id == t3.id
        assert t1.name == "idea"

    def test_empty_name_raises(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            with pytest.raises(StorageError):
                repo.get_or_create("   ")
            with pytest.raises(StorageError):
                repo.get_or_create("")


class TestListAndFindTag:
    def test_list_all_sorted(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            repo.get_or_create("zeta")
            repo.get_or_create("alpha")
            repo.get_or_create("mu")
            tags = repo.list_all()
        names = [t.name for t in tags]
        assert names == sorted(names)

    def test_get_by_name_none_when_absent(self, engine: Engine) -> None:
        with engine.connect() as conn:
            repo = TagRepositorySQLite(conn)
            assert repo.get_by_name("nonexistent") is None


class TestAssignUnassign:
    def test_assign_idempotent(self, engine: Engine) -> None:
        vid = _insert_video(engine, "ta1")
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t = repo.get_or_create("idea")
            assert t.id is not None
            repo.assign(VideoId(vid), t.id)
            repo.assign(VideoId(vid), t.id)  # idempotent
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM tag_assignments "
                     "WHERE video_id=:v AND tag_id=:t"),
                {"v": vid, "t": t.id},
            ).scalar()
        assert n == 1

    def test_unassign_noop_when_absent(self, engine: Engine) -> None:
        vid = _insert_video(engine, "ta2")
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t = repo.get_or_create("idea")
            assert t.id is not None
            repo.unassign(VideoId(vid), t.id)  # no-op, no error

    def test_list_for_video(self, engine: Engine) -> None:
        vid = _insert_video(engine, "ta3")
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t1 = repo.get_or_create("idea")
            t2 = repo.get_or_create("reuse")
            assert t1.id is not None and t2.id is not None
            repo.assign(VideoId(vid), t1.id)
            repo.assign(VideoId(vid), t2.id)
            tags = repo.list_for_video(VideoId(vid))
        names = {t.name for t in tags}
        assert names == {"idea", "reuse"}

    def test_list_video_ids_for_tag(self, engine: Engine) -> None:
        v1 = _insert_video(engine, "ta4")
        v2 = _insert_video(engine, "ta5")
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t = repo.get_or_create("hook")
            assert t.id is not None
            repo.assign(VideoId(v1), t.id)
            repo.assign(VideoId(v2), t.id)
            ids = repo.list_video_ids_for_tag("hook")
        assert set(int(i) for i in ids) == {v1, v2}

    def test_cascade_delete_video(self, engine: Engine) -> None:
        vid = _insert_video(engine, "ta6")
        with engine.begin() as conn:
            repo = TagRepositorySQLite(conn)
            t = repo.get_or_create("idea")
            assert t.id is not None
            repo.assign(VideoId(vid), t.id)
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(text("DELETE FROM videos WHERE id=:v"), {"v": vid})
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM tag_assignments WHERE video_id=:v"),
                {"v": vid},
            ).scalar()
        assert n == 0
