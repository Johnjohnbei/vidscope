"""SQLite implementation of :class:`MentionRepository`.

Uses SQLAlchemy Core exclusively. Mentions are stored in a side table
keyed by ``(video_id, handle)`` with an optional ``platform`` column
(per M007 D-03). No ``creator_id`` FK — mention↔creator linkage is
deferred to M011.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import mentions as mentions_table
from vidscope.domain import Mention, Platform, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["MentionRepositorySQLite"]


def _canonicalise_handle(handle: str) -> str:
    """Return the canonical form of ``handle``: lowercase + strip '@'."""
    return handle.lower().lstrip("@").strip()


class MentionRepositorySQLite:
    """Repository for :class:`Mention` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    def replace_for_video(
        self, video_id: VideoId, mentions: list[Mention]
    ) -> None:
        """DELETE existing rows for ``video_id`` then INSERT every mention.

        Canonicalises each handle and deduplicates by ``(handle, platform)``
        within the call.
        """
        try:
            self._conn.execute(
                delete(mentions_table).where(
                    mentions_table.c.video_id == int(video_id)
                )
            )
            seen: set[tuple[str, str | None]] = set()
            payloads: list[dict[str, Any]] = []
            now = datetime.now(UTC)
            for m in mentions:
                canon = _canonicalise_handle(m.handle)
                if not canon:
                    continue
                plat_value = m.platform.value if m.platform is not None else None
                key = (canon, plat_value)
                if key in seen:
                    continue
                seen.add(key)
                payloads.append(
                    {
                        "video_id": int(video_id),
                        "handle": canon,
                        "platform": plat_value,
                        "created_at": now,
                    }
                )
            if payloads:
                self._conn.execute(
                    mentions_table.insert().values(payloads)
                )
        except Exception as exc:
            raise StorageError(
                f"replace_for_video failed for mentions of video "
                f"{int(video_id)}: {exc}",
                cause=exc,
            ) from exc

    def list_for_video(self, video_id: VideoId) -> list[Mention]:
        """Return every mention row for ``video_id`` ordered by id asc.

        Empty list on miss — never raises.
        """
        rows = (
            self._conn.execute(
                select(mentions_table)
                .where(mentions_table.c.video_id == int(video_id))
                .order_by(mentions_table.c.id.asc())
            )
            .mappings()
            .all()
        )
        return [_row_to_mention(row) for row in rows]

    def find_video_ids_by_handle(
        self, handle: str, *, limit: int = 50
    ) -> list[VideoId]:
        """Return up to ``limit`` video ids mentioning ``handle``.

        ``handle`` is canonicalised before comparison (per D-04).
        """
        canon = _canonicalise_handle(handle)
        if not canon:
            return []
        rows = (
            self._conn.execute(
                select(mentions_table.c.video_id)
                .where(mentions_table.c.handle == canon)
                .order_by(mentions_table.c.id.desc())
                .limit(limit)
            )
            .all()
        )
        return [VideoId(int(row[0])) for row in rows]


def _row_to_mention(row: Any) -> Mention:
    data = cast("dict[str, Any]", dict(row))
    plat_raw = data.get("platform")
    platform = Platform(plat_raw) if plat_raw else None
    return Mention(
        id=int(data["id"]) if data.get("id") is not None else None,
        video_id=VideoId(int(data["video_id"])),
        handle=str(data["handle"]),
        platform=platform,
        created_at=_ensure_utc(data.get("created_at")),
    )


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
