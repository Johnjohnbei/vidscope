"""Tests for WatchRefreshRepositorySQLite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import WatchRefresh

UTC_NOW = datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC)


class TestWatchRefreshRepository:
    def test_add_and_read_back(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.watch_refreshes.add(
                WatchRefresh(
                    started_at=UTC_NOW,
                    accounts_checked=2,
                    new_videos_ingested=5,
                )
            )
            assert stored.id is not None
            assert stored.accounts_checked == 2

        with SqliteUnitOfWork(engine) as uow:
            rows = uow.watch_refreshes.list_recent(limit=10)
            assert len(rows) == 1
            assert rows[0].accounts_checked == 2
            assert rows[0].new_videos_ingested == 5
            assert rows[0].errors == ()

    def test_errors_tuple_round_trip(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.watch_refreshes.add(
                WatchRefresh(
                    started_at=UTC_NOW,
                    accounts_checked=3,
                    new_videos_ingested=1,
                    errors=("account @one: rate limit", "account @two: 404"),
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            rows = uow.watch_refreshes.list_recent()
            assert rows[0].errors == (
                "account @one: rate limit",
                "account @two: 404",
            )

    def test_finished_at_round_trip(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.watch_refreshes.add(
                WatchRefresh(
                    started_at=UTC_NOW,
                    finished_at=UTC_NOW + timedelta(seconds=10),
                    accounts_checked=1,
                    new_videos_ingested=0,
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            rows = uow.watch_refreshes.list_recent()
            r = rows[0]
            assert r.finished_at is not None
            d = r.duration()
            assert d is not None
            assert d.total_seconds() == 10

    def test_list_recent_newest_first(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            for i in range(5):
                uow.watch_refreshes.add(
                    WatchRefresh(
                        started_at=UTC_NOW + timedelta(minutes=i),
                        accounts_checked=i,
                        new_videos_ingested=i,
                    )
                )

        with SqliteUnitOfWork(engine) as uow:
            rows = uow.watch_refreshes.list_recent(limit=3)
            assert len(rows) == 3
            # Newest first: started_at descending
            assert rows[0].accounts_checked == 4
            assert rows[1].accounts_checked == 3
            assert rows[2].accounts_checked == 2
