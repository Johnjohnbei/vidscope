"""Schema-level tests for the SQLite adapter."""

from __future__ import annotations

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
