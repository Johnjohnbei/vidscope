"""SQLite implementation of :class:`VideoTrackingRepository` (M011/S01/R056).

One row per video — UNIQUE on ``video_id``. The only write method is
``upsert``: callers never decide between INSERT/UPDATE because the
``ON CONFLICT(video_id) DO UPDATE`` handles both atomically.

Security (T-SQL-M011-01): all queries use SQLAlchemy Core parameterized
statements. ``video_id`` values are cast to ``int`` explicitly and enum
values via ``.value`` — no raw string interpolation touches the query.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import video_tracking as video_tracking_table
from vidscope.domain import TrackingStatus, VideoId, VideoTracking

__all__ = ["VideoTrackingRepositorySQLite"]


class VideoTrackingRepositorySQLite:
    """Repository for :class:`VideoTracking` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Writes — upsert only (D1 of M011 RESEARCH)
    # ------------------------------------------------------------------

    def upsert(self, tracking: VideoTracking) -> VideoTracking:
        """Insert or update the tracking row for ``tracking.video_id``.

        Uses ``ON CONFLICT(video_id) DO UPDATE`` (Pitfall 3 resolved):
        second call for the same ``video_id`` atomically replaces
        ``status``, ``starred``, ``notes``, ``updated_at``. ``created_at``
        is preserved on update (via ``excluded`` only on insert path).
        """
        now = datetime.now(UTC)
        payload = {
            "video_id": int(tracking.video_id),
            "status": tracking.status.value,
            "starred": bool(tracking.starred),
            "notes": tracking.notes,
            "created_at": tracking.created_at or now,
            "updated_at": now,
        }
        stmt = sqlite_insert(video_tracking_table).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["video_id"],
            set_={
                "status": stmt.excluded.status,
                "starred": stmt.excluded.starred,
                "notes": stmt.excluded.notes,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        self._conn.execute(stmt)

        existing = self.get_for_video(tracking.video_id)
        if existing is None:  # pragma: no cover — defensive
            return tracking
        return existing

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_for_video(self, video_id: VideoId) -> VideoTracking | None:
        stmt = (
            select(video_tracking_table)
            .where(video_tracking_table.c.video_id == int(video_id))
            .limit(1)
        )
        row = self._conn.execute(stmt).mappings().first()
        if row is None:
            return None
        return _row_to_entity(dict(row))

    def list_by_status(
        self, status: TrackingStatus, *, limit: int = 1000
    ) -> list[VideoTracking]:
        stmt = (
            select(video_tracking_table)
            .where(video_tracking_table.c.status == status.value)
            .order_by(video_tracking_table.c.updated_at.desc())
            .limit(max(1, int(limit)))
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_row_to_entity(dict(r)) for r in rows]

    def list_starred(self, *, limit: int = 1000) -> list[VideoTracking]:
        stmt = (
            select(video_tracking_table)
            .where(video_tracking_table.c.starred.is_(True))
            .order_by(video_tracking_table.c.updated_at.desc())
            .limit(max(1, int(limit)))
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_row_to_entity(dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Row <-> entity translation
# ---------------------------------------------------------------------------


def _row_to_entity(row: dict[str, Any]) -> VideoTracking:
    # Defensive enum parse — corrupted DB value -> default to NEW (T-DATA-01).
    status_raw = row.get("status")
    try:
        status = TrackingStatus(str(status_raw)) if status_raw else TrackingStatus.NEW
    except ValueError:
        status = TrackingStatus.NEW

    created_at = row.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    updated_at = row.get("updated_at")
    if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)

    return VideoTracking(
        id=int(row["id"]),
        video_id=VideoId(int(row["video_id"])),
        status=status,
        starred=bool(row.get("starred")),
        notes=row.get("notes"),
        created_at=created_at,
        updated_at=updated_at,
    )
