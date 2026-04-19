# Phase M011: Veille workflow layer — Research

**Researched:** 2026-04-18
**Domain:** Python hexagonal architecture — SQLite migrations, domain entities, repository pattern, CLI sub-apps, dynamic SQL query builder, export adapters
**Confidence:** HIGH (all findings verified against live codebase)

---

## Summary

M011 adds a personal workflow overlay (tracking, tags, collections, exports) on top of the existing immutable video content layer. The codebase is mature (M001–M010 done) with strong hexagonal architecture contracts enforced by import-linter. Every design decision has a clear precedent in the codebase.

The core challenge is **S03** (composable facetted search): joining `video_tracking`, `tags`, and `tag_assignments` into the existing FTS5 pipeline requires a dynamic query builder in the SQLite adapter. The `SearchVideosUseCase` currently does two-phase filtering (FTS5 + Python set intersection); M011/S03 must extend this pattern carefully to avoid breaking existing callers while adding 8 new facets.

The export adapters (S04) are architecturally clean: a `Protocol` in `ports/`, three concrete files in `adapters/export/`, and a new import-linter contract mirroring `config-adapter-is-self-contained`. The only external question is `python-frontmatter` — it is **not currently a dependency** and is not needed for Markdown writing (only for reading/parsing); the Markdown exporter can write YAML frontmatter manually using stdlib `yaml` (already present via `pyyaml`).

**Primary recommendation:** Follow existing patterns exactly. New entities use `@dataclass(frozen=True, slots=True)`. New migrations use `_ensure_*` functions in `schema.py`. New repos live in `adapters/sqlite/`. UoW gains three new repo attributes. Container gains no new fields beyond `unit_of_work` (it delegates to UoW). CLI sub-apps use `typer.Typer` registered on the root app in `app.py`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| R056 | Tracking + notes: `video_tracking` table with `status ENUM`, `starred bool`, `notes TEXT`, `SetVideoTrackingUseCase`, `vidscope review <id>` CLI | S01 findings: entity pattern, UoW extension, migration 010, CLI sub-app pattern |
| R057 | Tags + collections: `Tag`, `Collection`, `CollectionItem` entities, many-to-many tables, 6 use cases, `vidscope tag` + `vidscope collection` CLI | S02 findings: many-to-many in SQLAlchemy Core, entity design, CLI sub-app pattern |
| R058 | Facetted search across all dimensions: `--status`, `--starred`, `--tag`, `--collection` added to existing `--content-type`, `--min-actionability`, etc. | S03 findings: dynamic query builder approach, backward-compatibility strategy, SQL injection prevention |
| R059 | Export: `vidscope export --format json\|markdown\|csv`, `ExportLibraryUseCase`, `Exporter` Protocol, 3 concrete adapters, frozen schema doc | S04 findings: Protocol pattern in ports, self-contained adapter contract, pyyaml for YAML frontmatter |
</phase_requirements>

---

## Standard Stack

[VERIFIED: pyproject.toml + codebase inspection]

### Core (already in dependencies — no new installs for S01–S03)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy Core | `>=2.0,<3` | DB layer for new tables | Already used throughout; Core (not ORM) per project convention |
| typer | `>=0.20,<1` | CLI sub-apps | Already used; `Typer()` sub-app pattern matches `watch_app`, `cookies_app` |
| rich | `>=14.0,<15` | Terminal output | Already used; `Console()`, `Table()` pattern from `_support.py` |
| pyyaml | `>=6.0,<7` | YAML frontmatter in Markdown export | Already a dependency (`config/taxonomy.yaml` loader) |

### New dependency needed for S04 (Markdown export)
| Library | Decision | Reason |
|---------|----------|--------|
| `python-frontmatter` | **Do NOT add** | Only needed for *reading/parsing* YAML frontmatter. The Markdown exporter only *writes* — use `yaml.dump()` from the already-present `pyyaml`. This avoids a new dependency. The ROADMAP's test requirement "Markdown frontmatter parseable by python-frontmatter" means the *test* can install it as a dev-only dependency if needed, but the exporter itself has no runtime need. |

### Dev test dependency (if ROADMAP test coverage requires it)
| Library | Version | Where | Purpose |
|---------|---------|-------|---------|
| `python-frontmatter` | `>=1.0` | `[dependency-groups.dev]` in `pyproject.toml` | Validate exported Markdown is parseable in test suite only |

**Version verification:** [VERIFIED: `pip show` — `python-frontmatter` is NOT installed in project venv. `pyyaml 6.x` is present via the `pyyaml>=6.0,<7` dependency.]

**Installation (if dev dependency added):**
```bash
uv add --dev python-frontmatter
```

