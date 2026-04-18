"""SQLite implementation of :class:`CollectionRepository` (M011/S02/R057).

Collection names are case-preserved (D3 M011 RESEARCH — unlike tags).
UNIQUE(name) at DB level is case-sensitive by default on SQLite.

Security (T-SQL-M011-02): all queries use SQLAlchemy Core binds.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import (
    collection_items as collection_items_table,
)
from vidscope.adapters.sqlite.schema import collections as collections_table
from vidscope.domain import Collection, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["CollectionRepositorySQLite"]


class CollectionRepositorySQLite:
    """Repository for :class:`Collection` + collection_items backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Collection CRUD
    # ------------------------------------------------------------------

    def create(self, name: str) -> Collection:
        stripped = name.strip()
        if not stripped:
            raise StorageError("collection name cannot be empty or whitespace-only")

        now = datetime.now(UTC)
        try:
            result = self._conn.execute(
                collections_table.insert().values(name=stripped, created_at=now)
            )
        except Exception as exc:  # IntegrityError on UNIQUE violation
            raise StorageError(
                f"collection {stripped!r} already exists or DB error: {exc}",
                cause=exc,
            ) from exc

        inserted_id = result.inserted_primary_key
        if not inserted_id or inserted_id[0] is None:  # pragma: no cover
            raise StorageError(f"insert returned no id for collection {stripped!r}")
        return Collection(id=int(inserted_id[0]), name=stripped, created_at=now)

    def get_by_name(self, name: str) -> Collection | None:
        stripped = name.strip()
        if not stripped:
            return None
        row = (
            self._conn.execute(
                select(collections_table).where(collections_table.c.name == stripped)
            )
            .mappings()
            .first()
        )
        return _row_to_collection(dict(row)) if row else None

    def list_all(self, *, limit: int = 1000) -> list[Collection]:
        rows = (
            self._conn.execute(
                select(collections_table)
                .order_by(collections_table.c.name.asc())
                .limit(max(1, int(limit)))
            )
            .mappings()
            .all()
        )
        return [_row_to_collection(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # collection_items (membership)
    # ------------------------------------------------------------------

    def add_video(self, collection_id: int, video_id: VideoId) -> None:
        now = datetime.now(UTC)
        stmt = sqlite_insert(collection_items_table).values(
            collection_id=int(collection_id),
            video_id=int(video_id),
            created_at=now,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["collection_id", "video_id"]
        )
        self._conn.execute(stmt)

    def remove_video(self, collection_id: int, video_id: VideoId) -> None:
        stmt = delete(collection_items_table).where(
            (collection_items_table.c.collection_id == int(collection_id))
            & (collection_items_table.c.video_id == int(video_id))
        )
        self._conn.execute(stmt)

    def list_videos(
        self, collection_id: int, *, limit: int = 1000
    ) -> list[VideoId]:
        stmt = (
            select(collection_items_table.c.video_id)
            .where(collection_items_table.c.collection_id == int(collection_id))
            .order_by(collection_items_table.c.created_at.desc())
            .limit(max(1, int(limit)))
        )
        rows = self._conn.execute(stmt).all()
        return [VideoId(int(r[0])) for r in rows]

    def list_collections_for_video(
        self, video_id: VideoId
    ) -> list[Collection]:
        stmt = (
            select(collections_table)
            .join(
                collection_items_table,
                collection_items_table.c.collection_id == collections_table.c.id,
            )
            .where(collection_items_table.c.video_id == int(video_id))
            .order_by(collections_table.c.name.asc())
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_row_to_collection(dict(r)) for r in rows]

    def list_video_ids_for_collection(
        self, name: str, *, limit: int = 1000
    ) -> list[VideoId]:
        stripped = name.strip()
        if not stripped:
            return []
        stmt = (
            select(collection_items_table.c.video_id)
            .join(
                collections_table,
                collections_table.c.id == collection_items_table.c.collection_id,
            )
            .where(collections_table.c.name == stripped)
            .order_by(collection_items_table.c.created_at.desc())
            .limit(max(1, int(limit)))
        )
        rows = self._conn.execute(stmt).all()
        return [VideoId(int(r[0])) for r in rows]


def _row_to_collection(row: dict[str, Any]) -> Collection:
    created_at = row.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return Collection(
        id=int(row["id"]),
        name=str(row["name"]),
        created_at=created_at,
    )
