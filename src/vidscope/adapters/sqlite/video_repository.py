"""SQLite implementation of :class:`VideoRepository`.

Uses SQLAlchemy Core exclusively. Every method takes a
:class:`sqlalchemy.engine.Connection` (bound to an open transaction by
the unit of work) so writes can be grouped atomically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import videos as videos_table
from vidscope.domain import Creator, CreatorId, Platform, PlatformId, Video, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["VideoRepositorySQLite"]


class VideoRepositorySQLite:
    """Repository for :class:`Video` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def add(self, video: Video) -> Video:
        """Insert ``video`` as a new row. Raises :class:`StorageError` if
        the ``(platform, platform_id)`` unique constraint is violated."""
        payload = _video_to_row(video)
        try:
            result = self._conn.execute(videos_table.insert().values(**payload))
        except Exception as exc:  # SQLAlchemy wraps IntegrityError etc.
            raise StorageError(
                f"failed to insert video {video.platform_id}: {exc}",
                cause=exc,
            ) from exc

        inserted_id = result.inserted_primary_key
        if inserted_id is None or inserted_id[0] is None:
            raise StorageError(
                f"insert returned no primary key for video {video.platform_id}"
            )
        return self.get(VideoId(int(inserted_id[0]))) or video

    def upsert_by_platform_id(
        self, video: Video, creator: Creator | None = None
    ) -> Video:
        """Insert or update the row matching ``(platform, platform_id)``.

        See :class:`VideoRepository.upsert_by_platform_id` for the
        write-through cache contract on ``videos.author`` when ``creator``
        is provided (D-03).
        """
        payload = _video_to_row(video)

        # D-03 write-through: when a creator is passed, the repository
        # owns both `author` (denormalised cache) and `creator_id` (FK).
        # They ARE written in the same SQL statement → atomic.
        if creator is not None:
            if creator.display_name is not None:
                payload["author"] = creator.display_name
            if creator.id is not None:
                payload["creator_id"] = int(creator.id)

        stmt = sqlite_insert(videos_table).values(**payload)
        # On conflict, update every field except id and created_at.
        update_map = {
            key: stmt.excluded[key]
            for key in payload
            if key not in ("created_at",)
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["platform_id"],
            set_=update_map,
        )
        try:
            self._conn.execute(stmt)
        except Exception as exc:
            raise StorageError(
                f"upsert failed for video {video.platform_id}: {exc}",
                cause=exc,
            ) from exc

        stored = self.get_by_platform_id(video.platform, video.platform_id)
        if stored is None:
            raise StorageError(
                f"upsert succeeded but row missing for {video.platform_id}"
            )
        return stored

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, video_id: VideoId) -> Video | None:
        row = self._conn.execute(
            select(videos_table).where(videos_table.c.id == int(video_id))
        ).mappings().first()
        return _row_to_video(row) if row else None

    def get_by_platform_id(
        self, platform: Platform, platform_id: PlatformId
    ) -> Video | None:
        row = (
            self._conn.execute(
                select(videos_table).where(
                    videos_table.c.platform == platform.value,
                    videos_table.c.platform_id == str(platform_id),
                )
            )
            .mappings()
            .first()
        )
        return _row_to_video(row) if row else None

    def list_recent(self, limit: int = 20) -> list[Video]:
        rows = (
            self._conn.execute(
                select(videos_table)
                .order_by(videos_table.c.created_at.desc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [_row_to_video(row) for row in rows]

    def list_by_creator(
        self, creator_id: CreatorId, *, limit: int = 50
    ) -> list[Video]:
        """Return up to ``limit`` videos for ``creator_id``, newest first."""
        rows = (
            self._conn.execute(
                select(videos_table)
                .where(videos_table.c.creator_id == int(creator_id))
                .order_by(videos_table.c.created_at.desc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [_row_to_video(row) for row in rows]

    def count(self) -> int:
        total = self._conn.execute(
            select(func.count()).select_from(videos_table)
        ).scalar()
        return int(total or 0)


# ---------------------------------------------------------------------------
# Row <-> entity translation
# ---------------------------------------------------------------------------


def _video_to_row(video: Video) -> dict[str, Any]:
    """Translate a domain :class:`Video` to a dict suitable for the
    ``videos`` table. ``id`` is omitted on insert; ``created_at`` is set
    to now() when absent."""
    return {
        "platform": video.platform.value,
        "platform_id": str(video.platform_id),
        "url": video.url,
        "author": video.author,
        "title": video.title,
        "duration": video.duration,
        "upload_date": video.upload_date,
        "view_count": video.view_count,
        "media_key": video.media_key,
        "created_at": video.created_at or datetime.now(UTC),
    }


def _row_to_video(row: Any) -> Video:
    """Translate a SQLAlchemy row mapping to a domain :class:`Video`."""
    data = cast("dict[str, Any]", dict(row))
    return Video(
        id=VideoId(int(data["id"])),
        platform=Platform(data["platform"]),
        platform_id=PlatformId(str(data["platform_id"])),
        url=str(data["url"]),
        author=data.get("author"),
        title=data.get("title"),
        duration=data.get("duration"),
        upload_date=data.get("upload_date"),
        view_count=data.get("view_count"),
        media_key=data.get("media_key"),
        created_at=_ensure_utc(data.get("created_at")),
        creator_id=(
            CreatorId(int(data["creator_id"]))
            if data.get("creator_id") is not None
            else None
        ),
    )


def _ensure_utc(value: datetime | None) -> datetime | None:
    """Guarantee ``created_at`` reads back as timezone-aware UTC.

    SQLite's ``DateTime(timezone=True)`` returns aware datetimes on
    round-trip when SQLAlchemy recognizes the storage format. On older
    SQLite builds we may get naive datetimes; attach UTC explicitly.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