---

## Architecture Patterns

### Existing Layer Structure (verified)
[VERIFIED: `src/vidscope/` directory + `.importlinter`]

```
src/vidscope/
├── domain/
│   ├── entities.py       # frozen dataclasses — add VideoTracking, Tag, Collection
│   ├── values.py         # StrEnum, NewType — add TrackingStatus, TagId, CollectionId
│   └── errors.py         # DomainError hierarchy — no changes needed
├── ports/
│   ├── repositories.py   # Protocol repos — add VideoTrackingRepository, TagRepository, CollectionRepository
│   ├── unit_of_work.py   # UnitOfWork Protocol — add video_tracking, tags, collections attrs
│   └── exporter.py       # NEW — Exporter Protocol for S04
├── adapters/
│   ├── sqlite/
│   │   ├── schema.py     # Tables + _ensure_* migrations — add 3 new _ensure_* functions
│   │   ├── unit_of_work.py  # SqliteUnitOfWork — add 3 new repo attrs in __enter__
│   │   ├── video_tracking_repository.py  # NEW
│   │   ├── tag_repository.py             # NEW
│   │   └── collection_repository.py      # NEW
│   └── export/           # NEW submodule
│       ├── __init__.py
│       ├── json_exporter.py
│       ├── markdown_exporter.py
│       └── csv_exporter.py
├── application/
│   ├── use_cases/
│   │   ├── set_video_tracking.py      # NEW (S01)
│   │   ├── tag_video.py               # NEW (S02)
│   │   ├── untag_video.py             # NEW (S02)
│   │   ├── list_tags.py               # NEW (S02)
│   │   ├── create_collection.py       # NEW (S02)
│   │   ├── add_to_collection.py       # NEW (S02)
│   │   ├── remove_from_collection.py  # NEW (S02)
│   │   └── export_library.py          # NEW (S04)
│   └── search_videos.py   # EXTENDED — add status, starred, tag, collection facets
├── cli/
│   ├── app.py            # register review_command, tag_app, collection_app, export_command
│   └── commands/
│       ├── review.py      # NEW (S01)
│       ├── tags.py        # NEW (S02) — tag_app sub-app
│       ├── collections.py # NEW (S02) — collection_app sub-app
│       ├── search.py      # EXTENDED (S03) — add 4 new facet options
│       └── export.py      # NEW (S04)
└── infrastructure/
    └── container.py      # no new fields — UoW factory already covers new repos
```

### Pattern 1: Frozen Domain Entity (verified from `entities.py`)
**What:** `@dataclass(frozen=True, slots=True)` — immutable, slot-based, no I/O
**When to use:** Every new entity (VideoTracking, Tag, Collection)

