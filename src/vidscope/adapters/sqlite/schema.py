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
    "collection_items",
    "collections",
    "creators",
    "frame_texts",
    "frames",
    "hashtags",
    "init_db",
    "links",
    "mentions",
    "metadata",
    "pipeline_runs",
    "tag_assignments",
    "tags",
    "transcripts",
    "video_stats",
    "video_tracking",
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
    Column("creator_id", Integer, ForeignKey("creators.id"), nullable=True),
    Column("thumbnail_key", Text, nullable=True),
    Column("content_shape", String(32), nullable=True),
    Column("media_type", String(20), nullable=True),
    Column("description", Text, nullable=True),  # M012/S01 — full caption text (R060)
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
    # M010 additive columns (all nullable — D032 additive migration)
    Column("verticals", JSON, nullable=True),
    Column("information_density", Float, nullable=True),
    Column("actionability", Float, nullable=True),
    Column("novelty", Float, nullable=True),
    Column("production_quality", Float, nullable=True),
    Column("sentiment", String(32), nullable=True),
    Column("is_sponsored", Boolean, nullable=True),
    Column("content_type", String(64), nullable=True),
    Column("reasoning", Text, nullable=True),
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

# M011: user workflow overlay (one row per video, UNIQUE on video_id).
# Independent of `videos` — re-ingesting a video never touches this row
# (pipeline neutrality per D033 / Pitfall 5 of M011 RESEARCH).
video_tracking = Table(
    "video_tracking",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("status", String(32), nullable=False, default="new"),
    Column("starred", Boolean, nullable=False, default=False),
    Column("notes", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("video_id", name="uq_video_tracking_video_id"),
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


# M011/S02: tag namespace + many-to-many tag_assignments.
tags = Table(
    "tags",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("name", name="uq_tags_name"),
)

tag_assignments = Table(
    "tag_assignments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "tag_id",
        Integer,
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("video_id", "tag_id", name="uq_tag_assignments_video_tag"),
)

# M011/S02: user-curated collections + many-to-many collection_items.
collections = Table(
    "collections",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("name", name="uq_collections_name"),
)

collection_items = Table(
    "collection_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "collection_id",
        Integer,
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "video_id",
        Integer,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("collection_id", "video_id", name="uq_collection_items_coll_video"),
)


# M006: creator entities (one row per platform user id).
creators = Table(
    "creators",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("platform", String(32), nullable=False),
    Column("platform_user_id", String(255), nullable=False),
    Column("handle", String(255), nullable=True),
    Column("display_name", String(255), nullable=True),
    Column("profile_url", Text, nullable=True),
    Column("avatar_url", Text, nullable=True),
    Column("follower_count", Integer, nullable=True),
    Column("is_verified", Boolean, nullable=True),
    Column("is_orphan", Boolean, nullable=False, default=False),
    Column("first_seen_at", DateTime(timezone=True), nullable=True),
    Column("last_seen_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint("platform", "platform_user_id", name="uq_creators_platform_user_id"),
)

# M008: OCR-extracted text from frames.
frame_texts = Table(
    "frame_texts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("video_id", Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
    Column("frame_id", Integer, ForeignKey("frames.id", ondelete="CASCADE"), nullable=False),
    Column("text", Text, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("bbox", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
)

# M007: hashtags extracted from video metadata tags.
hashtags = Table(
    "hashtags",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("video_id", Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
    Column("tag", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
)

# M007: URLs extracted from video descriptions / transcripts.
links = Table(
    "links",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("video_id", Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
    Column("url", Text, nullable=False),
    Column("normalized_url", Text, nullable=False),
    Column("source", String(64), nullable=False),
    Column("position_ms", Integer, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
)

# M007: @handle mentions extracted from video descriptions.
mentions = Table(
    "mentions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("video_id", Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
    Column("handle", String(255), nullable=False),
    Column("platform", String(32), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
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

    M010: calls :func:`_ensure_analysis_v2_columns` so that pre-M010
    databases gain the 9 new nullable columns on the ``analyses`` table.

    M011/S02: calls :func:`_ensure_tags_collections_tables` so that pre-S02
    databases gain tags, tag_assignments, collections, collection_items.
    """
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_video_stats_table(conn)
        _ensure_video_stats_indexes(conn)
        _ensure_analysis_v2_columns(conn)
        _ensure_video_tracking_table(conn)  # M011/S01
        _ensure_tags_collections_tables(conn)  # M011/S02
        _ensure_m006_m007_m008_tables(conn)  # M006/M007/M008
        _ensure_visual_media_columns(conn)  # visual_intelligence + media_type
        _ensure_description_column(conn)      # M012/S01


def _create_fts5(conn: Connection) -> None:
    """Execute the FTS5 virtual-table DDL on an existing connection."""
    conn.execute(text(_FTS5_CREATE_SQL))
    conn.execute(text(
        "CREATE VIRTUAL TABLE IF NOT EXISTS frame_texts_fts USING fts5("
        "frame_text_id UNINDEXED, video_id UNINDEXED, text,"
        " tokenize = 'unicode61 remove_diacritics 2')"
    ))


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


def _add_columns_if_missing(
    conn: Connection,
    table_name: str,
    new_columns: list[tuple[str, str]],
    allowed_types: set[str],
) -> None:
    """Helper to idempotently add nullable columns to a table.

    Uses ``PRAGMA table_info`` to check which columns already exist,
    then issues ``ALTER TABLE ... ADD COLUMN`` for any missing ones.
    Validates column types against ``allowed_types`` to defend against
    DDL injection (T-SQL-M011-02). Idempotent — safe to call repeatedly.

    Parameters
    ----------
    conn
        SQLAlchemy connection (transaction scope).
    table_name
        Name of the target table.
    new_columns
        List of (column_name, column_type) tuples to add if missing.
    allowed_types
        Set of allowed DDL type strings. Any type not in this set
        raises ValueError.
    """
    existing_cols = {
        row[1]
        for row in conn.execute(text(f"PRAGMA table_info({table_name})"))
    }
    for col_name, col_type in new_columns:
        if col_name in existing_cols:
            continue
        if col_type not in allowed_types:
            raise ValueError(f"DDL type non autorisé : {col_type!r}")
        safe_col = col_name.replace('"', '""')  # SQL identifier escaping
        conn.execute(
            text(f'ALTER TABLE {table_name} ADD COLUMN "{safe_col}" {col_type}')
        )


def _ensure_analysis_v2_columns(conn: Connection) -> None:
    """M010 additive migration: ensure ``analyses`` carries the 9 new columns.

    Inspects ``PRAGMA table_info(analyses)`` to decide which ALTERs are
    needed — SQLite's ``ADD COLUMN`` without ``IF NOT EXISTS`` would fail
    on a second call, so we branch on the existing column set for maximum
    portability. Each ALTER adds a nullable column. Pre-M010 rows keep
    their existing values; new columns are NULL until reanalysis.

    Idempotent — safe to call on every startup.
    """
    # T-SQL-M011-02: DDL does not support bound parameters, so we defend by
    # (a) quoting the column identifier and (b) validating the type against an
    # explicit allowlist.  Both values are currently compile-time constants;
    # the guards ensure safety if the list is ever fed from external config.
    _ALLOWED_DDL_TYPES = {
        "JSON",
        "FLOAT",
        "BOOLEAN",
        "TEXT",
        "VARCHAR(32)",
        "VARCHAR(64)",
    }
    new_columns = [
        ("verticals", "JSON"),
        ("information_density", "FLOAT"),
        ("actionability", "FLOAT"),
        ("novelty", "FLOAT"),
        ("production_quality", "FLOAT"),
        ("sentiment", "VARCHAR(32)"),
        ("is_sponsored", "BOOLEAN"),
        ("content_type", "VARCHAR(64)"),
        ("reasoning", "TEXT"),
    ]
    _add_columns_if_missing(conn, "analyses", new_columns, _ALLOWED_DDL_TYPES)


def _ensure_video_tracking_table(conn: Connection) -> None:
    """M011/S01 migration: create ``video_tracking`` if absent. Idempotent.

    Called by :func:`init_db` on every startup so pre-M011 databases are
    upgraded automatically. No-op when the table already exists.

    Indexes
    -------
    - ``idx_video_tracking_status``: speeds up ``--status`` facet search (S03).
    - ``idx_video_tracking_starred``: speeds up ``--starred`` facet search (S03).
    """
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }
    if "video_tracking" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE video_tracking (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id   INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                    status     VARCHAR(32) NOT NULL DEFAULT 'new',
                    starred    BOOLEAN NOT NULL DEFAULT 0,
                    notes      TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_video_tracking_video_id UNIQUE (video_id)
                )
                """
            )
        )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_tracking_status "
            "ON video_tracking (status)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_video_tracking_starred "
            "ON video_tracking (starred)"
        )
    )


def _ensure_tags_collections_tables(conn: Connection) -> None:
    """M011/S02 migration: create tags + tag_assignments + collections +
    collection_items if absent. Idempotent.

    Created in strict order (Pitfall 2): tags, tag_assignments,
    collections, collection_items. Order matters because
    tag_assignments and collection_items have FKs to the preceding tables.
    """
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }

    if "tags" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE tags (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       VARCHAR(128) NOT NULL,
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_tags_name UNIQUE (name)
                )
                """
            )
        )

    if "tag_assignments" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE tag_assignments (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id   INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_tag_assignments_video_tag UNIQUE (video_id, tag_id)
                )
                """
            )
        )

    if "collections" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE collections (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       VARCHAR(255) NOT NULL,
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_collections_name UNIQUE (name)
                )
                """
            )
        )

    if "collection_items" not in existing:
        conn.execute(
            text(
                """
                CREATE TABLE collection_items (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
                    video_id      INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                    created_at    DATETIME NOT NULL,
                    CONSTRAINT uq_collection_items_coll_video UNIQUE (collection_id, video_id)
                )
                """
            )
        )

    # Indexes (idempotent via IF NOT EXISTS)
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_tag_assignments_video_id "
            "ON tag_assignments (video_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_tag_assignments_tag_id "
            "ON tag_assignments (tag_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_collection_items_collection_id "
            "ON collection_items (collection_id)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_collection_items_video_id "
            "ON collection_items (video_id)"
        )
    )


def _ensure_m006_m007_m008_tables(conn: Connection) -> None:
    """M006/M007/M008 migration: create creators, frame_texts, hashtags,
    links, mentions if absent. Also adds creator_id to videos. Idempotent."""
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
    }
    if "creators" not in existing:
        conn.execute(text("""
            CREATE TABLE creators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform VARCHAR(32) NOT NULL,
                platform_user_id VARCHAR(255) NOT NULL,
                handle VARCHAR(255),
                display_name VARCHAR(255),
                profile_url TEXT,
                avatar_url TEXT,
                follower_count INTEGER,
                is_verified BOOLEAN,
                is_orphan BOOLEAN NOT NULL DEFAULT 0,
                first_seen_at DATETIME,
                last_seen_at DATETIME,
                created_at DATETIME NOT NULL,
                CONSTRAINT uq_creators_platform_user_id UNIQUE (platform, platform_user_id)
            )"""))
    if "frame_texts" not in existing:
        conn.execute(text("""
            CREATE TABLE frame_texts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                frame_id INTEGER NOT NULL REFERENCES frames(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                confidence FLOAT NOT NULL,
                bbox TEXT,
                created_at DATETIME NOT NULL
            )"""))
    if "hashtags" not in existing:
        conn.execute(text("""
            CREATE TABLE hashtags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                tag VARCHAR(128) NOT NULL,
                created_at DATETIME NOT NULL
            )"""))
    if "links" not in existing:
        conn.execute(text("""
            CREATE TABLE links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                url TEXT NOT NULL,
                normalized_url TEXT NOT NULL,
                source VARCHAR(64) NOT NULL,
                position_ms INTEGER,
                created_at DATETIME NOT NULL
            )"""))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_links_video_id ON links (video_id)"
        ))
    if "mentions" not in existing:
        conn.execute(text("""
            CREATE TABLE mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                handle VARCHAR(255) NOT NULL,
                platform VARCHAR(32),
                created_at DATETIME NOT NULL
            )"""))

    # Additive migration: creator_id FK on videos (added in M006).
    video_cols = {
        row[1]
        for row in conn.execute(text("PRAGMA table_info(videos)"))
    }
    if "creator_id" not in video_cols:
        conn.execute(
            text(
                "ALTER TABLE videos ADD COLUMN creator_id INTEGER "
                "REFERENCES creators(id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_videos_creator_id "
                "ON videos (creator_id)"
            )
        )


def _ensure_visual_media_columns(conn: Connection) -> None:
    """Migration: add thumbnail_key, content_shape, media_type to videos.

    Idempotent — safe to call on every startup. Pre-existing rows keep
    NULL for all three columns; new ingest populates them from the
    downloader outcome.
    """
    new_columns = [
        ("thumbnail_key", "TEXT"),
        ("content_shape", "VARCHAR(32)"),
        ("media_type", "VARCHAR(20)"),
    ]
    _ALLOWED = {"TEXT", "VARCHAR(32)", "VARCHAR(20)"}
    _add_columns_if_missing(conn, "videos", new_columns, _ALLOWED)


def _ensure_description_column(conn: Connection) -> None:
    """M012/S01 migration: add description column to videos table.

    Idempotent — safe to call on every startup. Pre-existing rows get NULL;
    new ingest populates from downloader outcome (R060).
    """
    new_columns = [("description", "TEXT")]
    _ALLOWED = {"TEXT"}
    _add_columns_if_missing(conn, "videos", new_columns, _ALLOWED)


# Re-export a type alias used by tests that want to introspect row maps
# without coupling to SQLAlchemy types.
Row = dict[str, Any]
