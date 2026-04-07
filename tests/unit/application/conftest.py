"""Fixtures for application-layer tests.

Each test gets a fresh SQLite engine bound to a tmp_path file, with
every table initialized via the real adapter. The UoW factory closes
over the engine. A fixed clock keeps timestamps deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine

from vidscope.adapters.sqlite.schema import init_db
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.infrastructure.sqlite_engine import build_engine
from vidscope.ports import UnitOfWork, UnitOfWorkFactory


@pytest.fixture()
def engine(tmp_path: Path) -> Engine:
    db_path = tmp_path / "app.db"
    eng = build_engine(db_path)
    init_db(eng)
    return eng


@pytest.fixture()
def uow_factory(engine: Engine) -> UnitOfWorkFactory:
    def _factory() -> UnitOfWork:
        return SqliteUnitOfWork(engine)

    return _factory


class FrozenClock:
    def __init__(self, when: datetime) -> None:
        self._when = when

    def now(self) -> datetime:
        return self._when


@pytest.fixture()
def clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC))