```python
# Source: src/vidscope/domain/entities.py — VideoStats pattern
@dataclass(frozen=True, slots=True)
class VideoTracking:
    """User's workflow overlay for a single video.

    One row per video — UNIQUE on video_id. ``status`` defaults to NEW
    when the row is first created (auto-create on first access pattern).
    ``starred`` and ``notes`` are independent of ``status``.
    """
    video_id: VideoId
    status: TrackingStatus
    starred: bool = False
    notes: str | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

### Pattern 2: StrEnum Value Object (verified from `values.py`)
**What:** `class X(StrEnum)` — string values persist without translation tables, round-trip through JSON unchanged

```python
# Source: src/vidscope/domain/values.py — ContentType pattern
class TrackingStatus(StrEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    SAVED = "saved"
    ACTIONED = "actioned"
    IGNORED = "ignored"
    ARCHIVED = "archived"
```

### Pattern 3: Repository Protocol (verified from `ports/repositories.py`)
**What:** `@runtime_checkable class XRepository(Protocol)` — adapters implement; use cases bind to Protocol only

```python
# Source: src/vidscope/ports/repositories.py — VideoStatsRepository pattern
@runtime_checkable
class VideoTrackingRepository(Protocol):
    def upsert(self, tracking: VideoTracking) -> VideoTracking: ...
    def get_for_video(self, video_id: VideoId) -> VideoTracking | None: ...
    def list_by_status(self, status: TrackingStatus, *, limit: int = 1000) -> list[VideoTracking]: ...
    def list_starred(self, *, limit: int = 1000) -> list[VideoTracking]: ...
```

### Pattern 4: Idempotent Migration Function (verified from `schema.py`)
**What:** `_ensure_X(conn)` function called from `init_db()` — checks existing tables/columns, applies DDL only if absent

```python
# Source: src/vidscope/adapters/sqlite/schema.py — _ensure_video_stats_table pattern
def _ensure_video_tracking_table(conn: Connection) -> None:
    """M011/S01 migration: create video_tracking if absent. Idempotent."""
    existing = {
        row[0]
        for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    }
    if "video_tracking" in existing:
        return
    conn.execute(text("""
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
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_video_tracking_status ON video_tracking (status)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_video_tracking_starred ON video_tracking (starred)"
    ))
```

**Registration in `init_db()`:**
```python
def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_video_stats_table(conn)
        _ensure_video_stats_indexes(conn)
        _ensure_analysis_v2_columns(conn)
        # M011 additions:
        _ensure_video_tracking_table(conn)
        _ensure_tags_collections_tables(conn)  # S02
```

### Pattern 5: UoW Extension (verified from `unit_of_work.py` — port and adapter)
**What:** Add new repo Protocol attribute to `UnitOfWork` Protocol in `ports/unit_of_work.py`, then assign concrete instance in `SqliteUnitOfWork.__enter__`

```python
# In ports/unit_of_work.py — add after video_stats:
video_tracking: VideoTrackingRepository
tags: TagRepository
collections: CollectionRepository

# In adapters/sqlite/unit_of_work.py __enter__ — add:
self.video_tracking = VideoTrackingRepositorySQLite(self._connection)
self.tags = TagRepositorySQLite(self._connection)
self.collections = CollectionRepositorySQLite(self._connection)
```

**Container impact:** The `Container.unit_of_work` is already `UnitOfWorkFactory` — **no Container changes needed**. New repos are automatically available via `uow.video_tracking` etc.

### Pattern 6: CLI Sub-App (verified from `commands/watch.py` + `app.py`)
**What:** `typer.Typer(name="...", no_args_is_help=True, add_completion=False)` registered in `app.py` via `app.add_typer(x_app, name="x")`

```python
# Source: src/vidscope/cli/commands/watch.py
tag_app = typer.Typer(
    name="tag",
    help="Manage video tags (add, remove, list).",
    no_args_is_help=True,
    add_completion=False,
)

@tag_app.command("add")
def tag_add(video_id: int = typer.Argument(...), name: str = typer.Argument(...)) -> None:
    """Tag a video."""
    with handle_domain_errors():
        container = acquire_container()
        use_case = TagVideoUseCase(unit_of_work_factory=container.unit_of_work)
        ...
```

### Pattern 7: Dynamic SQL Query Builder (verified from `analysis_repository.py`)
**What:** Build `where_clauses = []`, append conditionals, call `stmt.where(and_(*where_clauses))` — all via SQLAlchemy Core parameterized binds, never string interpolation

```python
# Source: src/vidscope/adapters/sqlite/analysis_repository.py — list_by_filters
where_clauses = []
if status is not None:
    where_clauses.append(video_tracking_table.c.status == status.value)
if starred:
    where_clauses.append(video_tracking_table.c.starred == True)  # noqa: E712
if tag is not None:
    # Existence subquery — anti-join pattern
    tag_subq = (
        select(tag_assignments_table.c.video_id)
        .join(tags_table, tags_table.c.id == tag_assignments_table.c.tag_id)
        .where(tags_table.c.name == tag)  # parameterized bind
    )
    where_clauses.append(videos_table.c.id.in_(tag_subq))
```

### Pattern 8: Exporter Protocol + Self-Contained Adapter
**What:** `Protocol` in `ports/exporter.py` mirrors the `Analyzer` pattern; concrete adapters in `adapters/export/` mirror `adapters/llm/` self-containment rule

```python
# NEW: src/vidscope/ports/exporter.py
from typing import Protocol

class Exporter(Protocol):
    """Write a list of export records to an output stream or path."""
    def write(self, records: list[ExportRecord], out: "Path | None" = None) -> None: ...
```

**Import-linter new contract:**
```ini
[importlinter:contract:export-adapter-is-self-contained]
name = export adapter does not import other adapters
type = forbidden
source_modules =
    vidscope.adapters.export
forbidden_modules =
    vidscope.adapters.sqlite
    vidscope.adapters.fs
    vidscope.adapters.ytdlp
    vidscope.adapters.whisper
    vidscope.adapters.ffmpeg
    vidscope.adapters.heuristic
    vidscope.adapters.llm
    vidscope.infrastructure
    vidscope.application
    vidscope.pipeline
    vidscope.cli
    vidscope.mcp
```

### Anti-Patterns to Avoid

- **Adding columns to `videos` table:** D033 — videos table is immutable. All workflow state goes in separate tables with FK to videos.id.
- **String interpolation in SQL:** Every existing adapter uses SQLAlchemy Core bind params. Use `.where(col == value)` — never `f"WHERE col = '{value}'"`.
- **Mutating dataclass fields:** All entities use `frozen=True`. Return `replace(entity, field=new_value)` via `dataclasses.replace()`.
- **Importing infrastructure or adapters from application layer:** `application-has-no-adapters` contract forbids it. Use only ports.
- **Importing from cli in mcp or vice versa:** `mcp-has-no-adapters` contract.
- **Unbounded queries:** Every `list_*` method must have a `limit` parameter with a sensible default (1000 max).

---

## Don't Hand-Roll

[VERIFIED: pyproject.toml + existing adapters]

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter serialization | Custom frontmatter writer | `yaml.dump()` from `pyyaml` (already a dep) | Handles escaping, multiline, special chars |
| CSV serialization | Custom CSV writer | `csv.DictWriter` from stdlib | Handles quoting, encoding, dialects |
| JSON serialization | Custom JSON serializer | `json.dumps()` from stdlib | Already used throughout codebase |
| SQL injection prevention | Manual input sanitization | SQLAlchemy Core bind params | Structural, not fragile |
| Parameterized queries | `f"WHERE col = '{val}'"` | `stmt.where(col == val)` | SQLAlchemy Core handles binding |
| Many-to-many join | Custom join logic | SQLAlchemy `.join()` + subquery `.in_()` | See `analysis_repository.py` EXISTS pattern |

---

## Key Design Decisions (Resolved)

### D1: `VideoTracking` auto-create on first access

**Decision:** `upsert` semantics — `SetVideoTrackingUseCase` does `upsert` (INSERT OR REPLACE / ON CONFLICT DO UPDATE). When `get_for_video` returns `None`, the CLI's `review` command creates the row with the requested status. There is no implicit row creation on ingest.

**Rationale:** Keeps the tracking table sparse (only videos the user has explicitly reviewed). Does not clutter the table with auto-created rows for every ingested video.

**Repository method:** `upsert(tracking: VideoTracking) -> VideoTracking` — handles both insert and update atomically via `INSERT OR REPLACE` or `ON CONFLICT(video_id) DO UPDATE SET ...`. Returns entity with `id` populated.

### D2: TrackingStatus state machine

**Allowed transitions:** All transitions are valid — there is no enforced state machine at the DB or domain layer. The status field is a label, not a workflow gate. The ROADMAP says "document allowed state machine" meaning: document which transitions are semantically meaningful, but don't raise on "illegal" transitions. The user can set any status at any time.

**Rationale:** This is a personal tool (R032 single-user). Forcing `archived → new` to fail adds friction without safety benefit.

**Domain behavior to document:** The `TrackingStatus` docstring should list "typical flow": new → reviewed → saved|actioned|ignored → archived.

### D3: Tag name uniqueness and normalization

**Decision from ROADMAP:** "UNIQUE tag name global" — case-insensitive by normalization. The `TagRepository` normalizes tag names to lowercase on insert. The `UNIQUE` constraint on `tags.name` operates on the stored (already-lowercased) value.

**Implementation:** `TagRepositorySQLite.get_or_create(name)` normalizes `name.strip().lower()` before insert/lookup. This way `"Idea"`, `"IDEA"`, `"idea"` all map to the same row.

### D4: Collection cascade behavior

**Decision:** When a `Collection` is deleted → `ON DELETE CASCADE` on `collection_items.collection_id` removes all membership rows. When a video is removed from a collection (not deleted from the library) → `collection_items` row is deleted, `videos` row and `video_tracking` row are unaffected.

**SQL:** `collection_items` has two FKs: `collection_id REFERENCES collections(id) ON DELETE CASCADE` and `video_id REFERENCES videos(id) ON DELETE CASCADE`. So deleting a video from the library also removes it from all collections.

### D5: S03 SearchVideos extension strategy

**Current state:** `SearchVideosUseCase` does FTS5 search → Python set-filter using `allowed_video_ids` from `AnalysisRepository.list_by_filters`.

**M011/S03 extension:** Add `status`, `starred`, `tag`, `collection` facets to `SearchFilters`. The `SearchFilters.is_empty()` fast-path stays intact. When new facets are set, the use case also calls `VideoTrackingRepository.list_by_*` and `TagRepository.list_video_ids_for_tag` to build additional `allowed_video_ids` sets, then intersects them.

**Alternative considered and rejected:** Moving all filtering to a single SQL JOIN query. Rejected because: (1) the FTS5 virtual table doesn't participate in standard SQLAlchemy JOINs cleanly, (2) the current two-phase approach already works and is tested, (3) the intersection of small sets in Python is fast enough for a personal library.

**Backward compatibility:** `SearchFilters` adds 4 new fields with default `None`. Existing callers pass no `filters` argument → `SearchFilters()` → `is_empty()` returns `True` → pure FTS5 path unchanged.

### D6: Export record schema (v1 frozen contract)

**Decision:** The JSON export record includes:

```python
@dataclass(frozen=True, slots=True)
class ExportRecord:
    """One video + all its associated data, suitable for export."""
    video_id: int
    platform: str
    url: str
    author: str | None
    title: str | None
    upload_date: str | None
    # Analysis
    score: float | None
    summary: str | None
    keywords: list[str]
    topics: list[str]
    verticals: list[str]
    actionability: float | None
    content_type: str | None
    # Tracking
    status: str | None       # None if no tracking row
    starred: bool
    notes: str | None
    # Tags
    tags: list[str]
    # Collection membership
    collections: list[str]
    # Metadata
    exported_at: str          # ISO 8601 UTC
```

**Markdown format:** YAML frontmatter block + `# Title` header + body sections. Uses `yaml.dump()` for the frontmatter dict.

**CSV format:** Flat — multi-value fields (`keywords`, `tags`, `collections`) are joined with `|` separator.

### D7: `python-frontmatter` — runtime vs dev dependency

**Decision:** NOT a runtime dependency. The exporter writes YAML frontmatter via `yaml.dump()` (pyyaml already present). If the test suite needs `python-frontmatter` to parse and validate exported files, add it to `[dependency-groups.dev]` only.

---

## Common Pitfalls

### Pitfall 1: Breaking existing `SearchVideosUseCase` callers
**What goes wrong:** Adding new parameters to `SearchFilters` with non-None defaults would change behavior for existing callers.
**Why it happens:** Python dataclass fields with defaults affect `is_empty()` logic.
**How to avoid:** All new `SearchFilters` fields MUST default to `None`. `is_empty()` must check all fields. Test the zero-filter fast path explicitly.
**Warning signs:** `test_search_videos.py` failures on the "no filters" path.

### Pitfall 2: Migration order dependency
**What goes wrong:** `_ensure_tags_collections_tables` references `tags` before creating it if split across multiple functions with wrong call order.
**Why it happens:** `collection_items` has a FK to both `tags` and `collections`.
**How to avoid:** One function `_ensure_tags_collections_tables` that creates `tags`, then `collections`, then `collection_items` in order. Don't split across multiple `_ensure_*` functions.
**Warning signs:** `OperationalError: no such table: tags` on first startup.

### Pitfall 3: `video_tracking` UNIQUE constraint on `video_id`
**What goes wrong:** Using `INSERT` instead of upsert → `IntegrityError` on second call to `review <id>`.
**Why it happens:** One tracking row per video, user can update status multiple times.
**How to avoid:** Use `INSERT OR REPLACE` or `ON CONFLICT(video_id) DO UPDATE SET status=excluded.status, ...` in the repository's `upsert` method.
**Warning signs:** `StorageError` on `vidscope review` called twice for same video.

### Pitfall 4: Tag name case sensitivity
**What goes wrong:** `Tag("Idea")` and `Tag("idea")` create two rows — user sees duplicates.
**Why it happens:** SQLite string comparison is case-sensitive by default.
**How to avoid:** Normalize to lowercase in `TagRepositorySQLite.get_or_create` before INSERT/SELECT. Add a `CHECK(name = lower(name))` constraint if enforcement is needed at DB level.
**Warning signs:** Duplicate tags in `vidscope tag list`.

### Pitfall 5: Pipeline neutrality regression
**What goes wrong:** Re-ingesting a video (via `vidscope add <url>`) wipes or overwrites the `video_tracking` row.
**Why it happens:** If `VideoRepository.upsert_by_platform_id` also cascades-deletes related rows (it should not — FK is `ON DELETE CASCADE` only on explicit delete, not upsert).
**How to avoid:** `ON DELETE CASCADE` is for `DELETE FROM videos WHERE id = ?`, not for upsert. SQLAlchemy's `ON CONFLICT DO UPDATE` on `(platform_id)` only updates the `videos` row itself, never the tracking FK children.
**Warning signs:** `video_tracking` row disappears after `vidscope add` on same URL.

### Pitfall 6: Import-linter violation with export adapter
**What goes wrong:** `adapters/export/json_exporter.py` imports from `adapters/sqlite/` to fetch data → violates `export-adapter-is-self-contained`.
**Why it happens:** Confusion between "the exporter fetches data" vs "the use case fetches data and passes it to the exporter".
**How to avoid:** `ExportLibraryUseCase` fetches all data via the UoW and builds `ExportRecord` list. It then passes the list to the `Exporter` adapter. The exporter only serializes — it receives `list[ExportRecord]` and writes to output. No adapter cross-contamination.
**Warning signs:** `lint-imports` fails with `export-adapter-is-self-contained`.

### Pitfall 7: `updated_at` on `video_tracking`
**What goes wrong:** Forgetting `updated_at` means there is no way to sort "recently reviewed" or detect stale status.
**Why it happens:** Many minimal schemas omit it.
**How to avoid:** Include `updated_at DATETIME NOT NULL` in the table. Set it in the `upsert` method to `datetime.now(UTC)` on every update.

---

## Code Examples

### Many-to-many: tags assignment table

```sql
-- Source: schema.py pattern — verified from video_stats / watched_accounts
CREATE TABLE tags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       VARCHAR(128) NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT uq_tags_name UNIQUE (name)
);

CREATE TABLE tag_assignments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id   INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at DATETIME NOT NULL,
    CONSTRAINT uq_tag_assignments_video_tag UNIQUE (video_id, tag_id)
);

CREATE TABLE collections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT uq_collections_name UNIQUE (name)
);

CREATE TABLE collection_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    video_id      INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    created_at    DATETIME NOT NULL,
    CONSTRAINT uq_collection_items_coll_video UNIQUE (collection_id, video_id)
);
```

### S03: Extending SearchFilters

```python
# Source: application/search_videos.py — SearchFilters pattern
@dataclass(frozen=True, slots=True)
class SearchFilters:
    # Existing M010 facets (unchanged):
    content_type: ContentType | None = None
    min_actionability: float | None = None
    is_sponsored: bool | None = None
    # M011/S03 new facets:
    status: TrackingStatus | None = None
    starred: bool | None = None          # None=no filter, True=starred only
    tag: str | None = None               # single tag name (normalized)
    collection: str | None = None        # single collection name

    def is_empty(self) -> bool:
        return (
            self.content_type is None
            and self.min_actionability is None
            and self.is_sponsored is None
            and self.status is None
            and self.starred is None
            and self.tag is None
            and self.collection is None
        )
```

### S04: Markdown exporter (no `python-frontmatter` needed)

```python
# Source: pyyaml pattern — yaml.dump for YAML frontmatter writing
import csv
import io
import json
from pathlib import Path
import yaml  # pyyaml already a dep

class MarkdownExporter:
    def write(self, records: list[ExportRecord], out: Path | None = None) -> None:
        lines: list[str] = []
        for rec in records:
            frontmatter = {
                "video_id": rec.video_id,
                "platform": rec.platform,
                "url": rec.url,
                "status": rec.status,
                "starred": rec.starred,
                "tags": rec.tags,
                "collections": rec.collections,
                "score": rec.score,
                "actionability": rec.actionability,
                "content_type": rec.content_type,
                "exported_at": rec.exported_at,
            }
            lines.append("---")
            lines.append(yaml.dump(frontmatter, allow_unicode=True, sort_keys=True).rstrip())
            lines.append("---")
            lines.append(f"# {rec.title or rec.url}")
            if rec.summary:
                lines.append("")
                lines.append(rec.summary)
            lines.append("")
            lines.append("---")
            lines.append("")
        content = "\n".join(lines)
        if out is None:
            print(content)
        else:
            out.write_text(content, encoding="utf-8")
```

### UoW extension: 3 repos at once

```python
# Source: adapters/sqlite/unit_of_work.py — __enter__ pattern
def __enter__(self) -> SqliteUnitOfWork:
    ...
    # Existing repos (preserved):
    self.videos = VideoRepositorySQLite(self._connection)
    # ... etc ...
    self.video_stats = VideoStatsRepositorySQLite(self._connection)
    # M011 additions:
    self.video_tracking = VideoTrackingRepositorySQLite(self._connection)
    self.tags = TagRepositorySQLite(self._connection)
    self.collections = CollectionRepositorySQLite(self._connection)
    return self
```

---

## Import-Linter Contracts: Current + New

[VERIFIED: `.importlinter` — 10 contracts currently defined]

| # | Contract | Status |
|---|----------|--------|
| 1 | `layers` — hexagonal inward-only | existing |
| 2 | `sqlite-never-imports-fs` | existing |
| 3 | `fs-never-imports-sqlite` | existing |
| 4 | `llm-never-imports-other-adapters` | existing |
| 5 | `domain-is-pure` | existing |
| 6 | `ports-are-pure` | existing |
| 7 | `pipeline-has-no-adapters` | existing |
| 8 | `application-has-no-adapters` | existing |
| 9 | `mcp-has-no-adapters` | existing |
| 10 | `config-adapter-is-self-contained` | existing |
| **11** | **`export-adapter-is-self-contained`** | **NEW — M011/S04** |

The new contract mirrors contract #10 (`config-adapter-is-self-contained`) exactly, replacing `vidscope.adapters.config` with `vidscope.adapters.export`.

---

## Environment Availability

Step 2.6: No new external dependencies. All required tooling is already available.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All slices | Yes | `>=3.12` (project requirement) | — |
| SQLite (stdlib) | S01/S02/S03 | Yes | stdlib | — |
| pyyaml | S04 Markdown exporter | Yes | `>=6.0,<7` in pyproject.toml | — |
| csv (stdlib) | S04 CSV exporter | Yes | stdlib | — |
| json (stdlib) | S04 JSON exporter | Yes | stdlib | — |
| python-frontmatter | S04 tests (optional) | Not installed | — | Write YAML manually with yaml.dump() — no runtime need |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** `python-frontmatter` — not needed at runtime; tests can validate frontmatter structure by parsing the YAML block manually with pyyaml.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/unit/ -x -q` |
| Full suite command | `pytest -x` (excludes integration by default per `addopts`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| R056 | `TrackingStatus` enum values and transitions | unit | `pytest tests/unit/test_video_tracking.py -x` | Wave 0 |
| R056 | `VideoTrackingRepositorySQLite` CRUD + upsert + UNIQUE | unit | `pytest tests/unit/test_video_tracking_repository.py -x` | Wave 0 |
| R056 | `SetVideoTrackingUseCase` with InMemory repo | unit | `pytest tests/unit/test_set_video_tracking.py -x` | Wave 0 |
| R056 | Pipeline neutrality: re-ingest does not wipe tracking | unit (integration-style) | `pytest tests/unit/test_pipeline_neutrality.py -x` | Wave 0 |
| R057 | `TagRepositorySQLite` CRUD, case-norm, UNIQUE | unit | `pytest tests/unit/test_tag_repository.py -x` | Wave 0 |
| R057 | `CollectionRepositorySQLite` CRUD, membership | unit | `pytest tests/unit/test_collection_repository.py -x` | Wave 0 |
| R057 | 6 tag/collection use cases | unit | `pytest tests/unit/test_tag_use_cases.py tests/unit/test_collection_use_cases.py -x` | Wave 0 |
| R058 | `SearchFilters.is_empty()` with new fields | unit | `pytest tests/unit/test_search_videos.py -x` | exists (extend) |
| R058 | Facet matrix: ≥50 combinations of 3 facets from 11 | unit | `pytest tests/unit/test_search_facets_matrix.py -x` | Wave 0 |
| R058 | SQL-injection guard: fuzz facet values | unit | `pytest tests/unit/test_search_sql_injection.py -x` | Wave 0 |
| R059 | JSON exporter: schema validation + round-trip | unit | `pytest tests/unit/test_export_json.py -x` | Wave 0 |
| R059 | Markdown exporter: frontmatter parseable | unit | `pytest tests/unit/test_export_markdown.py -x` | Wave 0 |
| R059 | CSV exporter: stdlib csv round-trip | unit | `pytest tests/unit/test_export_csv.py -x` | Wave 0 |
| R059 | `ExportLibraryUseCase` with fixture DB | unit | `pytest tests/unit/test_export_library.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/ -x -q`
- **Per wave merge:** `pytest -x` (full suite minus integration) + `lint-imports` + `mypy src/vidscope`
- **Phase gate:** Full suite green + `lint-imports` 11 contracts green + `verify-m011.sh` passes

### Wave 0 Gaps

- `tests/unit/test_video_tracking.py` — domain entity + enum tests (R056)
- `tests/unit/test_video_tracking_repository.py` — SQLite adapter tests (R056)
- `tests/unit/test_set_video_tracking.py` — use case tests (R056)
- `tests/unit/test_pipeline_neutrality.py` — regression guard (R056)
- `tests/unit/test_tag_repository.py` — (R057)
- `tests/unit/test_collection_repository.py` — (R057)
- `tests/unit/test_tag_use_cases.py` — (R057)
- `tests/unit/test_collection_use_cases.py` — (R057)
- `tests/unit/test_search_facets_matrix.py` — (R058)
- `tests/unit/test_search_sql_injection.py` — (R058)
- `tests/unit/test_export_json.py` — (R059)
- `tests/unit/test_export_markdown.py` — (R059)
- `tests/unit/test_export_csv.py` — (R059)
- `tests/unit/test_export_library.py` — (R059)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat `videos` table for all user state | Separate `video_tracking` table (D033) | M011 design decision | Re-ingest idempotent, annotations never wiped |
| Search limited to FTS5 + 3 analysis facets | Search with 11 composable facets (FTS5 + tracking + tags + collections + analysis) | M011/S03 | Full veille workflow in one query |
| No export | `vidscope export` with frozen v1 schema | M011/S04 | Notion/Obsidian/Airtable import |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `python-frontmatter` is not needed at runtime; `yaml.dump()` is sufficient for writing Markdown frontmatter | Standard Stack, Code Examples | If the test suite requires `python-frontmatter` for test validation, add it to `[dependency-groups.dev]` only — runtime code unchanged |
| A2 | There is no existing `vidscope.adapters.export` submodule | Architecture Patterns | If it exists, adapt the structure accordingly |
| A3 | `REQUIREMENTS.md` entries R056–R059 do not yet exist — they are defined by the ROADMAP for M011 | Phase Requirements | Minor — these are new requirements being introduced by M011 |

---

## Open Questions

1. **`ExportRecord` as domain entity or application DTO?**
   - What we know: Export records aggregate data from multiple tables (video + analysis + tracking + tags + collections). Domain entities in `entities.py` are single-aggregate.
   - What's unclear: Should `ExportRecord` live in `domain/` or in `application/use_cases/export_library.py` as a local DTO?
   - Recommendation: Application-layer DTO in `application/use_cases/export_library.py`. It's not a domain entity — it's a projection for a specific output operation. Keeps domain slim.

2. **MCP tool for S03 facets**
   - What we know: The ROADMAP says "MCP tool exposes the same facets". The current `search.py` MCP tool is in `mcp/server.py`.
   - What's unclear: Does the MCP search tool pass all 11 facets, or a subset?
   - Recommendation: Pass all facets for completeness. The `SearchFilters` dataclass is the single source of truth — the MCP tool just maps JSON parameters to it.

3. **`vidscope review` — create-or-update semantics for `notes`**
   - What we know: Notes are free-text. Partial update (change status without changing notes) should preserve existing notes.
   - What's unclear: Should `--note ""` clear existing notes, or should notes only be set when `--note` is explicitly provided?
   - Recommendation: If `--note` is not provided on CLI, existing notes are preserved (upsert only touches provided fields). If `--note ""` is provided explicitly, notes are cleared. Implement with `Optional[str]` parameter and conditional upsert logic.

---

## Sources

### Primary (HIGH confidence — verified against live codebase)
- `src/vidscope/domain/entities.py` — entity patterns, frozen dataclass, slot discipline
- `src/vidscope/domain/values.py` — StrEnum pattern, NewType aliases
- `src/vidscope/ports/repositories.py` — Protocol pattern, method signatures, docstring conventions
- `src/vidscope/ports/unit_of_work.py` — UoW Protocol structure, repo attribute pattern
- `src/vidscope/adapters/sqlite/schema.py` — `_ensure_*` migration pattern, SQLAlchemy table definitions
- `src/vidscope/adapters/sqlite/unit_of_work.py` — `__enter__` repo wiring pattern
- `src/vidscope/adapters/sqlite/analysis_repository.py` — `list_by_filters` dynamic query builder, SQL injection prevention
- `src/vidscope/adapters/sqlite/video_stats_repository.py` — append-only pattern, row↔entity translation
- `src/vidscope/application/search_videos.py` — `SearchFilters`, two-phase search, backward compat
- `src/vidscope/cli/commands/watch.py` — Typer sub-app pattern
- `src/vidscope/cli/commands/search.py` — facet CLI option pattern
- `src/vidscope/cli/app.py` — `add_typer` registration pattern
- `src/vidscope/infrastructure/container.py` — Container composition, no new fields needed
- `.importlinter` — 10 existing contracts, `config-adapter-is-self-contained` template for new export contract
- `pyproject.toml` — dependency versions, ruff/mypy config

### Secondary (MEDIUM confidence)
- `pip show python-frontmatter` — confirmed NOT installed; runtime unnecessary
- `python -c "import yaml"` — pyyaml available for YAML dump in exporter

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in pyproject.toml + venv
- Architecture patterns: HIGH — all patterns traced to specific file:line in codebase
- Migration strategy: HIGH — verified existing `_ensure_*` functions in schema.py
- S03 search extension: HIGH — verified `SearchFilters` + `list_by_filters` pattern
- S04 export: HIGH — Protocol pattern traced to ports layer; YAML dump verified
- Pitfalls: HIGH — each traced to specific existing code or design decision

**Research date:** 2026-04-18
**Valid until:** 2026-05-18 (stable codebase, no fast-moving dependencies)
