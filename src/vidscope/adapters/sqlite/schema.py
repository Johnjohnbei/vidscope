"""SQLAlchemy Core schema + FTS5 virtual table for VidScope.

Design notes
------------

- **Core, not ORM.** Every table is a :class:`sqlalchemy.Table`. Queries
  go through ``select()`` / ``insert()`` / ``update()``. Generated SQL
  stays transparent and a future Postgres migration is a mechanical
  exercise.

- **FTS5 via raw DDL.** SQLAlchemy Core has no native type for SQLite's
  ``CREATE VIRTUAL TABLE ... USING fts5(...)``. We execute the DDL as a
  raw statement in :func:`init_db`. The FTS5 table is populated
  explicitly from the :class:`SearchIndexSQLite` adapter rather than via
  triggers, so the adapter's public API is the single source of truth
  for which rows are searchable.

- **One search index for transcripts and analyses.** A single FTS5 table
  ``search_index`` with unindexed ``video_id`` and ``source`` columns
  plus an indexed ``text`` column covers both. ``source`` is one of
  ``'transcript'`` or ``'analysis_summary'``.

- **Idempotent init.** :func:`init_db` uses ``CREATE TABLE IF NOT EXISTS``
  (via ``metadata.create_all``) and ``CREATE VIRTUAL TABLE IF NOT
  EXISTS`` for the FTS5 table. Running it twice is a no-op.

- **Timestamps are UTC-aware.** The ``DateTime(timezone=True)`` column
  type plus a default of ``datetime.now(timezone.utc)`` guarantees every
  row carries a timezone-aware timestamp. SQLite stores them as ISO
  strings; the Core layer round-trips them as aware datetimes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.engine import Connection

__all__ = [
    "analyses",
    "creators",
    "frames",
    "hashtags",
    "init_db",
    "mentions",
    "metadata",
    "pipeline_runs",
    "transcripts",
    "videos",
    "watch_refreshes",
    "watched_accounts",
]


metadata = MetaData()


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp. Default for created_at columns."""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

