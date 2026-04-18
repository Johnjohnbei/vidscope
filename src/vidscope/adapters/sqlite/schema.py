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
    "frames",
    "init_db",
    "metadata",
    "pipeline_runs",
    "transcripts",
    "video_stats",
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

# M009: append-only engagement-counter snapshots (one row per probe).
# The UNIQUE constraint at (video_id, captured_at) with second resolution
# (D-01) ensures duplicate probes within the same second are silently
# ignored via ON CONFLICT DO NOTHING in the adapter.
video_stats = Table(
    "video_stats",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("view_count", Integer, nullable=True),
    Column("like_count", Integer, nullable=True),
    Column("repost_count", Integer, nullable=True),
    Column("comment_count", Integer, nullable=True),
    Column("save_count", Integer, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("video_id", "captured_at", name="uq_video_stats_video_id_captured_at"),
)


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
    guards itself the same way.

    M009: also calls :func:`_ensure_video_stats_table` so that pre-M009
    databases gain the ``video_stats`` table and its indexes on upgrade
    without requiring a separate migration command. The named indexes are
    created with ``IF NOT EXISTS`` so this is safe to call repeatedly.
    """
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_video_stats_table(conn)
        _ensure_video_stats_indexes(conn)


def _create_fts5(conn: Connection) -> None:
    """Execute the FTS5 virtual-table DDL on an existing connection."""
    conn.execute(text(_FTS5_CREATE_SQL))


def _ensure_video_stats_table(conn: Connection) -> None:
    """Idempotent migration: create the ``video_stats`` table if absent.

    Called by :func:`init_db` on every startup so pre-M009 databases are
    upgraded automatically. The function is a no-op when the table already
    exists (safe to call repeatedly).

    Indexes
    -------
    - ``idx_video_stats_video_id`` — speeds up ``WHERE video_id = ?`` queries.
    - ``idx_video_stats_captured_at`` — speeds up time-window queries.
    """
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }
    if "video_stats" in existing:
        return

    conn.execute(
        text(
            """
            CREATE TABLE video_stats (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id    INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                captured_at DATETIME NOT NULL,
                view_count  INTEGER,
                like_count  INTEGER,
                repost_count INTEGER,
                comment_count INTEGER,
                save_count  INTEGER,
                created_at  DATETIME NOT NULL,
                CONSTRAINT uq_video_stats_video_id_captured_at
                    UNIQUE (video_id, captured_at)
            )
            """
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_stats_video_id "
            "ON video_stats (video_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_stats_captured_at "
            "ON video_stats (captured_at)"
        )
    )


def _ensure_video_stats_indexes(conn: Connection) -> None:
    """Create named indexes on ``video_stats`` if they do not exist.

    Uses ``CREATE INDEX IF NOT EXISTS`` so this is safe to call on every
    startup regardless of whether the table was created by SQLAlchemy
    ``metadata.create_all`` or by :func:`_ensure_video_stats_table`.
    The ``CREATE INDEX IF NOT EXISTS`` syntax is idempotent.
    """
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_stats_video_id "
            "ON video_stats (video_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_stats_captured_at "
            "ON video_stats (captured_at)"
        )
    )


# Re-export a type alias used by tests that want to introspect row maps
# without coupling to SQLAlchemy types.
Row = dict[str, Any]
