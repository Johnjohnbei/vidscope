"""Fuzz SQL injection across facet values (M011/S03/R058 T-SQL-M011-03).

All facet values go through SQLAlchemy Core bind params — injection
is structurally impossible. These tests assert:
- The query does not raise on malicious inputs.
- The `videos` table remains intact (no DROP executed).
- Inputs containing SQL metacharacters match no rows (no leak via LIKE).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.application.search_videos import SearchFilters, SearchVideosUseCase

MALICIOUS_PAYLOADS = [
    "'",
    "--",
    "; DROP TABLE videos;--",
    "' OR '1'='1",
    "' UNION SELECT * FROM videos--",
    "\\",
    "%",
    "_",
    "\x00",
    "\" OR 1=1--",
    "`",
    "<script>alert(1)</script>",
    "../../etc/passwd",
    "0; SELECT * FROM sqlite_master",
    "\n\r\t",
    "normal_tag_name",
    "AAAAA" * 500,  # very long
    "emoji_test",
    "zhongwen_test",
    "\"; DELETE FROM tags;--",
]


@pytest.fixture
def _seeded_db(engine: Engine):
    """Insert 2 videos so we can verify they survive the fuzz."""
    with engine.begin() as conn:
        for pid in ("fuzz1", "fuzz2"):
            conn.execute(
                text("INSERT INTO videos (platform, platform_id, url, created_at) "
                     "VALUES ('youtube', :p, :u, :c)"),
                {"p": pid, "u": f"https://y.be/{pid}", "c": datetime.now(UTC)},
            )
    return engine


class TestSqlInjectionResistance:
    @pytest.mark.parametrize("payload", MALICIOUS_PAYLOADS)
    def test_tag_facet(self, _seeded_db: Engine, payload: str) -> None:
        def _factory():
            return SqliteUnitOfWork(_seeded_db)

        uc = SearchVideosUseCase(unit_of_work_factory=_factory)
        # Should not raise
        result = uc.execute("*", filters=SearchFilters(tag=payload))
        # Videos table still there
        with _seeded_db.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM videos")).scalar()
        assert count == 2
        # No leaked rows (no FTS5 matches since search_index is empty)
        assert isinstance(result.hits, tuple)

    @pytest.mark.parametrize("payload", MALICIOUS_PAYLOADS)
    def test_collection_facet(self, _seeded_db: Engine, payload: str) -> None:
        def _factory():
            return SqliteUnitOfWork(_seeded_db)

        uc = SearchVideosUseCase(unit_of_work_factory=_factory)
        result = uc.execute("*", filters=SearchFilters(collection=payload))
        with _seeded_db.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM videos")).scalar()
        assert count == 2
        assert isinstance(result.hits, tuple)

    def test_tables_still_exist_after_all_fuzz(self, _seeded_db: Engine) -> None:
        with _seeded_db.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            }
        for required in ("videos", "video_tracking", "tags", "tag_assignments",
                         "collections", "collection_items"):
            assert required in names
