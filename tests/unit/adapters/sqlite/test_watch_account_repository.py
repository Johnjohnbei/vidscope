"""Tests for WatchAccountRepositorySQLite."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine

from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.domain import Platform, WatchedAccount
from vidscope.domain.errors import StorageError

UTC_NOW = datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC)


def _sample_account(
    *,
    platform: Platform = Platform.YOUTUBE,
    handle: str = "@YouTube",
    url: str = "https://www.youtube.com/@YouTube",
) -> WatchedAccount:
    return WatchedAccount(platform=platform, handle=handle, url=url)


class TestWatchAccountRepository:
    def test_add_and_get_round_trip(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.watch_accounts.add(_sample_account())
            assert stored.id is not None
            assert stored.handle == "@YouTube"
            assert stored.platform is Platform.YOUTUBE
            assert stored.created_at is not None

        with SqliteUnitOfWork(engine) as uow:
            fetched = uow.watch_accounts.get(stored.id)  # type: ignore[arg-type]
            assert fetched is not None
            assert fetched.handle == "@YouTube"

    def test_get_missing_returns_none(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            assert uow.watch_accounts.get(999) is None

    def test_get_by_handle(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.watch_accounts.add(_sample_account(handle="@tiktok", platform=Platform.TIKTOK))

        with SqliteUnitOfWork(engine) as uow:
            found = uow.watch_accounts.get_by_handle(Platform.TIKTOK, "@tiktok")
            assert found is not None
            assert found.platform is Platform.TIKTOK

            missing = uow.watch_accounts.get_by_handle(Platform.YOUTUBE, "@tiktok")
            assert missing is None

    def test_duplicate_platform_handle_raises(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.watch_accounts.add(_sample_account())

        with SqliteUnitOfWork(engine) as uow, pytest.raises(StorageError):
            uow.watch_accounts.add(_sample_account())

    def test_same_handle_different_platforms_ok(self, engine: Engine) -> None:
        # Same handle, different platforms — allowed by compound UNIQUE
        with SqliteUnitOfWork(engine) as uow:
            uow.watch_accounts.add(
                _sample_account(platform=Platform.YOUTUBE, handle="@shared")
            )
            uow.watch_accounts.add(
                _sample_account(
                    platform=Platform.TIKTOK,
                    handle="@shared",
                    url="https://www.tiktok.com/@shared",
                )
            )

        with SqliteUnitOfWork(engine) as uow:
            assert len(uow.watch_accounts.list_all()) == 2

    def test_list_all_orders_by_created_at(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.watch_accounts.add(
                _sample_account(handle="@first", url="https://example.com/first")
            )
            uow.watch_accounts.add(
                _sample_account(handle="@second", url="https://example.com/second")
            )
            uow.watch_accounts.add(
                _sample_account(handle="@third", url="https://example.com/third")
            )

        with SqliteUnitOfWork(engine) as uow:
            accounts = uow.watch_accounts.list_all()
            assert len(accounts) == 3
            handles = [a.handle for a in accounts]
            assert handles == ["@first", "@second", "@third"]

    def test_remove(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.watch_accounts.add(_sample_account())
            assert stored.id is not None

        with SqliteUnitOfWork(engine) as uow:
            uow.watch_accounts.remove(stored.id)  # type: ignore[arg-type]

        with SqliteUnitOfWork(engine) as uow:
            assert uow.watch_accounts.get(stored.id) is None  # type: ignore[arg-type]
            assert uow.watch_accounts.list_all() == []

    def test_remove_missing_is_noop(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            uow.watch_accounts.remove(999)  # should not raise

    def test_update_last_checked(self, engine: Engine) -> None:
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.watch_accounts.add(_sample_account())
            assert stored.id is not None
            assert stored.last_checked_at is None

            uow.watch_accounts.update_last_checked(
                stored.id, last_checked_at=UTC_NOW
            )

        with SqliteUnitOfWork(engine) as uow:
            fetched = uow.watch_accounts.get(stored.id)  # type: ignore[arg-type]
            assert fetched is not None
            assert fetched.last_checked_at is not None
            assert fetched.last_checked_at == UTC_NOW

    def test_update_last_checked_rejects_non_datetime(
        self, engine: Engine
    ) -> None:
        with SqliteUnitOfWork(engine) as uow:
            stored = uow.watch_accounts.add(_sample_account())
            assert stored.id is not None

        with SqliteUnitOfWork(engine) as uow, pytest.raises(StorageError):
            uow.watch_accounts.update_last_checked(
                stored.id, last_checked_at="not a datetime"
            )