videos = Table(
    "videos",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("platform", String(32), nullable=False),
    Column("platform_id", String(128), nullable=False, unique=True),
    Column("url", Text, nullable=False),
    Column("author", String(255), nullable=True),
    Column("title", Text, nullable=True),
    Column("duration", Float, nullable=True),
    Column("upload_date", String(32), nullable=True),
    Column("view_count", Integer, nullable=True),
    Column("media_key", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    Column(
        "creator_id",
        Integer,
        ForeignKey("creators.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("description", Text, nullable=True),
    Column("music_track", String(255), nullable=True),
    Column("music_artist", String(255), nullable=True),
)

transcripts = Table(
    "transcripts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("language", String(16), nullable=False),
    Column("full_text", Text, nullable=False, default=""),
    Column("segments", JSON, nullable=False, default=list),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
)

frames = Table(
    "frames",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("image_key", Text, nullable=False),
    Column("timestamp_ms", Integer, nullable=False),
    Column("is_keyframe", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
)

analyses = Table(
    "analyses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("provider", String(64), nullable=False),
    Column("language", String(16), nullable=False),
    Column("keywords", JSON, nullable=False, default=list),
    Column("topics", JSON, nullable=False, default=list),
    Column("score", Float, nullable=True),
    Column("summary", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
)

pipeline_runs = Table(
    "pipeline_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="SET NULL"),
        nullable=True,
    ),
    # Carries the original URL even when no videos row exists yet
    # (ingest-stage failure before platform_id is known).
    Column("source_url", Text, nullable=True),
    Column("phase", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("error", Text, nullable=True),
    Column("retry_count", Integer, nullable=False, default=0),
)

# M003: watched accounts and refresh history
watched_accounts = Table(
    "watched_accounts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("platform", String(32), nullable=False),
    Column("handle", String(255), nullable=False),
    Column("url", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    Column("last_checked_at", DateTime(timezone=True), nullable=True),
    # Compound UNIQUE on (platform, handle) — different platforms may
    # share the same handle ("@tiktok" exists on both TikTok and as
    # an Instagram handle), same platform cannot.
    UniqueConstraint("platform", "handle", name="uq_watched_accounts_platform_handle"),
)

watch_refreshes = Table(
    "watch_refreshes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("started_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("accounts_checked", Integer, nullable=False, default=0),
    Column("new_videos_ingested", Integer, nullable=False, default=0),
    Column("errors", JSON, nullable=False, default=list),
)


# M006: creators registry
creators = Table(
    "creators",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("platform", String(32), nullable=False),
    Column("platform_user_id", String(255), nullable=False),
    Column("handle", String(255), nullable=True),          # non-unique (D-01)
    Column("display_name", Text, nullable=True),
    Column("profile_url", Text, nullable=True),
    Column("avatar_url", Text, nullable=True),             # URL string only (D-05)
    Column("follower_count", Integer, nullable=True),      # scalar (D-04)
    Column("is_verified", Boolean, nullable=True),
    Column("is_orphan", Boolean, nullable=False, default=False),
    Column("first_seen_at", DateTime(timezone=True), nullable=True),
    Column("last_seen_at", DateTime(timezone=True), nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    ),
    # Compound UNIQUE on (platform, platform_user_id) — D-01 canonical
    # identity. Same uploader_id on different platforms is allowed
    # (no cross-platform identity resolution in M006).
    UniqueConstraint(
        "platform",
        "platform_user_id",
        name="uq_creators_platform_user_id",
    ),
)

# Indexes on both sides of the creator<->video relationship.
Index("idx_creators_handle", creators.c.platform, creators.c.handle)
Index("idx_videos_creator_id", videos.c.creator_id)

# M007: hashtag side table (D-05)
hashtags = Table(
    "hashtags",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # Canonical lowercase form without the leading "#" (D-04 exact match).
    Column("tag", String(255), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    ),
)
Index("idx_hashtags_video_id", hashtags.c.video_id)
Index("idx_hashtags_tag", hashtags.c.tag)

# M007: mention side table (D-03, D-05). handle is canonical lowercase
# without the leading "@". No creator_id FK (per D-03) — mention↔creator
# linkage derivable via JOIN in M011 only.
mentions = Table(
    "mentions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("handle", String(255), nullable=False),
    Column("platform", String(32), nullable=True),  # Platform | None (D-03)
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    ),
)
Index("idx_mentions_video_id", mentions.c.video_id)
Index("idx_mentions_handle", mentions.c.handle)


# ---------------------------------------------------------------------------
# FTS5 virtual table DDL
# ---------------------------------------------------------------------------

# ``video_id`` and ``source`` are UNINDEXED so they are stored but not
# tokenized — we use them as filter/metadata columns. ``text`` is the
# only tokenized column. The unicode61 tokenizer with diacritic removal
# handles French and English correctly.
_FTS5_CREATE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    video_id UNINDEXED,
    source UNINDEXED,
    text,
    tokenize = 'unicode61 remove_diacritics 2'
)
"""


def init_db(engine: Engine) -> None:
    """Create every table and the FTS5 virtual table. Idempotent.

    Safe to call on every startup — :meth:`MetaData.create_all` uses
    ``CREATE TABLE IF NOT EXISTS`` under the hood, and the FTS5 DDL
    plus the ``_ensure_*`` helpers both guard themselves against
    double-execution on upgraded DBs.
    """
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_videos_creator_id(conn)
        _ensure_videos_metadata_columns(conn)


def _create_fts5(conn: Connection) -> None:
    """Execute the FTS5 virtual-table DDL on an existing connection."""
    conn.execute(text(_FTS5_CREATE_SQL))


def _ensure_videos_creator_id(conn: Connection) -> None:
    """Add ``videos.creator_id`` on upgraded databases. Idempotent.

    M006/S01 adds a nullable FK column ``videos.creator_id``. On fresh
    installs the Core ``metadata.create_all`` path declares the column
    inline (see the ``videos`` Table definition above). On pre-M006
    databases the ``videos`` table already exists, so ``create_all``
    is a no-op — we must explicitly ALTER it.

    SQLite supports ``ALTER TABLE ADD COLUMN ... REFERENCES`` as of
    3.26 (2018). The inline ``ON DELETE SET NULL`` is honored because
    ``PRAGMA foreign_keys`` is enabled on every connection by
    ``sqlite_engine._apply_sqlite_pragmas``.
    """
    cols = {
        row[1]
        for row in conn.execute(text("PRAGMA table_info(videos)"))
    }
    if "creator_id" in cols:
        return
    conn.execute(
        text(
            "ALTER TABLE videos ADD COLUMN creator_id INTEGER "
            "REFERENCES creators(id) ON DELETE SET NULL"
        )
    )


def _ensure_videos_metadata_columns(conn: Connection) -> None:
    """Add M007 metadata columns on upgraded databases. Idempotent.

    M007/S01 adds three nullable columns on ``videos``: ``description``,
    ``music_track``, ``music_artist`` (per D-01 — no side entity). On
    fresh installs the Core ``metadata.create_all`` path declares the
    columns inline (see the ``videos`` Table definition above). On
    pre-M007 databases the ``videos`` table already exists, so
    ``create_all`` is a no-op — we must explicitly ALTER it for each
    missing column.
    """
    cols = {
        row[1]
        for row in conn.execute(text("PRAGMA table_info(videos)"))
    }
    if "description" not in cols:
        conn.execute(text("ALTER TABLE videos ADD COLUMN description TEXT"))
    if "music_track" not in cols:
        conn.execute(
            text("ALTER TABLE videos ADD COLUMN music_track VARCHAR(255)")
        )
    if "music_artist" not in cols:
        conn.execute(
            text("ALTER TABLE videos ADD COLUMN music_artist VARCHAR(255)")
        )


# Re-export a type alias used by tests that want to introspect row maps
# without coupling to SQLAlchemy types.
Row = dict[str, Any]
