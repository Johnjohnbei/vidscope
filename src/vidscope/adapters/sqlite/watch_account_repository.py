"""SQLite implementation of :class:`WatchAccountRepository`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import watched_accounts as table
from vidscope.domain import Platform, WatchedAccount
from vidscope.domain.errors import StorageError

__all__ = ["WatchAccountRepositorySQLite"]


class WatchAccountRepositorySQLite:
    """Repository for :class:`WatchedAccount` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    def add(self, account: WatchedAccount) -> WatchedAccount:
        payload = _account_to_row(account)
        try:
            result = self._conn.execute(table.insert().values(**payload))
        except Exception as exc:
            raise StorageError(
                f"failed to insert watched account "
                f"{account.platform.value}/{account.handle}: {exc}",
                cause=exc,
            ) from exc

        inserted = result.inserted_primary_key
        if inserted is None or inserted[0] is None:
            raise StorageError("insert returned no account id")
        fetched = self.get(int(inserted[0]))
        return fetched if fetched is not None else account

    def get(self, account_id: int) -> WatchedAccount | None:
        row = (
            self._conn.execute(
                select(table).where(table.c.id == account_id)
            )
            .mappings()
            .first()
        )
        return _row_to_account(row) if row else None

    def get_by_handle(
        self, platform: Platform, handle: str
    ) -> WatchedAccount | None:
        row = (
            self._conn.execute(
                select(table).where(
                    table.c.platform == platform.value,
                    table.c.handle == handle,
                )
            )
            .mappings()
            .first()
        )
        return _row_to_account(row) if row else None

    def list_all(self) -> list[WatchedAccount]:
        rows = (
            self._conn.execute(select(table).order_by(table.c.created_at.asc()))
            .mappings()
            .all()
        )
        return [_row_to_account(row) for row in rows]

    def remove(self, account_id: int) -> None:
        try:
            self._conn.execute(delete(table).where(table.c.id == account_id))
        except Exception as exc:
            raise StorageError(
                f"failed to remove watched account {account_id}: {exc}",
                cause=exc,
            ) from exc

    def update_last_checked(
        self, account_id: int, *, last_checked_at: object
    ) -> None:
        if not isinstance(last_checked_at, datetime):
            raise StorageError(
                f"last_checked_at must be a datetime, got {type(last_checked_at)}"
            )
        try:
            self._conn.execute(
                update(table)
                .where(table.c.id == account_id)
                .values(last_checked_at=_ensure_utc_for_write(last_checked_at))
            )
        except Exception as exc:
            raise StorageError(
                f"failed to update last_checked_at for account {account_id}: {exc}",
                cause=exc,
            ) from exc


def _account_to_row(account: WatchedAccount) -> dict[str, Any]:
    return {
        "platform": account.platform.value,
        "handle": account.handle,
        "url": account.url,
        "created_at": account.created_at or datetime.now(UTC),
        "last_checked_at": (
            _ensure_utc_for_write(account.last_checked_at)
            if account.last_checked_at is not None
            else None
        ),
    }


def _row_to_account(row: Any) -> WatchedAccount:
    data = cast("dict[str, Any]", dict(row))
    return WatchedAccount(
        id=int(data["id"]),
        platform=Platform(data["platform"]),
        handle=str(data["handle"]),
        url=str(data["url"]),
        created_at=_ensure_utc_for_read(data.get("created_at")),
        last_checked_at=_ensure_utc_for_read(data.get("last_checked_at")),
    )


def _ensure_utc_for_write(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ensure_utc_for_read(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
