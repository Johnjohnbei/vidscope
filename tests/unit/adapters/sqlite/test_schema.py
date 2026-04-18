"""Schema-level tests for the SQLite adapter."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, inspect, text

from vidscope.adapters.sqlite.schema import init_db


class TestInitDb:
    def test_creates_every_expected_table(self, engine: Engine) -> None:
        names = set(inspect(engine).get_table_names())
        expected = {
            "videos",
            "transcripts",
            "frames",
            "analyses",
            "pipeline_runs",
            "search_index",  # FTS5 virtual table
        }
        assert expected.issubset(names), f"missing: {expected - names}"

    def test_init_db_is_idempotent(self, engine: Engine) -> None:
        # Calling init_db twice must not raise.
        init_db(engine)
        init_db(engine)

    def test_foreign_keys_are_enabled_on_connections(
        self, engine: Engine
    ) -> None:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys")).scalar()
            assert result == 1

    def test_search_index_accepts_fts5_match_syntax(
        self, engine: Engine
    ) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO search_index (video_id, source, text) "
                    "VALUES (:vid, :src, :txt)"
                ),
                {
                    "vid": 1,
                    "src": "transcript",
                    "txt": "bonjour tout le monde",
                },
            )
            row = conn.execute(
                text(
                    "SELECT video_id, source, text FROM search_index "
                    "WHERE search_index MATCH 'bonjour'"
                )
            ).mappings().first()
            assert row is not None
            assert row["video_id"] == 1
            assert row["source"] == "transcript"


class TestCreatorsSchema:
    """Schema-level tests for the creators table (M006/S01)."""

    def test_creators_table_exists(self, engine: Engine) -> None:
        names = set(inspect(engine).get_table_names())
        assert "creators" in names

    def test_videos_creator_id_column_exists(self, engine: Engine) -> None:
        cols = {c["name"] for c in inspect(engine).get_columns("videos")}
        assert "creator_id" in cols

    def test_creators_unique_platform_user_id_enforced(
        self, engine: Engine
    ) -> None:
        from sqlalchemy.exc import IntegrityError

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO creators "
                    "(platform, platform_user_id, is_orphan, created_at) "
                    "VALUES ('youtube', 'UC_ABC', 0, CURRENT_TIMESTAMP)"
                )
            )
        # Same (platform, platform_user_id) must fail the compound UNIQUE.
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO creators "
                    "(platform, platform_user_id, is_orphan, created_at) "
                    "VALUES ('youtube', 'UC_ABC', 0, CURRENT_TIMESTAMP)"
                )
            )

    def test_same_platform_user_id_across_platforms_ok(
        self, engine: Engine
    ) -> None:
        # D-01 scope: no cross-platform identity resolution.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO creators "
                    "(platform, platform_user_id, is_orphan, created_at) "
                    "VALUES ('youtube', 'shared_id', 0, CURRENT_TIMESTAMP)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO creators "
                    "(platform, platform_user_id, is_orphan, created_at) "
                    "VALUES ('tiktok', 'shared_id', 0, CURRENT_TIMESTAMP)"
                )
            )
            total = conn.execute(
                text("SELECT COUNT(*) FROM creators")
            ).scalar()
            assert total == 2

    def test_videos_creator_id_set_null_on_creator_delete(
        self, engine: Engine
    ) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO creators "
                    "(id, platform, platform_user_id, is_orphan, created_at) "
                    "VALUES (100, 'youtube', 'UC_DEL', 0, CURRENT_TIMESTAMP)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO videos "
                    "(platform, platform_id, url, creator_id, created_at) "
                    "VALUES ('youtube', 'v_del', 'https://x', 100, CURRENT_TIMESTAMP)"
                )
            )

            # Delete creator — videos row must survive with creator_id = NULL
            conn.execute(text("DELETE FROM creators WHERE id = 100"))
            row = conn.execute(
                text(
                    "SELECT creator_id FROM videos WHERE platform_id = 'v_del'"
                )
            ).first()
            assert row is not None
            assert row[0] is None  # ON DELETE SET NULL fired

    def test_idx_creators_handle_exists(self, engine: Engine) -> None:
        indexes = inspect(engine).get_indexes("creators")
        names = {idx["name"] for idx in indexes}
        assert "idx_creators_handle" in names

    def test_idx_videos_creator_id_exists(self, engine: Engine) -> None:
        indexes = inspect(engine).get_indexes("videos")
        names = {idx["name"] for idx in indexes}
        assert "idx_videos_creator_id" in names


class TestVideosCreatorIdAlter:
    """Tests for ``_ensure_videos_creator_id`` idempotency.

    Two paths must work:
    1. Fresh install — videos.creator_id declared inline on the Table.
    2. Upgrade path — pre-M006 videos table exists WITHOUT the column;
       _ensure_videos_creator_id must ALTER it in.
    """

    def test_ensure_idempotent_on_fresh_install(
        self, engine: Engine
    ) -> None:
        # engine fixture already ran init_db once. Run it again.
        init_db(engine)
        init_db(engine)  # third call, still no error
        cols = {c["name"] for c in inspect(engine).get_columns("videos")}
        assert "creator_id" in cols

    def test_upgrade_path_adds_creator_id(self, tmp_path: object) -> None:
        """Simulate a pre-M006 DB: create videos WITHOUT creator_id,
        then run init_db and assert the column gets added.
        """
        from pathlib import Path

        from vidscope.infrastructure.sqlite_engine import build_engine

        db_path = Path(str(tmp_path)) / "pre_m006.db"  # type: ignore[arg-type]
        eng = build_engine(db_path)

        # Pre-M006 minimal videos table (no creator_id)
        with eng.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE videos ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "platform TEXT NOT NULL, "
                    "platform_id TEXT NOT NULL UNIQUE, "
                    "url TEXT NOT NULL, "
                    "author TEXT, "
                    "title TEXT, "
                    "duration REAL, "
                    "upload_date TEXT, "
                    "view_count INTEGER, "
                    "media_key TEXT, "
                    "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            # Seed one row so we know data survives the ALTER
            conn.execute(
                text(
                    "INSERT INTO videos (platform, platform_id, url, author) "
                    "VALUES ('youtube', 'legacy_v1', 'https://x', 'Old Author')"
                )
            )

        # Now run init_db — should add creator_id without losing data
        init_db(eng)

        cols = {c["name"] for c in inspect(eng).get_columns("videos")}
        assert "creator_id" in cols

        with eng.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT author, creator_id FROM videos "
                    "WHERE platform_id = 'legacy_v1'"
                )
            ).first()
            assert row is not None
            assert row[0] == "Old Author"  # data preserved
            assert row[1] is None  # new column defaults to NULL

    def test_ensure_creator_id_helper_directly_idempotent(
        self, tmp_path: object
    ) -> None:
        """Call _ensure_videos_creator_id twice explicitly to pin
        the PRAGMA table_info guard.
        """
        from pathlib import Path

        from vidscope.adapters.sqlite.schema import (
            _ensure_videos_creator_id,
        )
        from vidscope.infrastructure.sqlite_engine import build_engine

        eng = build_engine(Path(str(tmp_path)) / "idem.db")  # type: ignore[arg-type]
        init_db(eng)
        with eng.begin() as conn:
            _ensure_videos_creator_id(conn)  # second call, no error
            _ensure_videos_creator_id(conn)  # third call, no error


class TestM007Schema:
    """M007/S01-P02: hashtags/mentions tables + _ensure_videos_metadata_columns."""

    def test_hashtags_table_exists(self, engine: Engine) -> None:
        names = set(inspect(engine).get_table_names())
        assert "hashtags" in names

    def test_mentions_table_exists(self, engine: Engine) -> None:
        names = set(inspect(engine).get_table_names())
        assert "mentions" in names

    def test_videos_has_description_column(self, engine: Engine) -> None:
        cols = {c["name"] for c in inspect(engine).get_columns("videos")}
        assert "description" in cols

    def test_videos_has_music_track_column(self, engine: Engine) -> None:
        cols = {c["name"] for c in inspect(engine).get_columns("videos")}
        assert "music_track" in cols

    def test_videos_has_music_artist_column(self, engine: Engine) -> None:
        cols = {c["name"] for c in inspect(engine).get_columns("videos")}
        assert "music_artist" in cols

    def test_init_db_idempotent_m007(self, engine: Engine) -> None:
        """init_db called twice must not raise with M007 helpers."""
        init_db(engine)
        init_db(engine)

    def test_ensure_videos_metadata_columns_directly_idempotent(
        self, tmp_path: object
    ) -> None:
        """Call _ensure_videos_metadata_columns twice explicitly."""
        from pathlib import Path

        from vidscope.adapters.sqlite.schema import (
            _ensure_videos_metadata_columns,
        )
        from vidscope.infrastructure.sqlite_engine import build_engine

        eng = build_engine(Path(str(tmp_path)) / "m007_idem.db")  # type: ignore[arg-type]
        init_db(eng)
        with eng.begin() as conn:
            _ensure_videos_metadata_columns(conn)  # second call — must be no-op
            _ensure_videos_metadata_columns(conn)  # third call

    def test_upgrade_path_adds_metadata_columns(self, tmp_path: object) -> None:
        """Simulate pre-M007 DB (no description/music columns) then run init_db."""
        from pathlib import Path

        from vidscope.infrastructure.sqlite_engine import build_engine

        db_path = Path(str(tmp_path)) / "pre_m007.db"  # type: ignore[arg-type]
        eng = build_engine(db_path)

        # Pre-M007 minimal videos table (no description/music_track/music_artist)
        with eng.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE videos ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "platform TEXT NOT NULL, "
                    "platform_id TEXT NOT NULL UNIQUE, "
                    "url TEXT NOT NULL, "
                    "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            # Also create creators table (required for FK in videos)
            conn.execute(
                text(
                    "CREATE TABLE creators ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "platform TEXT NOT NULL, "
                    "platform_user_id TEXT NOT NULL, "
                    "is_orphan INTEGER NOT NULL DEFAULT 0, "
                    "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "UNIQUE(platform, platform_user_id)"
                    ")"
                )
            )

        # Now run init_db — should add the 3 metadata columns
        init_db(eng)

        cols = {c["name"] for c in inspect(eng).get_columns("videos")}
        assert "description" in cols
        assert "music_track" in cols
        assert "music_artist" in cols


class TestLinksSchema:
    """M007/S02-P01: links table + indexes."""

    def test_links_table_exists_after_init_db(self, engine: Engine) -> None:
        names = set(inspect(engine).get_table_names())
        assert "links" in names

    def test_links_table_has_expected_columns(self, engine: Engine) -> None:
        cols = {c["name"] for c in inspect(engine).get_columns("links")}
        expected = {
            "id", "video_id", "url", "normalized_url",
            "source", "position_ms", "created_at",
        }
        assert expected == cols

    def test_links_video_id_index_exists(self, engine: Engine) -> None:
        indexes = inspect(engine).get_indexes("links")
        names = {idx["name"] for idx in indexes}
        assert "idx_links_video_id" in names

    def test_links_normalized_url_index_exists(self, engine: Engine) -> None:
        indexes = inspect(engine).get_indexes("links")
        names = {idx["name"] for idx in indexes}
        assert "idx_links_normalized_url" in names

    def test_links_source_index_exists(self, engine: Engine) -> None:
        indexes = inspect(engine).get_indexes("links")
        names = {idx["name"] for idx in indexes}
        assert "idx_links_source" in names

    def test_links_table_created_by_init_db_sql(self, engine: Engine) -> None:
        """Verify the links table DDL exists in sqlite_master."""
        with engine.connect() as conn:
            sql = conn.execute(
                text('SELECT sql FROM sqlite_master WHERE name="links"')
            ).scalar()
        assert sql is not None
