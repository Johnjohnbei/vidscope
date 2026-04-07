"""Fixtures shared by the sqlite adapter tests.

Every test gets a fresh file-backed SQLite engine sandboxed under
``tmp_path``. We use a real file (not ``:memory:``) so FTS5 behaves
exactly as it does in production.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.sqlite.schema import init_db
from vidscope.infrastructure.sqlite_engine import build_engine


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    """Return a fresh engine with every table and FTS5 table created."""
    db_path = tmp_path / "test.db"
    eng = build_engine(db_path)
    init_db(eng)
    return eng
