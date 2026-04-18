"""SQLite implementation of :class:`HashtagRepository`.

Uses SQLAlchemy Core exclusively. Every method takes a
:class:`sqlalchemy.engine.Connection` (bound to an open transaction by
the unit of work) so hashtag writes can be grouped atomically with
video writes in the same :class:`IngestStage` transaction.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from vidscope.adapters.sqlite.schema import hashtags as hashtags_table
from vidscope.domain import Hashtag, VideoId
from vidscope.domain.errors import StorageError

_logger = logging.getLogger(__name__)

__all__ = ["HashtagRepositorySQLite"]


def _canonicalise_tag(tag: str) -> str:
    """Return the canonical form of ``tag``: lowercase + strip leading '#'.

    Applied consistently across write and lookup paths so callers can
    pass ``"#Cooking"`` or ``"cooking"`` interchangeably (per M007 D-04).
    """
    return tag.lower().lstrip("#").strip()


class HashtagRepositorySQLite:
    """Repository for :class:`Hashtag` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def replace_for_video(self, video_id: VideoId, tags: list[str]) -> None:
        """DELETE existing rows for ``video_id`` then INSERT every tag.

        Canonicalises each tag (lowercase + strip leading '#') and
        deduplicates within the call — empty strings after
        canonicalisation are dropped silently.
        """
        try:
            self._conn.execute(
                delete(hashtags_table).where(
                    hashtags_table.c.video_id == int(video_id)
                )
            )
            seen: set[str] = set()
            canonicalised: list[dict[str, Any]] = []
            now = datetime.now(UTC)
            for raw in tags:
                canon = _canonicalise_tag(raw)
                if not canon:
                    _logger.debug(
                        "tag %r became empty after canonicalisation for "
                        "video %d; skipping",
                        raw,
                        int(video_id),
                    )
                    continue
                if canon in seen:
                    continue
                seen.add(canon)
                canonicalised.append(
                    {
                        "video_id": int(video_id),
                        "tag": canon,
                        "created_at": now,
                    }
                )
            if canonicalised:
                self._conn.execute(
                    hashtags_table.insert().values(canonicalised)
                )
        except SQLAlchemyError as exc:
            raise StorageError(
                f"replace_for_video failed for hashtags of video "
                f"{int(video_id)}: {exc}",
                cause=exc,
            ) from exc

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_for_video(self, video_id: VideoId) -> list[Hashtag]:
        """Return every hashtag row for ``video_id`` ordered by id asc.

        Empty list on miss — never raises.
        """
        rows = (
            self._conn.execute(
                select(hashtags_table)
                .where(hashtags_table.c.video_id == int(video_id))
                .order_by(hashtags_table.c.id.asc())
            )
            .mappings()
            .all()
        )
        return [_row_to_hashtag(row) for row in rows]

    def find_video_ids_by_tag(
        self, tag: str, *, limit: int = 50
    ) -> list[VideoId]:
        """Return up to ``limit`` video ids whose hashtags include ``tag``.

        ``tag`` is canonicalised before comparison (per D-04).
        """
        canon = _canonicalise_tag(tag)
        if not canon:
            return []
        rows = (
            self._conn.execute(
                select(hashtags_table.c.video_id)
                .where(hashtags_table.c.tag == canon)
                .order_by(hashtags_table.c.id.desc())
                .limit(limit)
            )
            .all()
        )
        return [VideoId(int(row[0])) for row in rows]


# ---------------------------------------------------------------------------
# Row <-> entity translation
# ---------------------------------------------------------------------------


def _row_to_hashtag(row: Any) -> Hashtag:
    data = cast("dict[str, Any]", dict(row))
    return Hashtag(
        id=int(data["id"]) if data.get("id") is not None else None,
        video_id=VideoId(int(data["video_id"])),
        tag=str(data["tag"]),
        created_at=_ensure_utc(data.get("created_at")),
    )


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
