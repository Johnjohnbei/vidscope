"""SQLite implementation of :class:`VideoStatsRepository`.

Append-only: rows are inserted with ON CONFLICT DO NOTHING on the
UNIQUE(video_id, captured_at) constraint. No UPDATE method exists on this
class — mutating a stats row is a domain violation (D031).

Security (T-SQL-01): all queries use SQLAlchemy Core parameterized
statements. ``video_id`` values are cast to ``int`` explicitly before use
so no caller can inject a non-integer type into the query.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import video_stats as video_stats_table
from vidscope.domain import VideoId, VideoStats

__all__ = ["VideoStatsRepositorySQLite"]


class VideoStatsRepositorySQLite:
    """Repository for :class:`VideoStats` backed by SQLite.

    All methods accept a :class:`sqlalchemy.engine.Connection` bound to
    an open transaction (provided by :class:`SqliteUnitOfWork`) so writes
    participate in the caller's atomic transaction.
    """

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Writes — append-only (no update method by design)
    # ------------------------------------------------------------------

    def append(self, stats: VideoStats) -> VideoStats:
        """Insert ``stats`` and return it with ``id`` populated.

        If a row with the same ``(video_id, captured_at)`` already exists,
        the insert is silently ignored (ON CONFLICT DO NOTHING) and the
        original persisted row is returned. This keeps the operation
        idempotent (D-01, D031 append-only invariant).

        Security: ``int(stats.video_id)`` cast prevents non-int injection.
        """
        payload = _entity_to_row(stats)
        stmt = (
            sqlite_insert(video_stats_table)
            .values(**payload)
            .on_conflict_do_nothing(
                index_elements=["video_id", "captured_at"]
            )
        )
        self._conn.execute(stmt)

        # Fetch the persisted row (may be the original if conflict occurred)
        existing = self.latest_for_video(stats.video_id)
        if existing is not None:
            # Return the row that matches captured_at exactly
            for row in self._rows_for_video(stats.video_id):
                entity = _row_to_entity(row)
                if entity.captured_at == stats.captured_at:
                    return entity
        # Fallback: return as-is (should not happen in practice)
        return stats

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_for_video(self, video_id: VideoId, *, limit: int = 100) -> list[VideoStats]:
        """Return up to ``limit`` snapshots for ``video_id``, oldest first.

        Ordered by ``captured_at`` ascending for direct use in velocity
        computation (T-INPUT-01: limit default bounds query size).
        """
        stmt = (
            select(video_stats_table)
            .where(video_stats_table.c.video_id == int(video_id))
            .order_by(video_stats_table.c.captured_at.asc())
            .limit(limit)
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [_row_to_entity(dict(row)) for row in rows]

    def latest_for_video(self, video_id: VideoId) -> VideoStats | None:
        """Return the most recent snapshot for ``video_id``, or ``None``."""
        stmt = (
            select(video_stats_table)
            .where(video_stats_table.c.video_id == int(video_id))
            .order_by(video_stats_table.c.captured_at.desc())
            .limit(1)
        )
        row = self._conn.execute(stmt).mappings().first()
        if row is None:
            return None
        return _row_to_entity(dict(row))

    def has_any_for_video(self, video_id: VideoId) -> bool:
        """Return ``True`` if at least one snapshot exists for ``video_id``."""
        stmt = (
            select(func.count())
            .select_from(video_stats_table)
            .where(video_stats_table.c.video_id == int(video_id))
        )
        count: int = self._conn.execute(stmt).scalar() or 0
        return count > 0

    def list_videos_with_min_snapshots(
        self, min_snapshots: int = 2, *, limit: int = 200
    ) -> list[VideoId]:
        """Return ids of videos that have at least ``min_snapshots`` rows.

        Used by the velocity-computation use case (S04) to identify videos
        eligible for trend analysis (T-INPUT-01: limit default bounds query).
        """
        stmt = (
            select(video_stats_table.c.video_id)
            .group_by(video_stats_table.c.video_id)
            .having(func.count(video_stats_table.c.id) >= min_snapshots)
            .limit(limit)
        )
        rows = self._conn.execute(stmt).all()
        return [VideoId(int(row[0])) for row in rows]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rows_for_video(self, video_id: VideoId) -> list[dict[str, Any]]:
        """Return all raw rows for ``video_id`` ordered by captured_at asc."""
        stmt = (
            select(video_stats_table)
            .where(video_stats_table.c.video_id == int(video_id))
            .order_by(video_stats_table.c.captured_at.asc())
        )
        return [dict(row) for row in self._conn.execute(stmt).mappings().all()]


# ---------------------------------------------------------------------------
# Row ↔ entity translation
# ---------------------------------------------------------------------------


def _entity_to_row(stats: VideoStats) -> dict[str, Any]:
    """Translate a :class:`VideoStats` entity to a DB row dict."""
    return {
        "video_id": int(stats.video_id),
        "captured_at": stats.captured_at,
        "view_count": stats.view_count,
        "like_count": stats.like_count,
        "repost_count": stats.repost_count,
        "comment_count": stats.comment_count,
        "save_count": stats.save_count,
        "created_at": datetime.now(UTC),
    }


def _row_to_entity(row: dict[str, Any]) -> VideoStats:
    """Translate a raw DB row dict to a :class:`VideoStats` entity.

    ``None`` counters are preserved as ``None`` (D-03 — never coerce to 0).
    ``captured_at`` is made UTC-aware if stored as naive datetime.
    """
    captured_at: datetime = row["captured_at"]
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=UTC)

    created_at: datetime | None = row.get("created_at")
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    return VideoStats(
        id=int(row["id"]),
        video_id=VideoId(int(row["video_id"])),
        captured_at=captured_at,
        view_count=row.get("view_count"),
        like_count=row.get("like_count"),
        repost_count=row.get("repost_count"),
        comment_count=row.get("comment_count"),
        save_count=row.get("save_count"),
        created_at=created_at,
    )
