"""SQLite implementation of :class:`TagRepository` (M011/S02/R057).

Tag names are normalised to lowercase-stripped before INSERT/SELECT.
UNIQUE(name) at the DB level prevents duplicates.

Security (T-SQL-M011-02): all queries use SQLAlchemy Core parameterised
binds. No string interpolation, no f-strings inside execute().
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import (
    tag_assignments as tag_assignments_table,
)
from vidscope.adapters.sqlite.schema import tags as tags_table
from vidscope.domain import Tag, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["TagRepositorySQLite"]


def _normalize(name: str) -> str:
    """Lowercase + strip. Empty result is a domain error (caller raises)."""
    return name.strip().lower()


class TagRepositorySQLite:
    """Repository for :class:`Tag` and tag_assignments backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Tag CRUD
    # ------------------------------------------------------------------

    def get_or_create(self, name: str) -> Tag:
        normalized = _normalize(name)
        if not normalized:
            raise StorageError(
                f"tag name cannot be empty or whitespace-only (got {name!r})"
            )
        # Try to SELECT first (happy path avoids ON CONFLICT)
        existing = self.get_by_name(normalized)
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        stmt = sqlite_insert(tags_table).values(name=normalized, created_at=now)
        stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
        self._conn.execute(stmt)
        # Re-fetch (insert may have been a no-op if a concurrent writer won)
        row = (
            self._conn.execute(
                select(tags_table).where(tags_table.c.name == normalized)
            )
            .mappings()
            .first()
        )
        if row is None:  # pragma: no cover
            raise StorageError(f"tag {normalized!r} missing after insert")
        return _row_to_tag(dict(row))

    def get_by_name(self, name: str) -> Tag | None:
        normalized = _normalize(name)
        if not normalized:
            return None
        row = (
            self._conn.execute(
                select(tags_table).where(tags_table.c.name == normalized)
            )
            .mappings()
            .first()
        )
        return _row_to_tag(dict(row)) if row else None

    def list_all(self, *, limit: int = 1000) -> list[Tag]:
        rows = (
            self._conn.execute(
                select(tags_table)
                .order_by(tags_table.c.name.asc())
                .limit(max(1, int(limit)))
            )
            .mappings()
            .all()
        )
        return [_row_to_tag(dict(r)) for r in rows]

    def list_for_video(self, video_id: VideoId) -> list[Tag]:
        stmt = (
            select(tags_table)
            .join(
                tag_assignments_table,
                tag_assignments_table.c.tag_id == tags_table.c.id,
            )
            .where(tag_assignments_table.c.video_id == int(video_id))
            .order_by(tags_table.c.name.asc())
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_row_to_tag(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # tag_assignments (many-to-many)
    # ------------------------------------------------------------------

    def assign(self, video_id: VideoId, tag_id: int) -> None:
        now = datetime.now(UTC)
        stmt = sqlite_insert(tag_assignments_table).values(
            video_id=int(video_id), tag_id=int(tag_id), created_at=now,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["video_id", "tag_id"]
        )
        self._conn.execute(stmt)

    def unassign(self, video_id: VideoId, tag_id: int) -> None:
        stmt = delete(tag_assignments_table).where(
            (tag_assignments_table.c.video_id == int(video_id))
            & (tag_assignments_table.c.tag_id == int(tag_id))
        )
        self._conn.execute(stmt)

    def list_video_ids_for_tag(
        self, name: str, *, limit: int = 1000
    ) -> list[VideoId]:
        normalized = _normalize(name)
        if not normalized:
            return []
        stmt = (
            select(tag_assignments_table.c.video_id)
            .join(tags_table, tags_table.c.id == tag_assignments_table.c.tag_id)
            .where(tags_table.c.name == normalized)
            .order_by(tag_assignments_table.c.created_at.desc())
            .limit(max(1, int(limit)))
        )
        rows = self._conn.execute(stmt).all()
        return [VideoId(int(r[0])) for r in rows]


def _row_to_tag(row: dict[str, Any]) -> Tag:
    created_at = row.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return Tag(
        id=int(row["id"]),
        name=str(row["name"]),
        created_at=created_at,
    )
