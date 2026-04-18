"""SQLite implementation of :class:`CreatorRepository`.

Uses SQLAlchemy Core exclusively. Every method takes a
:class:`sqlalchemy.engine.Connection` (bound to an open transaction by
the unit of work) so creator writes can be grouped atomically with
video writes — this is the structural contract that makes the
write-through cache on ``videos.author`` (D-03) safe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import creators as creators_table
from vidscope.domain import Creator, CreatorId, Platform, PlatformUserId
from vidscope.domain.errors import StorageError

__all__ = ["CreatorRepositorySQLite"]


class CreatorRepositorySQLite:
    """Repository for :class:`Creator` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert(self, creator: Creator) -> Creator:
        """Insert or update the row matching ``(platform, platform_user_id)``.

        Uses SQLite's ``INSERT ... ON CONFLICT DO UPDATE`` with the
        compound index elements ``["platform", "platform_user_id"]``
        (D-01 canonical UNIQUE). ``created_at`` and ``first_seen_at``
        are preserved on update (archaeology); every other field is
        overwritten by the incoming row.
        """
        payload = _creator_to_row(creator)
        stmt = sqlite_insert(creators_table).values(**payload)
        # On conflict, update every field EXCEPT the ones that must
        # survive as historical anchors.
        preserved = {"created_at", "first_seen_at"}
        update_map = {
            key: stmt.excluded[key]
            for key in payload
            if key not in preserved
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["platform", "platform_user_id"],
            set_=update_map,
        )
        try:
            self._conn.execute(stmt)
        except Exception as exc:
            raise StorageError(
                f"upsert failed for creator "
                f"{creator.platform.value}/{creator.platform_user_id}: {exc}",
                cause=exc,
            ) from exc

        stored = self.find_by_platform_user_id(
            creator.platform, creator.platform_user_id
        )
        if stored is None:
            raise StorageError(
                f"upsert succeeded but row missing for "
                f"{creator.platform.value}/{creator.platform_user_id}"
            )
        return stored

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, creator_id: CreatorId) -> Creator | None:
        row = (
            self._conn.execute(
                select(creators_table).where(
                    creators_table.c.id == int(creator_id)
                )
            )
            .mappings()
            .first()
        )
        return _row_to_creator(row) if row else None

    def find_by_platform_user_id(
        self, platform: Platform, platform_user_id: PlatformUserId
    ) -> Creator | None:
        row = (
            self._conn.execute(
                select(creators_table).where(
                    creators_table.c.platform == platform.value,
                    creators_table.c.platform_user_id == str(platform_user_id),
                )
            )
            .mappings()
            .first()
        )
        return _row_to_creator(row) if row else None

    def find_by_handle(
        self, platform: Platform, handle: str
    ) -> Creator | None:
        # Most recently seen first: a renamed handle may collide with
        # an old row; newest wins for display.
        row = (
            self._conn.execute(
                select(creators_table)
                .where(
                    creators_table.c.platform == platform.value,
                    creators_table.c.handle == handle,
                )
                .order_by(creators_table.c.last_seen_at.desc().nulls_last())
                .limit(1)
            )
            .mappings()
            .first()
        )
        return _row_to_creator(row) if row else None

    def list_by_platform(
        self, platform: Platform, *, limit: int = 50
    ) -> list[Creator]:
        rows = (
            self._conn.execute(
                select(creators_table)
                .where(creators_table.c.platform == platform.value)
                .order_by(creators_table.c.last_seen_at.desc().nulls_last())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [_row_to_creator(row) for row in rows]

    def list_by_min_followers(
        self, min_count: int, *, limit: int = 50
    ) -> list[Creator]:
        rows = (
            self._conn.execute(
                select(creators_table)
                .where(creators_table.c.follower_count >= min_count)
                .order_by(creators_table.c.follower_count.desc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [_row_to_creator(row) for row in rows]

    def count(self) -> int:
        total = self._conn.execute(
            select(func.count()).select_from(creators_table)
        ).scalar()
        return int(total or 0)


# ---------------------------------------------------------------------------
# Row <-> entity translation
# ---------------------------------------------------------------------------


def _creator_to_row(creator: Creator) -> dict[str, Any]:
    """Translate a domain :class:`Creator` to a dict suitable for the
    ``creators`` table. ``id`` is omitted on insert.
    """
    now = datetime.now(UTC)
    return {
        "platform": creator.platform.value,
        "platform_user_id": str(creator.platform_user_id),
        "handle": creator.handle,
        "display_name": creator.display_name,
        "profile_url": creator.profile_url,
        "avatar_url": creator.avatar_url,
        "follower_count": creator.follower_count,
        "is_verified": creator.is_verified,
        "is_orphan": creator.is_orphan,
        "first_seen_at": (
            _ensure_utc_for_write(creator.first_seen_at)
            if creator.first_seen_at is not None
            else now
        ),
        "last_seen_at": (
            _ensure_utc_for_write(creator.last_seen_at)
            if creator.last_seen_at is not None
            else now
        ),
        "created_at": (
            _ensure_utc_for_write(creator.created_at)
            if creator.created_at is not None
            else now
        ),
    }


def _row_to_creator(row: Any) -> Creator:
    data = cast("dict[str, Any]", dict(row))
    return Creator(
        id=CreatorId(int(data["id"])),
        platform=Platform(data["platform"]),
        platform_user_id=PlatformUserId(str(data["platform_user_id"])),
        handle=data.get("handle"),
        display_name=data.get("display_name"),
        profile_url=data.get("profile_url"),
        avatar_url=data.get("avatar_url"),
        follower_count=data.get("follower_count"),
        is_verified=data.get("is_verified"),
        is_orphan=bool(data.get("is_orphan") or False),
        first_seen_at=_ensure_utc_for_read(data.get("first_seen_at")),
        last_seen_at=_ensure_utc_for_read(data.get("last_seen_at")),
        created_at=_ensure_utc_for_read(data.get("created_at")),
    )


def _ensure_utc_for_write(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ensure_utc_for_read(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
