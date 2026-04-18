"""SQLite implementation of :class:`LinkRepository`.

Uses SQLAlchemy Core exclusively. Links are stored with dedup on
``(video_id, normalized_url, source)`` — the same URL from description
and from transcript is TWO rows (intentional per R044 "source origin").
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import links as links_table
from vidscope.domain import Link, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["LinkRepositorySQLite"]


class LinkRepositorySQLite:
    """Repository for :class:`Link` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def add_many_for_video(
        self, video_id: VideoId, links: list[Link]
    ) -> list[Link]:
        """Insert every link atomically with dedup on
        ``(normalized_url, source)`` within the call."""
        if not links:
            return []
        try:
            seen: set[tuple[str, str]] = set()
            payloads: list[dict[str, Any]] = []
            now = datetime.now(UTC)
            for ln in links:
                key = (ln.normalized_url, ln.source)
                if key in seen:
                    continue
                seen.add(key)
                payloads.append(
                    {
                        "video_id": int(video_id),
                        "url": ln.url,
                        "normalized_url": ln.normalized_url,
                        "source": ln.source,
                        "position_ms": ln.position_ms,
                        "created_at": now,
                    }
                )
            if not payloads:
                return []
            self._conn.execute(links_table.insert().values(payloads))
        except Exception as exc:
            raise StorageError(
                f"add_many_for_video failed for links of video "
                f"{int(video_id)}: {exc}",
                cause=exc,
            ) from exc
        # Return the stored rows with id populated (query back by
        # video_id — cheap because idx_links_video_id indexes it)
        return self.list_for_video(video_id)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_for_video(
        self, video_id: VideoId, *, source: str | None = None
    ) -> list[Link]:
        query = (
            select(links_table)
            .where(links_table.c.video_id == int(video_id))
            .order_by(links_table.c.id.asc())
        )
        if source is not None:
            query = query.where(links_table.c.source == source)
        rows = self._conn.execute(query).mappings().all()
        return [_row_to_link(row) for row in rows]

    def has_any_for_video(self, video_id: VideoId) -> bool:
        count = self._conn.execute(
            select(func.count())
            .select_from(links_table)
            .where(links_table.c.video_id == int(video_id))
        ).scalar()
        return bool(count and int(count) > 0)

    def find_video_ids_with_any_link(
        self, *, limit: int = 50
    ) -> list[VideoId]:
        rows = (
            self._conn.execute(
                select(links_table.c.video_id)
                .distinct()
                .order_by(links_table.c.video_id.desc())
                .limit(limit)
            )
            .all()
        )
        return [VideoId(int(row[0])) for row in rows]


# ---------------------------------------------------------------------------
# Row <-> entity translation
# ---------------------------------------------------------------------------


def _row_to_link(row: Any) -> Link:
    data = cast("dict[str, Any]", dict(row))
    return Link(
        id=int(data["id"]) if data.get("id") is not None else None,
        video_id=VideoId(int(data["video_id"])),
        url=str(data["url"]),
        normalized_url=str(data["normalized_url"]),
        source=str(data["source"]),
        position_ms=(
            int(data["position_ms"])
            if data.get("position_ms") is not None
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
