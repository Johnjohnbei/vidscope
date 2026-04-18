"""Schema-level tests for the SQLite adapter."""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from vidscope.adapters.sqlite.schema import _ensure_video_stats_table, init_db


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
            "video_stats",   # M009
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

    def test_init_db_creates_video_stats_table(self, engine: Engine) -> None:
        """M009: video_stats table must be created by init_db."""
        with engine.connect() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            }
            assert "video_stats" in tables

    def test_init_db_is_idempotent_on_video_stats(self, engine: Engine) -> None:
        """Calling init_db twice must not raise (idempotent migration)."""
        init_db(engine)
        init_db(engine)
        with engine.connect() as conn:
            indexes = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='index' "
                        "AND tbl_name='video_stats'"
                    )
                )
            }
            assert "idx_video_stats_video_id" in indexes
            assert "idx_video_stats_captured_at" in indexes

    def test_ensure_video_stats_table_on_pre_m009_db(self, tmp_path: object) -> None:
        """Simulate a pre-M009 DB: create videos, then add video_stats via migration."""
        from pathlib import Path

        from vidscope.infrastructure.sqlite_engine import build_engine

        db_path = Path(str(tmp_path)) / "pre_m009.db"  # type: ignore[arg-type]
        eng = build_engine(db_path)
        with eng.begin() as conn:
            conn.execute(text("CREATE TABLE videos (id INTEGER PRIMARY KEY)"))
            _ensure_video_stats_table(conn)
            tables = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            }
            assert "video_stats" in tables

    def test_ensure_video_stats_table_is_noop_when_exists(self, engine: Engine) -> None:
        """_ensure_video_stats_table does not raise when table already exists."""
        with engine.begin() as conn:
            _ensure_video_stats_table(conn)  # second call — must be no-op
