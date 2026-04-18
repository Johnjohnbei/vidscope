"""SQLite implementation of :class:`FrameTextRepository`.

Uses SQLAlchemy Core for the ``frame_texts`` table and raw SQL for
the ``frame_texts_fts`` virtual table (FTS5 is not part of Core's
DDL vocabulary). Every ``add_many_for_frame`` call writes to BOTH
tables in the same transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from vidscope.adapters.sqlite.schema import frame_texts as frame_texts_table
from vidscope.domain import FrameText, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["FrameTextRepositorySQLite"]


class FrameTextRepositorySQLite:
    """Repository for :class:`FrameText` backed by SQLite + FTS5."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def add_many_for_frame(
        self,
        frame_id: int,
        video_id: VideoId,
        texts: list[FrameText],
    ) -> list[FrameText]:
        """INSERT frame_texts rows + sync frame_texts_fts. No-op on empty input."""
        if not texts:
            return []
        try:
            now = datetime.now(UTC)
            payloads: list[dict[str, Any]] = []
            for t in texts:
                payloads.append(
                    {
                        "video_id": int(video_id),
                        "frame_id": int(frame_id),
                        "text": t.text,
                        "confidence": float(t.confidence),
                        "bbox": t.bbox,
                        "created_at": now,
                    }
                )
            # Count pre-existing rows so WR-01 can target only newly inserted ones.
            count_before = len(self._list_by_frame(frame_id))
            self._conn.execute(
                frame_texts_table.insert().values(payloads)
            )
        except SQLAlchemyError as exc:
            raise StorageError(
                f"add_many_for_frame failed for frame {int(frame_id)}: {exc}",
                cause=exc,
            ) from exc

        # Re-query for ids; slice to newly inserted rows only (WR-01 + WR-05).
        # rowcount is dialect-unreliable for bulk inserts — the re-query is
        # the ground truth (WR-05).
        all_rows = self._list_by_frame(frame_id)
        inserted = all_rows[count_before:]
        if not inserted:
            raise StorageError(
                f"add_many_for_frame: insert acknowledged but no rows "
                f"retrieved for frame {int(frame_id)}"
            )
        # Sync into frame_texts_fts. Use raw SQL — FTS5 is not a Core
        # Table so we cannot use insert().values().
        for row in inserted:
            if row.id is None:
                continue
            self._conn.execute(
                text(
                    "INSERT INTO frame_texts_fts "
                    "(frame_text_id, video_id, text) "
                    "VALUES (:frame_text_id, :video_id, :text)"
                ),
                {
                    "frame_text_id": int(row.id),
                    "video_id": int(row.video_id),
                    "text": row.text,
                },
            )
        return inserted

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def _list_by_frame(self, frame_id: int) -> list[FrameText]:
        rows = (
            self._conn.execute(
                select(frame_texts_table)
                .where(frame_texts_table.c.frame_id == int(frame_id))
                .order_by(frame_texts_table.c.id.asc())
            )
            .mappings()
            .all()
        )
        return [_row_to_frame_text(row) for row in rows]

    def list_for_video(self, video_id: VideoId) -> list[FrameText]:
        rows = (
            self._conn.execute(
                select(frame_texts_table)
                .where(frame_texts_table.c.video_id == int(video_id))
                .order_by(
                    frame_texts_table.c.frame_id.asc(),
                    frame_texts_table.c.id.asc(),
                )
            )
            .mappings()
            .all()
        )
        return [_row_to_frame_text(row) for row in rows]

    def has_any_for_video(self, video_id: VideoId) -> bool:
        count = self._conn.execute(
            select(func.count())
            .select_from(frame_texts_table)
            .where(frame_texts_table.c.video_id == int(video_id))
        ).scalar()
        return bool(count and int(count) > 0)

    def find_video_ids_by_text(
        self, query: str, *, limit: int = 50
    ) -> list[VideoId]:
        """FTS5 MATCH on frame_texts_fts. Returns distinct video ids."""
        if not query.strip():
            return []
        try:
            rows = self._conn.execute(
                text(
                    "SELECT DISTINCT video_id FROM frame_texts_fts "
                    "WHERE frame_texts_fts MATCH :q "
                    "LIMIT :lim"
                ),
                {"q": query, "lim": int(limit)},
            ).all()
        except SQLAlchemyError as exc:
            raise StorageError(
                f"find_video_ids_by_text failed for query {query!r}: {exc}",
                cause=exc,
            ) from exc
        return [VideoId(int(row[0])) for row in rows]


# ---------------------------------------------------------------------------
# Row <-> entity translation
# ---------------------------------------------------------------------------


def _row_to_frame_text(row: Any) -> FrameText:
    data = cast("dict[str, Any]", dict(row))
    return FrameText(
        id=int(data["id"]) if data.get("id") is not None else None,
        video_id=VideoId(int(data["video_id"])),
        frame_id=int(data["frame_id"]),
        text=str(data["text"]),
        confidence=float(data["confidence"]),
        bbox=(
            str(data["bbox"])
            if data.get("bbox") is not None
            else None
        ),
        created_at=_ensure_utc(data.get("created_at")),
    )


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
