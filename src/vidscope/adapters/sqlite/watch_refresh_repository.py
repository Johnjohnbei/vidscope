"""SQLite implementation of :class:`WatchRefreshRepository`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import watch_refreshes as table
from vidscope.domain import WatchRefresh
from vidscope.domain.errors import StorageError

__all__ = ["WatchRefreshRepositorySQLite"]


class WatchRefreshRepositorySQLite:
    """Repository for :class:`WatchRefresh` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    def add(self, refresh: WatchRefresh) -> WatchRefresh:
        payload = _refresh_to_row(refresh)
        try:
            result = self._conn.execute(table.insert().values(**payload))
        except Exception as exc:
            raise StorageError(
                f"failed to insert watch_refresh: {exc}",
                cause=exc,
            ) from exc

        inserted = result.inserted_primary_key
        if inserted is None or inserted[0] is None:
            raise StorageError("insert returned no refresh id")
        return self._get_by_id(int(inserted[0])) or refresh

    def list_recent(self, limit: int = 10) -> list[WatchRefresh]:
        rows = (
            self._conn.execute(
                select(table)
                .order_by(table.c.started_at.desc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [_row_to_refresh(row) for row in rows]

    def _get_by_id(self, refresh_id: int) -> WatchRefresh | None:
        row = (
            self._conn.execute(
                select(table).where(table.c.id == refresh_id)
            )
            .mappings()
            .first()
        )
        return _row_to_refresh(row) if row else None


def _refresh_to_row(refresh: WatchRefresh) -> dict[str, Any]:
    return {
        "started_at": _ensure_utc_for_write(refresh.started_at),
        "finished_at": (
            _ensure_utc_for_write(refresh.finished_at)
            if refresh.finished_at is not None
            else None
        ),
        "accounts_checked": int(refresh.accounts_checked),
        "new_videos_ingested": int(refresh.new_videos_ingested),
        "errors": list(refresh.errors),
    }


def _row_to_refresh(row: Any) -> WatchRefresh:
    data = cast("dict[str, Any]", dict(row))
    errors_raw = data.get("errors") or []
    return WatchRefresh(
        id=int(data["id"]),
        started_at=_ensure_utc_for_read(data["started_at"]),
        finished_at=(
            _ensure_utc_for_read(data["finished_at"])
            if data.get("finished_at") is not None
            else None
        ),
        accounts_checked=int(data["accounts_checked"]),
        new_videos_ingested=int(data["new_videos_ingested"]),
        errors=tuple(str(e) for e in errors_raw),
    )


def _ensure_utc_for_write(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ensure_utc_for_read(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
