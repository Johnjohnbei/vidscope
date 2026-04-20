"""Schema-level tests for the SQLite adapter."""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from vidscope.adapters.sqlite.schema import (
    _ensure_analysis_v2_columns,
    _ensure_video_stats_table,
    _ensure_visual_media_columns,
    init_db,
)


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

    def test_ensure_description_column_idempotent(self, tmp_path: object) -> None:
        """M012/S01 — description column added idempotently, second init_db is a no-op."""
        from pathlib import Path
        from sqlalchemy import create_engine, text
        from vidscope.infrastructure.sqlite_engine import build_engine

        db_path = Path(str(tmp_path)) / "test_desc.db"  # type: ignore[arg-type]
        engine = build_engine(db_path)

        init_db(engine)
        init_db(engine)  # second call must not raise

        with engine.connect() as conn:
            cols = {row[1]: row[2] for row in conn.execute(text("PRAGMA table_info(videos)"))}
        assert "description" in cols
        assert cols["description"].upper() == "TEXT"


class TestAnalysisV2Migration:
    """M010 additive migration on analyses table."""

    def test_new_columns_exist_after_init_db(self, engine: Engine) -> None:
        with engine.connect() as conn:
            cols = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(analyses)"))
            }
        expected_new = {
            "verticals",
            "information_density",
            "actionability",
            "novelty",
            "production_quality",
            "sentiment",
            "is_sponsored",
            "content_type",
            "reasoning",
        }
        missing = expected_new - cols
        assert not missing, f"missing M010 columns on analyses: {missing}"

    def test_ensure_analysis_v2_columns_is_idempotent(self, engine: Engine) -> None:
        with engine.begin() as conn:
            _ensure_analysis_v2_columns(conn)
            _ensure_analysis_v2_columns(conn)
        # no exception means idempotent

    def test_pre_m010_rows_survive_migration(self, engine: Engine) -> None:
        """Rows inserted before the M010 columns existed must stay intact."""
        from datetime import UTC, datetime

        # Insert a row using only pre-M010 columns (values for M010 columns NULL by default)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO videos (platform, platform_id, url, created_at) "
                     "VALUES (:p, :pid, :u, :c)"),
                {"p": "youtube", "pid": "legacy1", "u": "https://y.be/legacy1",
                 "c": datetime(2026, 1, 1, tzinfo=UTC)},
            )
            vid = conn.execute(text("SELECT id FROM videos WHERE platform_id='legacy1'")).scalar()
            conn.execute(
                text("INSERT INTO analyses (video_id, provider, language, keywords, topics, "
                     "score, summary, created_at) "
                     "VALUES (:v, 'heuristic', 'en', '[]', '[]', 42, 'legacy summary', :c)"),
                {"v": vid, "c": datetime(2026, 1, 1, tzinfo=UTC)},
            )
        # Re-apply migration
        with engine.begin() as conn:
            _ensure_analysis_v2_columns(conn)
        # Legacy data still there
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT score, summary, reasoning FROM analyses WHERE provider='heuristic'")
            ).mappings().first()
        assert row is not None
        assert row["score"] == 42
        assert row["summary"] == "legacy summary"
        assert row["reasoning"] is None


class TestVisualMediaColumnsMigration:
    """_ensure_visual_media_columns adds thumbnail_key, content_shape, media_type."""

    def test_columns_exist_after_init_db(self, engine: Engine) -> None:
        with engine.connect() as conn:
            cols = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(videos)"))
            }
        assert "thumbnail_key" in cols
        assert "content_shape" in cols
        assert "media_type" in cols

    def test_ensure_visual_media_columns_is_idempotent(
        self, engine: Engine
    ) -> None:
        with engine.begin() as conn:
            _ensure_visual_media_columns(conn)
            _ensure_visual_media_columns(conn)
        # no exception means idempotent

    def test_adds_columns_to_db_missing_them(self, tmp_path: object) -> None:
        """Simulate a pre-migration DB that has no visual media columns."""
        from pathlib import Path

        from vidscope.infrastructure.sqlite_engine import build_engine

        db_path = Path(str(tmp_path)) / "pre_visual.db"  # type: ignore[arg-type]
        eng = build_engine(db_path)
        # Create the videos table without the visual columns
        with eng.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE videos ("
                    "id INTEGER PRIMARY KEY, "
                    "platform TEXT NOT NULL, "
                    "platform_id TEXT NOT NULL UNIQUE, "
                    "url TEXT NOT NULL, "
                    "created_at TEXT NOT NULL"
                    ")"
                )
            )
            # Confirm the columns are absent before migration
            cols_before = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(videos)"))
            }
            assert "thumbnail_key" not in cols_before
            assert "content_shape" not in cols_before
            assert "media_type" not in cols_before

            _ensure_visual_media_columns(conn)

            cols_after = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(videos)"))
            }

        assert "thumbnail_key" in cols_after
        assert "content_shape" in cols_after
        assert "media_type" in cols_after

    def test_pre_existing_rows_survive_migration(self, tmp_path: object) -> None:
        """Rows inserted before the visual columns must remain intact after migration."""
        from pathlib import Path

        from vidscope.infrastructure.sqlite_engine import build_engine

        db_path = Path(str(tmp_path)) / "pre_visual2.db"  # type: ignore[arg-type]
        eng = build_engine(db_path)
        with eng.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE videos ("
                    "id INTEGER PRIMARY KEY, "
                    "platform TEXT NOT NULL, "
                    "platform_id TEXT NOT NULL UNIQUE, "
                    "url TEXT NOT NULL, "
                    "created_at TEXT NOT NULL"
                    ")"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO videos (platform, platform_id, url, created_at) "
                    "VALUES ('youtube', 'old1', 'https://example.com', '2026-01-01')"
                )
            )
            _ensure_visual_media_columns(conn)

        with eng.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT platform_id, thumbnail_key, content_shape, media_type "
                    "FROM videos WHERE platform_id = 'old1'"
                )
            ).mappings().first()

        assert row is not None
        assert row["platform_id"] == "old1"
        assert row["thumbnail_key"] is None
        assert row["content_shape"] is None
        assert row["media_type"] is None
