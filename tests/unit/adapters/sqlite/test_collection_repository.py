"""CollectionRepositorySQLite (M011/S02/R057)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.collection_repository import (
    CollectionRepositorySQLite,
)
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


class TestCreate:
    def test_create_returns_entity(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("Concurrents Shopify")
        assert c.name == "Concurrents Shopify"
        assert c.id is not None

    def test_duplicate_name_raises(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            repo.create("X")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            with pytest.raises(StorageError):
                repo.create("X")

    def test_case_preserved_distinct_rows(self, engine: Engine) -> None:
        """D3 M011 RESEARCH: collection names are case-preserved."""
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            a = repo.create("Concurrents")
            b = repo.create("concurrents")
        assert a.id != b.id

    def test_empty_name_raises(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            with pytest.raises(StorageError):
                repo.create("   ")


class TestListAndLookup:
    def test_list_all_sorted(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            repo.create("Zeta")
            repo.create("Alpha")
            repo.create("Mu")
            cols = repo.list_all()
        names = [c.name for c in cols]
        assert names == sorted(names)

    def test_get_by_name(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            repo.create("My Collection")
        with engine.connect() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.get_by_name("My Collection")
            miss = repo.get_by_name("nope")
        assert c is not None
        assert c.name == "My Collection"
        assert miss is None


class TestMembership:
    def test_add_video_idempotent(self, engine: Engine) -> None:
        vid = _insert_video(engine, "cm1")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("C1")
            assert c.id is not None
            repo.add_video(c.id, VideoId(vid))
            repo.add_video(c.id, VideoId(vid))
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM collection_items "
                     "WHERE collection_id=:c AND video_id=:v"),
                {"c": c.id, "v": vid},
            ).scalar()
        assert n == 1

    def test_remove_video_noop_when_absent(self, engine: Engine) -> None:
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("C2")
            assert c.id is not None
            repo.remove_video(c.id, VideoId(999))

    def test_list_videos_ordered_desc(self, engine: Engine) -> None:
        import time
        v1 = _insert_video(engine, "cm2")
        v2 = _insert_video(engine, "cm3")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("C3")
            assert c.id is not None
            repo.add_video(c.id, VideoId(v1))
        time.sleep(0.01)
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.get_by_name("C3")
            assert c is not None and c.id is not None
            repo.add_video(c.id, VideoId(v2))
        with engine.connect() as conn:
            repo = CollectionRepositorySQLite(conn)
            ids = repo.list_videos(c.id)
        # Most-recently-added first: v2 then v1
        assert [int(i) for i in ids] == [v2, v1]

    def test_list_video_ids_for_collection(self, engine: Engine) -> None:
        v1 = _insert_video(engine, "cm4")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("Find Me")
            assert c.id is not None
            repo.add_video(c.id, VideoId(v1))
        with engine.connect() as conn:
            repo = CollectionRepositorySQLite(conn)
            ids = repo.list_video_ids_for_collection("Find Me")
        assert [int(i) for i in ids] == [v1]

    def test_list_collections_for_video(self, engine: Engine) -> None:
        vid = _insert_video(engine, "cm5")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c1 = repo.create("A")
            c2 = repo.create("B")
            assert c1.id is not None and c2.id is not None
            repo.add_video(c1.id, VideoId(vid))
            repo.add_video(c2.id, VideoId(vid))
            cols = repo.list_collections_for_video(VideoId(vid))
        assert {c.name for c in cols} == {"A", "B"}

    def test_cascade_delete_video(self, engine: Engine) -> None:
        vid = _insert_video(engine, "cm6")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("Casc")
            assert c.id is not None
            repo.add_video(c.id, VideoId(vid))
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(text("DELETE FROM videos WHERE id=:v"), {"v": vid})
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM collection_items WHERE video_id=:v"),
                {"v": vid},
            ).scalar()
        assert n == 0

    def test_cascade_delete_collection(self, engine: Engine) -> None:
        vid = _insert_video(engine, "cm7")
        with engine.begin() as conn:
            repo = CollectionRepositorySQLite(conn)
            c = repo.create("DelMe")
            assert c.id is not None
            repo.add_video(c.id, VideoId(vid))
            cid = c.id
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(text("DELETE FROM collections WHERE id=:c"), {"c": cid})
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT COUNT(*) FROM collection_items WHERE collection_id=:c"),
                {"c": cid},
            ).scalar()
        assert n == 0


class TestUoWExposure:
    def test_uow_exposes_tags_and_collections(self, engine: Engine) -> None:
        from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
        with SqliteUnitOfWork(engine) as uow:
            assert uow.tags is not None
            assert uow.collections is not None
