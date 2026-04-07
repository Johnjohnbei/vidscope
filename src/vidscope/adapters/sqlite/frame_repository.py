"""SQLite implementation of :class:`FrameRepository`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import frames as frames_table
from vidscope.domain import Frame, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["FrameRepositorySQLite"]


class FrameRepositorySQLite:
    """Repository for :class:`Frame` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    def add_many(self, frames: list[Frame]) -> list[Frame]:
        """Insert every frame in order. Atomic: all rows land in the
        calling transaction or none do."""
        if not frames:
            return []

        payload = [_frame_to_row(frame) for frame in frames]
        try:
            # executemany semantics — a single statement with many
            # parameter tuples. Atomic within the open transaction.
            self._conn.execute(frames_table.insert(), payload)
        except Exception as exc:
            raise StorageError(
                f"failed to insert {len(frames)} frames for video "
                f"{frames[0].video_id}: {exc}",
                cause=exc,
            ) from exc

        # Return the frames as stored by re-querying the video's frame
        # list ordered by timestamp — the safer alternative to guessing
        # ids from the last insert.
        return self.list_for_video(frames[0].video_id)

    def list_for_video(self, video_id: VideoId) -> list[Frame]:
        rows = (
            self._conn.execute(
                select(frames_table)
                .where(frames_table.c.video_id == int(video_id))
                .order_by(frames_table.c.timestamp_ms.asc())
            )
            .mappings()
            .all()
        )
        return [_row_to_frame(row) for row in rows]


def _frame_to_row(frame: Frame) -> dict[str, Any]:
    return {
        "video_id": int(frame.video_id),
        "image_key": frame.image_key,
        "timestamp_ms": int(frame.timestamp_ms),
        "is_keyframe": bool(frame.is_keyframe),
        "created_at": frame.created_at or datetime.now(UTC),
    }


def _row_to_frame(row: Any) -> Frame:
    data = cast("dict[str, Any]", dict(row))
    return Frame(
        id=int(data["id"]),
        video_id=VideoId(int(data["video_id"])),
        image_key=str(data["image_key"]),
        timestamp_ms=int(data["timestamp_ms"]),
        is_keyframe=bool(data["is_keyframe"]),
        created_at=_ensure_utc(data.get("created_at")),
    )


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
