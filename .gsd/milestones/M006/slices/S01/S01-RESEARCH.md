# Phase M006/S01: Creator domain entity + SQLite adapter + migration — Research

**Researched:** 2026-04-17
**Domain:** Hexagonal Python / SQLAlchemy Core / SQLite FTS / yt-dlp reuse
**Confidence:** HIGH (pattern is a near-copy of the existing `WatchAccount` slice — M003/S01 — with two additional moving parts: a column-level addition on an existing table and a one-shot backfill script)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (D-01 .. D-05)

- **D-01:** Primary UNIQUE key on `creators` = `(platform, platform_user_id)`. `platform_user_id` stores yt-dlp's stable `uploader_id`. `creators.id` remains a surrogate autoincrement INT PK. `handle` is stored but **not** UNIQUE — renames are supported without data loss.
- **D-02:** Backfill strategy = re-probe yt-dlp via `Downloader.probe()`. Script iterates every pre-M006 video, upserts the creator row, sets `videos.creator_id`. Mandatory `--dry-run` default; `--apply` required for mutation. 404s produce `creators.is_orphan=true` so every video still gets an FK populated.
- **D-03:** `videos.author` is **preserved** as denormalised write-through cache. On every video upsert, `creator.display_name` is copied into `videos.author` inside the same transaction. Sync is structurally enforced at the repository layer — application code never writes `videos.author` directly. Regression test required: updating `creator.display_name` + re-upserting the video must propagate.
- **D-04:** `follower_count` = scalar field on `creators`. No time-series table in M006 (M009 owns temporal data). YAGNI.
- **D-05:** Avatar = `avatar_url` string only. Zero download, zero MediaStorage write, zero image I/O.

### Claude's Discretion

- Exact SQLAlchemy Core column types (follow existing conventions in `adapters/sqlite/schema.py`).
- `CreatorRepository` Protocol method signatures (idiomatic: `find_by_platform_user_id`, `upsert`, `find_by_handle`, `list_by_platform`, `list_by_min_followers`).
- Test helpers (`InMemoryCreatorRepository` for application unit tests — build as needed for ≥ 80% coverage).
- Exact wording of dry-run output in `backfill_creators.py`.

### Deferred Ideas (OUT OF SCOPE for S01)

- yt-dlp extraction of creator info during live ingest → **S02**.
- CLI `vidscope creator show/list/videos` + MCP tool `vidscope_get_creator` → **S03**.
- Creator-level velocity / `creator_stats` time-series → **M009** (deferred; D-04 leaves the door open by not pre-allocating).
- Avatar image download & cache → out-of-scope (D-05 chose URL string only).
- Cross-platform identity resolution → out of M006 entirely.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| R040 | Every ingested video is linked to a `Creator` entity carrying platform, stable `platform_user_id`, canonical `handle`, `display_name`, `profile_url`, `follower_count`, `avatar_url`, `is_verified`. | S01 delivers the **entity + table + FK + repo + DI wiring**. Live-ingest population (yt-dlp extraction in `DownloadResult`) lands in S02. S01 is the structural foundation — enough to hold data and be backfilled. |
| R041 (partial) | CLI and MCP surfaces for creators. | **Not in S01.** S01 only ships the repository so S03 can plug the CLI/MCP on top without re-wiring. CONTEXT.md §Phase Boundary is explicit: no CLI, no MCP in S01. |
| R042 | Migration from `videos.author` to `videos.creator_id` is lossless and reversible. | S01 delivers `backfill_creators.py` using `Downloader.probe()`. Loss-less: `videos.author` stays; every video row gets an FK (orphan flag for 404s). Reversible: `videos.author` is the recovery surface if `creator_id` is dropped. |
</phase_requirements>

## Summary

S01 is a direct structural mirror of the M003/S01 slice that shipped `WatchedAccount`: a frozen domain entity + one repository Protocol + one SQLAlchemy Core table + one SQLite adapter + UoW wiring + DI wiring. The incremental complexity over M003/S01 is (1) a column-level addition to the existing `videos` table, which on SQLite means an `ALTER TABLE ADD COLUMN ... REFERENCES creators(id)` executed as raw DDL (SQLAlchemy Core's `metadata.create_all()` alone cannot add a column to an existing table), (2) a **write-through cache** discipline on `videos.author` that requires either refactoring `VideoRepositorySQLite.upsert_by_platform_id` to source `author` from a `Creator` argument or adding a UoW-level orchestration method, and (3) a one-shot python script under `scripts/` that reuses the existing `Downloader.probe()` method.

Migration harness: the codebase has **no migration framework today** (no Alembic, no numbered migration files). Schema creation runs through `metadata.create_all()` in `init_db()` which is idempotent for new tables but silently ignores drift on existing tables. For S01, the minimal-fit recommendation is to extend `init_db()` with a **deterministic `ALTER TABLE` block** that runs `PRAGMA table_info(videos)` first and issues `ALTER TABLE videos ADD COLUMN creator_id` only when the column is absent. This preserves idempotency, matches D005/D006 (SQLite + thin SQL), and avoids introducing Alembic for one column.

**Primary recommendation:** treat S01 as WatchAccount-plus-FK-plus-backfill. Mirror `WatchAccountRepositorySQLite` line-for-line for `SqlCreatorRepository`. Add creators to `schema.py`'s `metadata` + an imperative post-create ALTER block for `videos.creator_id`. Put `CreatorRepository` Protocol in **`ports/repositories.py`** (existing convention). Write-through cache: add a `VideoRepository.upsert_with_creator(video, creator)` method that copies `creator.display_name` → `videos.author` in the same SQL statement. Backfill: plain `argparse` script at `scripts/backfill_creators.py` (no Typer — keep the one-shot out of the user-facing CLI).

## Canonical File Inventory

| CONTEXT.md deliverable | File path | Confirmed / New |
|----|----|----|
| `Creator` frozen dataclass | `src/vidscope/domain/entities.py` (append) | extend existing file |
| `CreatorId`, `PlatformUserId` value objects | `src/vidscope/domain/values.py` (append) | extend existing file |
| `CreatorRepository` Protocol | `src/vidscope/ports/repositories.py` (append) | extend existing file (see §Port Organization Decision below) |
| Domain + ports exports | `src/vidscope/domain/__init__.py` and `src/vidscope/ports/__init__.py` (append to `__all__`) | extend |
| `SqlCreatorRepository` concrete | `src/vidscope/adapters/sqlite/creator_repository.py` | **new file** |
| `creators` table definition | `src/vidscope/adapters/sqlite/schema.py` (append Table + ALTER block) | extend existing file |
| Migration "003_creators" | **not a separate file** — becomes an idempotent block in `schema.init_db` (see §Migration Strategy) | executed inside `init_db` |
| SqlCreatorRepository re-export | `src/vidscope/adapters/sqlite/__init__.py` (append) | extend |
| UoW wiring | `src/vidscope/adapters/sqlite/unit_of_work.py` (add `self.creators` slot + `CreatorRepositorySQLite` construction) | extend |
| Container wiring | `src/vidscope/infrastructure/container.py` — nothing to change for S01 because repos are constructed per-UoW, not on the container (consistent with the other 7 repos) | **unchanged** — noted in open questions |
| Backfill script | `scripts/backfill_creators.py` | **new file** (first Python script under `scripts/`; all prior entries are bash `verify-*.sh`) |
| Adapter tests | `tests/unit/adapters/sqlite/test_creator_repository.py` | **new file** |
| Schema tests (ALTER block idempotence, FK on-delete, index) | `tests/unit/adapters/sqlite/test_schema.py` (append class or cases) | extend |
| UoW tests | `tests/unit/adapters/sqlite/test_unit_of_work.py` (append case for `uow.creators` property) | extend |
| Domain entity tests | `tests/unit/domain/test_entities.py` (add `TestCreator`) | extend |
| Domain value tests | `tests/unit/domain/test_values.py` (add `TestCreatorId`, `TestPlatformUserId`) | extend |
| Backfill tests | `tests/unit/scripts/test_backfill_creators.py` (new subpackage if needed) | **new file + new subpackage** |
| Architecture test — expected contracts list | `tests/architecture/test_layering.py` — **already covers 8 of 9 contracts via name, and all 9 via `lint-imports` exit code**. No change needed unless planner chooses to also align the `EXPECTED_CONTRACTS` tuple (pre-existing drift, out of S01 scope). | unchanged |

## Migration Strategy

### What exists today

- **No Alembic.** No `alembic.ini`, no `migrations/` subdirectory anywhere under `src/vidscope/adapters/sqlite/`. Confirmed by `ls` — only `*.py` repo files + `schema.py` + `search_index.py` + `unit_of_work.py`.
- **Schema is declared as a SQLAlchemy Core `MetaData` registry** in `schema.py`. `init_db(engine)` calls `metadata.create_all(engine)` (which issues `CREATE TABLE IF NOT EXISTS` per-table) and then runs a raw `CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(...)`.
- **Idempotency is per-table, not per-column.** If a Column is added to an existing Table declaration, `metadata.create_all()` will NOT alter the existing table on disk — the new column silently won't exist on already-initialized DBs.
- **Pre-existing user DBs already have data** from M001–M005 (this is the whole reason R042 exists and demands a backfill).

### Recommended shape for "003_creators"

Because the codebase has no migration harness and CONTEXT.md's "migration 003_creators.py" is aspirational, adapt: **put the new table in `metadata` (so fresh installs work via `create_all`) AND execute an idempotent `ALTER TABLE videos ADD COLUMN creator_id` guard in `init_db` (so upgraded installs get the column)**. This is the minimal fit — introducing Alembic for one column-add is disproportionate at this scale.

**Proposed additions to `schema.py`:**

```python
# After the existing `videos` Table definition (lines 81-95):
videos = Table(
    "videos",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("platform", String(32), nullable=False),
    Column("platform_id", String(128), nullable=False, unique=True),
    Column("url", Text, nullable=False),
    Column("author", String(255), nullable=True),          # preserved (D-03)
    Column("title", Text, nullable=True),
    Column("duration", Float, nullable=True),
    Column("upload_date", String(32), nullable=True),
    Column("view_count", Integer, nullable=True),
    Column("media_key", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    # NEW — declared here so fresh installs get it via create_all.
    Column(
        "creator_id",
        Integer,
        ForeignKey("creators.id", ondelete="SET NULL"),
        nullable=True,
    ),
)

# New creators table:
creators = Table(
    "creators",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("platform", String(32), nullable=False),
    Column("platform_user_id", String(255), nullable=False),
    Column("handle", String(255), nullable=True),          # non-unique (D-01)
    Column("display_name", Text, nullable=True),
    Column("profile_url", Text, nullable=True),
    Column("avatar_url", Text, nullable=True),
    Column("follower_count", Integer, nullable=True),
    Column("is_verified", Boolean, nullable=True),
    Column("is_orphan", Boolean, nullable=False, default=False),
    Column("first_seen_at", DateTime(timezone=True), nullable=True),
    Column("last_seen_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=_utc_now),
    UniqueConstraint(
        "platform", "platform_user_id",
        name="uq_creators_platform_user_id",
    ),
)
Index("idx_creators_handle", creators.c.platform, creators.c.handle)
Index("idx_videos_creator_id", videos.c.creator_id)
```

**And in `init_db`:**

```python
def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    with engine.begin() as conn:
        _create_fts5(conn)
        _ensure_videos_creator_id(conn)  # NEW — idempotent ALTER

def _ensure_videos_creator_id(conn: Connection) -> None:
    """Add videos.creator_id on upgraded DBs. Idempotent."""
    cols = {row[1] for row in conn.execute(text("PRAGMA table_info(videos)"))}
    if "creator_id" in cols:
        return
    # SQLite note: ALTER TABLE ADD COLUMN with a REFERENCES clause is
    # supported; ON DELETE SET NULL is honored because PRAGMA foreign_keys
    # is already ON for every connection (sqlite_engine.py:57).
    conn.execute(text(
        "ALTER TABLE videos ADD COLUMN creator_id INTEGER "
        "REFERENCES creators(id) ON DELETE SET NULL"
    ))
```

**Why this works and why no separate `migrations/003_creators.py`:**
- Fresh installs: `metadata.create_all()` creates both tables with the FK inline.
- Upgraded installs: `metadata.create_all()` creates `creators` but skips `videos` (already exists); `_ensure_videos_creator_id()` adds the column.
- Idempotent on repeat init: `PRAGMA table_info` guard prevents double-ALTER.
- Matches the style of the existing raw `CREATE VIRTUAL TABLE IF NOT EXISTS` FTS5 block — raw SQL alongside SA Core when Core can't express the DDL.

**Reversibility (R042):** A future "003_creators_down" is a raw `DROP COLUMN` (SQLite 3.35+ supports `ALTER TABLE videos DROP COLUMN creator_id`). For S01, the reversibility requirement is satisfied functionally because `videos.author` still carries the display name — dropping `creator_id` leaves the row valid. S01 does not need to ship a down-migration script, but the planner may choose to add a `scripts/rollback_m006.sh` for safety. Confidence: MEDIUM — the CONTEXT.md wording is "reversible", not "auto-reversible", and D-03 is the pragmatic safety net.

## Port Organization Decision

**Recommendation:** **Append `CreatorRepository` to `ports/repositories.py`**. Do NOT create a new `ports/creator_repository.py` file.

**Rationale (verified by reading the existing code):**
- `ports/repositories.py` is 275 lines and already contains **seven** repository Protocols: `VideoRepository`, `TranscriptRepository`, `FrameRepository`, `AnalysisRepository`, `PipelineRunRepository`, `WatchAccountRepository`, `WatchRefreshRepository`.
- The file docstring (`"""Repository ports."""`, line 1) explicitly says: *"Every persistent aggregate has its own repository Protocol. Adapters in `vidscope.adapters.sqlite` implement these"* — the file IS the registry.
- `ports/__init__.py` re-exports from `vidscope.ports.repositories` in a single grouped import (lines 34-42). Adding `CreatorRepository` there is one line.
- Splitting into a new file would be inconsistent with 100% of the existing convention and would require the planner to decide whether to retroactively split the other seven (out of scope for S01).

**The CONTEXT.md references `ports/creator_repository.py`** — that wording is aspirational/shorthand. The correct mirror of the existing codebase is `ports/repositories.py`.

## Repository Pattern Reference

### Canonical upsert shape (mirror exactly)

The pattern to copy is **`VideoRepositorySQLite.upsert_by_platform_id`** at `src/vidscope/adapters/sqlite/video_repository.py:53-85`:

```python
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

def upsert_by_platform_user_id(self, creator: Creator) -> Creator:
    payload = _creator_to_row(creator)
    stmt = sqlite_insert(creators_table).values(**payload)
    # On conflict, update every field except id and created_at.
    update_map = {
        key: stmt.excluded[key]
        for key in payload
        if key not in ("created_at",)
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["platform", "platform_user_id"],  # matches UNIQUE (D-01)
        set_=update_map,
    )
    try:
        self._conn.execute(stmt)
    except Exception as exc:
        raise StorageError(
            f"upsert failed for creator {creator.platform_user_id}: {exc}",
            cause=exc,
        ) from exc

    stored = self.find_by_platform_user_id(creator.platform, creator.platform_user_id)
    if stored is None:
        raise StorageError(
            f"upsert succeeded but row missing for {creator.platform_user_id}"
        )
    return stored
```

**Key conventions observed across all five existing adapters:**
- Constructor takes a `Connection` (NOT an engine). UoW owns the connection and passes it in on `__enter__`.
- Every method wraps SQLAlchemy exceptions in `StorageError(msg, cause=exc)`.
- Upsert returns the entity re-read from the DB (with `id` populated from `inserted_primary_key` OR from a follow-up `get_by_*` call).
- Row↔entity translation via two module-level helpers: `_<entity>_to_row()` and `_row_to_<entity>()`. See `video_repository.py:136-169` and `watch_account_repository.py:103-140`.
- Datetime round-trip uses a `_ensure_utc_for_read` / `_ensure_utc_for_write` pair (see `watch_account_repository.py:129-140`) — adopt it for Creator's `first_seen_at`, `last_seen_at`, `created_at`.
- Reads return `None` on miss, never raise. List methods take explicit `limit`.

### Minimal `CreatorRepository` Protocol signature (Claude's discretion — idiomatic set)

```python
@runtime_checkable
class CreatorRepository(Protocol):
    def upsert(self, creator: Creator) -> Creator: ...
    def find_by_platform_user_id(
        self, platform: Platform, platform_user_id: PlatformUserId
    ) -> Creator | None: ...
    def find_by_handle(
        self, platform: Platform, handle: str
    ) -> Creator | None: ...
    def get(self, creator_id: CreatorId) -> Creator | None: ...
    def list_by_platform(
        self, platform: Platform, *, limit: int = 50
    ) -> list[Creator]: ...
    def list_by_min_followers(
        self, min_count: int, *, limit: int = 50
    ) -> list[Creator]: ...
    def count(self) -> int: ...
```

Method naming note: the existing codebase mixes `get_*` / `get_by_*` / `list_*`. Using `find_by_*` for null-returning lookups is still idiomatic (VideoRepository uses `get` for the PK lookup, `get_by_*` for secondary lookups). Planner may prefer `get_by_platform_user_id` for symmetry — either works.

## Backfill Plan

### `Downloader.probe()` return shape (verified in `ports/pipeline.py:191-215`)

```python
@dataclass(frozen=True, slots=True)
class ProbeResult:
    status: ProbeStatus  # OK / AUTH_REQUIRED / NOT_FOUND / NETWORK_ERROR / UNSUPPORTED / ERROR
    url: str
    detail: str
    title: str | None = None
```

**Current ProbeResult carries only `status`, `url`, `detail`, `title`.** It does **NOT** expose `uploader`, `uploader_id`, `uploader_url`, `channel_follower_count`, or `uploader_thumbnail`. These fields exist in the raw yt-dlp `info_dict` inside `YtdlpDownloader.probe` (`adapters/ytdlp/downloader.py:264-315`) but are discarded before the result is returned.

**This is a significant gap the planner must resolve.** Two options:

| Option | Approach | Tradeoff |
|---|---|---|
| **A: Extend ProbeResult** | Add `uploader`, `uploader_id`, `uploader_url`, `channel_follower_count`, `uploader_thumbnail` fields to `ProbeResult` (all `str \| None` / `int \| None`). Populate them in `YtdlpDownloader.probe`. | Port change — but additive; S02 will need this anyway to populate `CreatorInfo` in `DownloadResult`. **Recommended.** |
| B: New `probe_creator()` method | Add `Downloader.probe_creator(url) -> CreatorProbeResult`. | New port method purely for this slice. Overlaps heavily with probe; will be duplicated work when S02 extracts from the download path. Reject. |

**Recommendation: Option A.** ProbeResult becomes the shared metadata envelope for both `vidscope cookies test` (which only reads `.status` and `.title`) and S01 backfill (which reads the new uploader_* fields). Additive: existing callers are unaffected. The work is ~10 lines in `YtdlpDownloader.probe` (map `info.get("uploader_id")`, etc.) plus 5 new dataclass fields. Pre-existing cookies tests remain green.

### yt-dlp info_dict fields → Creator fields

| yt-dlp info_dict key | Creator field | Notes |
|---|---|---|
| `uploader_id` | `platform_user_id` | STABLE; never changes on rename. D-01's canonical UNIQUE key. |
| `uploader` | `display_name` | Human-friendly name; may change. |
| `uploader` (or `channel`) | `handle` | Use `@uploader` form when yt-dlp returns a bare name; fall back to `channel` for YouTube. **Ambiguous — flag to planner.** |
| `uploader_url` | `profile_url` | Platform profile page. |
| `channel_follower_count` | `follower_count` | INTEGER, nullable. TikTok: `channel_follower_count` or `channel_followers`. |
| `uploader_thumbnail` (or `channel_thumbnail`) | `avatar_url` | First URL if it's a list (yt-dlp sometimes returns `thumbnails` array). |
| `channel_verified` / `uploader_verified` | `is_verified` | Not consistently exposed across extractors — OK to end up NULL. |
| `extractor_key` (via `_platform_from_info`) | `platform` | Reuse the existing helper `_platform_from_info` verbatim. |
| n/a (computed) | `first_seen_at`, `last_seen_at` | Set to `datetime.now(UTC)` on first insert; preserved on update. |
| n/a (default False) | `is_orphan` | Set to `True` only when probe returns `NOT_FOUND` or `AUTH_REQUIRED`. |

### Backfill script shape

```python
# scripts/backfill_creators.py
"""Backfill videos.creator_id from existing M001-M005 rows.

Default mode is --dry-run: probe every video, print the creator row
that would be upserted + the resulting videos.creator_id, write NOTHING.
--apply is required to actually mutate.
"""

import argparse
import sys
from pathlib import Path

# NOTE: this script is a one-shot maintenance tool, not user-facing CLI.
# Using argparse (stdlib) not Typer keeps it explicitly out of the
# `vidscope` entry point and avoids any ambiguity about scope.

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write. Default is --dry-run.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Stop after N videos (for testing).")
    args = parser.parse_args(argv)
    dry_run = not args.apply

    from vidscope.infrastructure.container import build_container
    container = build_container()

    # 1. list videos with creator_id IS NULL
    # 2. for each: call container.downloader.probe(video.url)
    # 3. build Creator from probe result (is_orphan=true if NOT_FOUND/AUTH_REQUIRED)
    # 4. in a single UoW per video: upsert creator, then set video.creator_id + videos.author
    # 5. print progress line: [1/N] youtube/<pid> -> creator <handle> (orphan=<bool>)
    # 6. on dry-run, do NOT open the write transaction — just print the plan.
    ...

if __name__ == "__main__":
    sys.exit(main())
```

**Why argparse not Typer:** `pyproject.toml` `[project.scripts]` exposes only `vidscope = "vidscope.cli.app:app"`. Adding this backfill as a Typer sub-app would pollute `vidscope --help` with a one-shot maintenance command; keeping it in `scripts/` as `python scripts/backfill_creators.py` preserves the user-facing CLI surface. Run as `python -m uv run python scripts/backfill_creators.py --apply` — consistent with how `scripts/verify-*.sh` run other ad-hoc tools.

### 404 / AUTH_REQUIRED path → `is_orphan=true`

```
ProbeStatus.OK              → upsert creator with full fields; is_orphan=False
ProbeStatus.NOT_FOUND       → upsert creator with platform_user_id=synthesised, is_orphan=True
ProbeStatus.AUTH_REQUIRED   → upsert creator with is_orphan=True (cookies expired for old Instagram row)
ProbeStatus.NETWORK_ERROR   → skip this video, report in exit summary, suggest retry
ProbeStatus.UNSUPPORTED     → unreachable in practice (video was ingested, so extractor worked)
ProbeStatus.ERROR           → skip + report; don't create orphan (data quality)
```

**"Synthesised" platform_user_id for orphans:** when probe returns NOT_FOUND we have no `uploader_id`. Use the existing `videos.author` as a fallback platform_user_id (e.g. `platform_user_id = f"orphan:{videos.author}"`) and set `is_orphan=True`. This keeps UNIQUE(platform, platform_user_id) satisfiable for every video while flagging the row.

### Dry-run vs apply

- **Default (no flag): dry-run.** Script probes, prints the plan, exits 0. Zero writes. Explicit `--apply` required to mutate.
- **Per-video transaction:** each video's creator upsert + `videos.creator_id` update runs in its own UoW. A mid-run Ctrl-C leaves the DB in a consistent state (every committed creator has a matching video FK; no half-written creator rows).
- **Idempotent on re-run:** skip videos where `creator_id IS NOT NULL`.

## Write-Through Cache Enforcement (D-03)

**Goal:** whenever `videos.author` exists on a row, it MUST equal `creators.display_name` of the referenced creator. Application code NEVER writes `videos.author` directly.

### Three candidate mechanisms

| Option | Mechanism | Pros | Cons |
|---|---|---|---|
| **A: Refactor `VideoRepository.upsert_by_platform_id`** | Change signature from `upsert_by_platform_id(video)` to `upsert_by_platform_id(video, creator: Creator \| None = None)`. When `creator is not None`, set `video.author = creator.display_name` before writing. When `None`, skip (backward compat for S01 where S02 hasn't wired it). | Port change is minimal & additive. One enforcement point. Testable. | S01 ships with the seam but without the producer (S02 is the first caller that passes a Creator). Cache stays stale on M001-M005 rows UNTIL S02 re-ingests them OR S01 backfill writes them. |
| **B: New UoW method `upsert_video_with_creator(video, creator)`** | Single transaction-scoped helper on the UoW that upserts creator, captures `id`, then upserts video with `author=creator.display_name, creator_id=creator.id`. | Atomicity is crystal-clear; single-line call site. | Bigger port change (UoW gets a new method). Two repos coupled through UoW — unusual for this codebase. |
| **C: DB trigger** | SQLite trigger: `AFTER UPDATE OF display_name ON creators FOR EACH ROW UPDATE videos SET author = NEW.display_name WHERE creator_id = OLD.id`. | Structural, impossible to bypass. | Moves business logic into DB. Harder to test. Breaks the "no triggers except FTS5 via adapter" convention (search_index.py:4-7 docstring). **Reject.** |

**Recommendation: Option A + backfill enforcement.**

- Port change: `VideoRepository.upsert_by_platform_id(video, creator: Creator | None = None) -> Video`.
- When `creator is not None`: set `payload["author"] = creator.display_name` and `payload["creator_id"] = int(creator.id)`.
- When `creator is None`: preserve existing behavior (for S01, most callers still pass None).
- **Regression test (mandatory per CONTEXT.md specifics):** upsert a creator, upsert a video with that creator, change `creator.display_name`, re-upsert video with the same creator → assert `videos.author == new display name`.
- Backfill script uses the new signature to populate `videos.author` + `videos.creator_id` together during the one-shot migration.

**S02 consequence (out of S01 scope but must not be broken):** `IngestStage.execute` will need to upsert creator first, then pass it into `upsert_by_platform_id`. Document in open questions so S02's planner carries it.

## FK + PRAGMA Handling

### Existing mechanism (verified in `src/vidscope/infrastructure/sqlite_engine.py:51-60`)

```python
@event.listens_for(engine, "connect")
def _apply_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()
```

This listener fires on every new connection made through the engine, so **every UoW transaction has FK enforcement active**. The existing test `test_schema.py::TestInitDb::test_foreign_keys_are_enabled_on_connections` (line 28-33) pins this invariant.

### How existing FKs are declared (verified in `schema.py`)

Every existing FK uses the inline `ForeignKey()` constructor directly inside a `Column(...)`:
- `transcripts.video_id` → `ForeignKey("videos.id", ondelete="CASCADE")` (line 105)
- `frames.video_id` → `ForeignKey("videos.id", ondelete="CASCADE")` (line 120)
- `analyses.video_id` → `ForeignKey("videos.id", ondelete="CASCADE")` (line 136)
- `pipeline_runs.video_id` → `ForeignKey("videos.id", ondelete="SET NULL")` (line 156) — precedent for the nullable FK shape we need.

### S01 follows this pattern for both paths

- **Fresh install (`metadata.create_all`):** `videos.creator_id` is declared with `ForeignKey("creators.id", ondelete="SET NULL")` inline — same shape as `pipeline_runs.video_id`.
- **Upgrade path (ALTER TABLE):** the raw SQL emits the FK in the column definition: `ALTER TABLE videos ADD COLUMN creator_id INTEGER REFERENCES creators(id) ON DELETE SET NULL`. SQLite accepts this form as of SQLite 3.26+ (2018). Confirmed by the SQLite docs — `REFERENCES` clause in `ALTER TABLE ADD COLUMN` is fully supported when the referenced table exists (we create `creators` first via `metadata.create_all`).

**Caveat:** SQLite's FK check is deferred by default inside a transaction. For the backfill script, this means orphan-creator rows will validate at COMMIT time, not at the moment of INSERT. Acceptable; surface in tests.

## Script Entry Point

**Verified:** `pyproject.toml:36-37` declares only one entry:
```toml
[project.scripts]
vidscope = "vidscope.cli.app:app"
```

**Existing `scripts/` directory contents** (verified): 11 bash scripts named `verify-m00x.sh` / `verify-s0x.sh`. Zero Python scripts. `scripts/backfill_creators.py` will be the first Python script in that directory — establishes a new convention.

**Recommended invocation pattern:**

```bash
# Default: dry-run
python -m uv run python scripts/backfill_creators.py

# Apply for real
python -m uv run python scripts/backfill_creators.py --apply

# Test against a fixture DB
VIDSCOPE_DATA_DIR=/tmp/fixture python -m uv run python scripts/backfill_creators.py --apply
```

**Why not add it to `[project.scripts]` as `vidscope-backfill-creators`?** It's a one-shot data-migration tool, not a product feature. Adding it to the installed entry points suggests users should run it routinely; they shouldn't.

**Why not a Typer sub-app under `vidscope`?** Would pollute `vidscope --help` and blur the line between product CLI and maintenance script.

**Documentation:** `docs/migrations.md` (new file, 20-30 lines) explaining when to run it, what `--dry-run` shows, and recovery if probing fails. Planner decides whether this file is in S01 scope or deferred to S03/docs pass.

## Test Plan

### Fixture patterns (verified)

- **Adapter tests (`tests/unit/adapters/sqlite/conftest.py`):** `engine` fixture = `tmp_path / "test.db"` + `build_engine` + `init_db`. Real SQLite file, every table. **Reuse directly for `test_creator_repository.py`.**
- **Application tests (`tests/unit/application/conftest.py`):** `engine` + `uow_factory` + `FrozenClock`. Reuse when writing tests that exercise the repo through a UoW.
- **Integration tests:** marked `@pytest.mark.integration`; excluded by default via `addopts = ["-m", "not integration"]` in `pyproject.toml`. Live-network tests go there.

### `InMemoryCreatorRepository` — where does it belong?

**Verified:** there is **no existing in-memory repo stub** for any other repository in the codebase. Pattern across the codebase is:
- Application tests use `SqliteUnitOfWork` via the `uow_factory` fixture (see `tests/unit/application/test_watchlist.py` + `conftest.py`).
- Pipeline stage tests use `FakeDownloader` / `FakeRunner` — but never a fake repository.

**Recommendation:** **Do NOT build an `InMemoryCreatorRepository`.** Mirror the existing convention: adapter tests hit real SQLite under `tmp_path`; application-level tests (S03, not S01) will use the same pattern. The CONTEXT.md note "`InMemoryCreatorRepository` for application unit tests" is flagged as Claude's discretion — the discretion here is to say no, because the project doesn't do that elsewhere and a real SQLite fixture is already ~2ms per test.

If the planner decides otherwise (future consistency), place it in `tests/_helpers/in_memory_creator_repository.py` and import from tests that need it. But mark this as a new convention and expect pushback.

### Coverage targets per layer (CONTEXT.md: ≥ 80% line coverage on new modules)

| Layer | Test file | What to cover |
|---|---|---|
| Domain | `tests/unit/domain/test_entities.py` (extend with `TestCreator`) | Frozen semantics (`pytest.raises(AttributeError)` on mutation), slots (`assert not hasattr(c, "__dict__")`), equality, defaults (is_orphan=False), `CreatorId \| None = None` on fresh entities. |
| Domain values | `tests/unit/domain/test_values.py` (extend) | `CreatorId` and `PlatformUserId` NewType round-trip, mypy-level uniqueness is not runtime-testable but instantiation is. |
| Adapter — schema | `tests/unit/adapters/sqlite/test_schema.py` (extend) | `creators` table in `inspect(engine).get_table_names()`, UNIQUE (platform, platform_user_id), `idx_creators_handle` exists, `videos.creator_id` column exists after `init_db`, FK constraint fires (`pytest.raises(IntegrityError)` when inserting video with bad creator_id... actually SET NULL doesn't raise — write a deletion test: delete creator, verify videos.creator_id becomes NULL), `_ensure_videos_creator_id` idempotent (call init_db twice). |
| Adapter — repo | `tests/unit/adapters/sqlite/test_creator_repository.py` (new) | CRUD: add/upsert/get/find_by_platform_user_id/find_by_handle/list_by_platform/list_by_min_followers/count. Upsert idempotence across transactions. Duplicate `(platform, platform_user_id)` on `add` raises `StorageError`. Same handle on different platforms allowed. `is_orphan=True` round-trips. |
| Adapter — UoW | `tests/unit/adapters/sqlite/test_unit_of_work.py` (extend) | `uow.creators` exists and is the right Protocol type; creator + video upsert share the same transaction (rollback leaves neither row). |
| Adapter — write-through | `tests/unit/adapters/sqlite/test_video_repository.py` (extend) | **Regression test (D-03):** upsert creator `display_name="A"`, upsert video referencing it → `videos.author == "A"`. Re-upsert creator with `display_name="B"`, re-upsert video → `videos.author == "B"`. Also: upsert video with `creator=None` preserves old signature. |
| Script — backfill | `tests/unit/scripts/test_backfill_creators.py` (new, with `tests/unit/scripts/__init__.py`) | Dry-run writes nothing (assert `uow.creators.count() == 0`, `videos.creator_id IS NULL` afterwards). `--apply` writes (every video gets a `creator_id`). Orphan path: seeded video whose probe returns NOT_FOUND gets a creator with `is_orphan=True`. Idempotence: running twice with `--apply` yields same state. N=0 (empty DB) exits cleanly. Uses a stub `Downloader` that returns pre-seeded `ProbeResult` values, same pattern as `_FakeDownloader` in `tests/unit/application/test_watchlist.py:213-237`. |
| Architecture | `tests/architecture/test_layering.py` (unchanged) | The existing `test_lint_imports_exits_zero` runs the full `.importlinter` suite and will catch any new violation. **Note:** `EXPECTED_CONTRACTS` tuple only lists 8 of 9 contracts (missing `llm adapter does not import other adapters`) — pre-existing drift, not S01's concern. |

### Nyquist sampling

- **Per task commit:** `python -m uv run pytest tests/unit/adapters/sqlite/test_creator_repository.py -x` (runs < 1 s).
- **Per wave merge:** `python -m uv run pytest -q` (full unit suite — currently ~620 tests, runs ~15s).
- **Phase gate:** `python -m uv run ruff check src tests` + `python -m uv run mypy src` + `python -m uv run lint-imports` + `python -m uv run pytest -q` all green before `/gsd-verify-work`.

## Architecture Compliance

### 9 contracts in `.importlinter` and their S01 relevance

| # | Contract name | New files in S01 | Stays green because |
|---|---|---|---|
| 1 | Hexagonal layering — inward-only | `domain/entities.py`(+), `domain/values.py`(+), `ports/repositories.py`(+), `adapters/sqlite/creator_repository.py`, `adapters/sqlite/schema.py`(+), `adapters/sqlite/unit_of_work.py`(+) | All new imports follow inward direction: entities/values import stdlib only; ports import only domain; adapters import ports + domain + SQLAlchemy (allowed). |
| 2 | sqlite-never-imports-fs | `creator_repository.py` | New file imports only SQLAlchemy + `vidscope.domain` + `vidscope.domain.errors`. No fs imports. |
| 3 | fs-never-imports-sqlite | n/a | No fs changes. |
| 4 | llm-never-imports-other-adapters | n/a | No llm changes. |
| 5 | domain-is-pure | `entities.py`(+), `values.py`(+) | `Creator` uses only `datetime` + `dataclasses` + `vidscope.domain.values`. `CreatorId`/`PlatformUserId` use only `typing.NewType`. |
| 6 | ports-are-pure | `repositories.py`(+) | `CreatorRepository` Protocol imports only `vidscope.domain`. Same as all 7 existing Protocols. |
| 7 | pipeline-has-no-adapters | n/a | Pipeline unchanged in S01 (S02 will wire IngestStage). |
| 8 | application-has-no-adapters | n/a | Application unchanged in S01 (S03 will add use cases). |
| 9 | mcp-has-no-adapters | n/a | MCP unchanged in S01 (S03 will add the tool). |

**Pre-verification:** every new file's imports must come from `vidscope.domain.*`, `vidscope.ports.*`, `sqlalchemy`, or stdlib. The backfill script `scripts/backfill_creators.py` is OUTSIDE the `vidscope` package so `.importlinter` does not govern it — it's free to import `vidscope.infrastructure.container.build_container` like the `verify-*.sh` scripts do.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x + pytest-cov 7.x (from `pyproject.toml` `[dependency-groups] dev`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, markers: `unit`, `integration`, `architecture`, `slow`. `addopts` excludes `integration` by default. |
| Quick run command | `python -m uv run pytest tests/unit/adapters/sqlite/test_creator_repository.py -x` |
| Full suite command | `python -m uv run pytest -q` |
| Phase gate | `ruff check && mypy src && lint-imports && pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| R040 | Creator entity is a frozen slotted dataclass with the 12-field shape from CONTEXT.md | unit (domain) | `pytest tests/unit/domain/test_entities.py::TestCreator -x` | ❌ Wave 0 |
| R040 | CreatorRepository contract supports upsert/find_by_platform_user_id/find_by_handle/list_by_platform | unit (adapter) | `pytest tests/unit/adapters/sqlite/test_creator_repository.py -x` | ❌ Wave 0 |
| R040 | Schema creates `creators` table + UNIQUE constraint + FK index on fresh install | unit (adapter) | `pytest tests/unit/adapters/sqlite/test_schema.py::TestCreatorsSchema -x` | ❌ Wave 0 |
| R040 | Schema ALTER `videos.creator_id` is idempotent and works on upgraded DB | unit (adapter) | `pytest tests/unit/adapters/sqlite/test_schema.py::TestVideosCreatorIdAlter -x` | ❌ Wave 0 |
| R040 | `uow.creators` shares the transaction with `uow.videos` (rollback leaves neither) | unit (adapter) | `pytest tests/unit/adapters/sqlite/test_unit_of_work.py::TestCreatorInTransaction -x` | ❌ Wave 0 |
| R042 | Backfill dry-run writes nothing | unit (script) | `pytest tests/unit/scripts/test_backfill_creators.py::test_dry_run_no_writes -x` | ❌ Wave 0 |
| R042 | Backfill --apply populates creator_id on every video | unit (script) | `pytest tests/unit/scripts/test_backfill_creators.py::test_apply_fills_all -x` | ❌ Wave 0 |
| R042 | Backfill NOT_FOUND path creates orphan | unit (script) | `pytest tests/unit/scripts/test_backfill_creators.py::test_orphan_on_not_found -x` | ❌ Wave 0 |
| R042 | Backfill is idempotent (re-run = no-op) | unit (script) | `pytest tests/unit/scripts/test_backfill_creators.py::test_apply_twice_idempotent -x` | ❌ Wave 0 |
| R042 | N=0 empty DB exits cleanly | unit (script) | `pytest tests/unit/scripts/test_backfill_creators.py::test_empty_db -x` | ❌ Wave 0 |
| D-03 | Write-through: updating creator.display_name + re-upsert video updates videos.author | unit (adapter) | `pytest tests/unit/adapters/sqlite/test_video_repository.py::TestWriteThroughAuthor -x` | ❌ Wave 0 |
| Arch | All 9 import-linter contracts stay green | architecture | `pytest tests/architecture -m architecture` | ✅ (existing) |
| Type | mypy strict on new modules | type check | `python -m uv run mypy src` | ✅ (existing) |
| R041 (S01 partial) | CLI/MCP surface | — | **Not tested in S01** — delivered in S03 | — |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/adapters/sqlite/test_creator_repository.py -x` + `pytest tests/unit/domain/test_entities.py -x -k Creator`
- **Per wave merge:** `pytest -q` (full unit + architecture)
- **Phase gate:** the four quality gates green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/adapters/sqlite/test_creator_repository.py` — covers R040 (repo CRUD)
- [ ] `tests/unit/scripts/__init__.py` — new test subpackage
- [ ] `tests/unit/scripts/test_backfill_creators.py` — covers R042
- [ ] Extend `tests/unit/adapters/sqlite/test_schema.py` — covers R040 (schema)
- [ ] Extend `tests/unit/adapters/sqlite/test_unit_of_work.py` — covers R040 (UoW)
- [ ] Extend `tests/unit/adapters/sqlite/test_video_repository.py` — covers D-03 (write-through regression)
- [ ] Extend `tests/unit/domain/test_entities.py` — add `TestCreator` for R040
- [ ] Extend `tests/unit/domain/test_values.py` — add `TestCreatorId`, `TestPlatformUserId`
- [ ] (Optional) `scripts/verify-m006-s01.sh` — bash harness mirroring `verify-s07.sh` running the 4 quality gates + a tiny backfill smoke against a seeded fixture DB

## Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **`Downloader.probe()` doesn't currently expose uploader_id/uploader_url/channel_follower_count/uploader_thumbnail.** Backfill script is blocked until ProbeResult is extended. | HIGH | HIGH (blocks S01 backfill entirely) | First task in the plan: extend `ProbeResult` dataclass with the 5 new fields (all nullable) + populate them in `YtdlpDownloader.probe`. Additive change; existing cookies-test callers untouched because they only read `.status` and `.title`. Pre-existing `test_downloader.py` tests stay green. S02 will reuse these same fields. |
| 2 | **SQLite ALTER TABLE ADD COLUMN with REFERENCES may not enforce FK on existing rows** because PRAGMA foreign_keys only enforces on new operations, not retroactively. Existing videos will have `creator_id = NULL` which is fine (nullable FK) but a bad creator_id would only be caught on new writes. | MEDIUM | LOW | Acceptable — backfill script is the only writer of `creator_id` in S01 and it always references a just-upserted creator row. No external data source populates creator_id. Add a one-shot integrity check at end of backfill: `SELECT COUNT(*) FROM videos v LEFT JOIN creators c ON v.creator_id = c.id WHERE v.creator_id IS NOT NULL AND c.id IS NULL` — must be 0. |
| 3 | **Write-through cache divergence.** A bug path could write `videos.author` without going through the creator-aware upsert. Detection is manual. | LOW | MEDIUM | Two mitigations: (a) `VideoRepository.upsert_by_platform_id`'s `creator` kwarg defaults to `None`, and when None the repo does NOT touch `author` — it preserves the existing value. That way old M001-M005 author strings are preserved on re-ingest until S02 flows a real creator. (b) Backfill script is the authoritative sync for legacy rows. (c) Documented in a module docstring + tested in the regression test. |
| 4 | **yt-dlp rate limits during backfill** — probing N videos at once triggers a platform 429. Instagram especially. | MEDIUM | MEDIUM | Per-video error isolation: one failed probe doesn't abort the script. Report at end: "N succeeded, M failed (see --retry), K orphaned." Add a small per-call sleep (default 0, env-overridable `VIDSCOPE_BACKFILL_DELAY_MS`). Backfill is idempotent so a user can re-run `--apply` after a cooldown. |
| 5 | **Two-part schema creation path drift** — fresh installs (Column declared inline on `videos`) vs upgrade path (ALTER adds the column) could diverge in subtle ways (e.g. different default handling). | LOW | MEDIUM | Test both paths: (a) `test_fresh_install_has_creator_id` runs `init_db` on an empty tmp DB; (b) `test_upgrade_path_adds_creator_id` creates a DB via pre-M006 schema copy (just `CREATE TABLE videos ...` without `creator_id`), then runs `init_db`, asserts column exists. The second test is the idempotence check for `_ensure_videos_creator_id`. |

## Open Questions for Planner

1. **ProbeResult field extension — in-slice or prerequisite?** §Backfill Plan recommends adding `uploader`, `uploader_id`, `uploader_url`, `channel_follower_count`, `uploader_thumbnail`, `uploader_verified` to `ProbeResult`. This is a port change. Should the planner: (a) make it the first task of S01 (lands in S01 as scope creep), or (b) declare it a prerequisite and document as a separate micro-PR before S01 kickoff? Recommendation: **(a)** — it's ~20 lines of code and tests, and S01 cannot deliver the backfill without it. The field additions are purely additive so the risk is minimal.

2. **Handle derivation.** yt-dlp exposes `uploader` (name), `uploader_id` (stable id), `channel` (sometimes), `channel_id` (sometimes). The `handle` column is for the @-prefixed username the user recognizes. yt-dlp doesn't have a single clean "handle" field that works across all three platforms. Should S01 store: (a) `uploader_id` as handle (wrong — it's the platform_user_id), (b) `@{uploader}` (best-effort string), (c) leave it NULL and let S02 figure it out from the live download path? Recommendation: **(b) with a helper `_handle_from_info(info, platform)`** mirroring `application/watchlist.py::_handle_from_url`. Document the heuristic.

3. **`creators.first_seen_at` semantics.** On backfill, what's the "first seen" date? The earliest `videos.created_at` of that creator's videos, OR the backfill run timestamp? Recommendation: **earliest video created_at** (archaeology preserved). Planner may disagree — it's a one-line SQL either way.

4. **Container wiring — does `Container` need a creator_repository field?** The existing 7 repos are NOT fields on `Container` — they are per-UoW, constructed inside `SqliteUnitOfWork.__enter__`. Creator should follow the same pattern: no new field on `Container`. The CONTEXT.md mention of "Container wires the new repo" refers to the UoW wiring. **Recommendation: leave `Container` untouched; add `uow.creators` only.** If the planner disagrees and wants a direct `container.creator_repository`, flag that it breaks convention and will pollute the composition root for every future entity.

5. **Reversibility for R042.** §Migration Strategy noted SQLite 3.35+ supports `DROP COLUMN`. Should S01 ship a matching `scripts/rollback_m006_s01.sh` (drops `creator_id`, leaves `creators` + `videos.author` intact so the library stays usable)? CONTEXT.md calls reversibility "lossless" — `videos.author` is the structural safety net, but an explicit rollback script is more obvious. Planner decides.

6. **Windows line endings / cross-platform for `scripts/backfill_creators.py`.** D018 mandates cross-platform discipline. Keep it as pure Python with `pathlib` and no shell-outs (none needed — backfill only talks to DB + yt-dlp). Use `sys.stdout.write` not `print` for progress if the planner wants TTY-aware output. No blocker — just a reminder.

7. **`verify-m006-s01.sh` script.** Every shipped milestone has a `verify-*.sh`. Should S01 ship one, or is that reserved for milestone-level verification (`verify-m006.sh` at the end of S03)? Recommendation: **ship `scripts/verify-s01.sh`** mirroring `scripts/verify-s07.sh` — runs the 4 quality gates + a backfill smoke against a seeded fixture DB. Not strictly in CONTEXT.md but aligns with established release discipline.

8. **The `EXPECTED_CONTRACTS` drift** (pre-existing). `.importlinter` has 9 contracts; `tests/architecture/test_layering.py::EXPECTED_CONTRACTS` lists 8 (missing `llm adapter does not import other adapters`). This was introduced in M004 and went unnoticed. **Not S01's job to fix** (out-of-scope) but worth flagging as a micro-PR candidate — would be 1 line of test change.

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|---|---|---|
| Standard stack (SQLAlchemy Core + yt-dlp + argparse + pytest) | HIGH | Every library/pattern is already in use elsewhere in the codebase; zero new deps. |
| Architecture / file inventory | HIGH | Direct mirror of `WatchAccount` slice which shipped cleanly in M003. |
| Migration strategy | MEDIUM | No existing harness; the `_ensure_videos_creator_id` approach is novel to this codebase but follows the same idiom as the existing raw `CREATE VIRTUAL TABLE` FTS5 block. Confidence MEDIUM pending one additional test: `init_db` on a DB that has `videos` but not `creator_id` (the realistic upgrade scenario). |
| `Downloader.probe()` extension | HIGH | The `info_dict` fields (`uploader_id`, etc.) are documented yt-dlp contract and verified in `YtdlpDownloader.probe` source. Risk is only in mypy/test updates, not semantics. |
| Write-through cache mechanism | MEDIUM | Option A (kwarg on upsert) is safe and testable; but relies on discipline at every caller. Trigger-based (Option C) would be more airtight but violates codebase convention. Regression test is the safety net. |
| Testing approach | HIGH | Direct mirror of existing adapter tests; fixture pattern verified. |

**Research date:** 2026-04-17
**Valid until:** 2026-05-17 (30 days — stable patterns, stable yt-dlp, SQLAlchemy 2.0 LTS)

## Sources

### Primary (HIGH confidence — codebase inspection, all file paths absolute)
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\domain\entities.py` — Video/Transcript/Frame/Analysis/WatchedAccount shape + docstring conventions
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\domain\values.py` — NewType + StrEnum pattern
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\ports\repositories.py` — all 7 existing repo Protocols in one file
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\ports\pipeline.py` — ProbeResult/ProbeStatus dataclass shape
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\ports\__init__.py` — re-export convention
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\adapters\sqlite\schema.py` — MetaData registry + init_db idempotency + FTS5 raw DDL precedent
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\adapters\sqlite\video_repository.py` — canonical upsert pattern (lines 53-85)
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\adapters\sqlite\watch_account_repository.py` — canonical row↔entity translator pattern + datetime UTC handling
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\adapters\sqlite\unit_of_work.py` — UoW repo-slot pattern
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\adapters\sqlite\__init__.py` — re-export convention
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\adapters\ytdlp\downloader.py` — existing probe() impl (lines 264-315) + info_dict extraction helpers
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\infrastructure\container.py` — DI composition root (creators need NO new field here)
- `C:\Users\joaud\Documents\GitHub\vidscope\src\vidscope\infrastructure\sqlite_engine.py` — PRAGMA foreign_keys=ON listener (lines 51-60)
- `C:\Users\joaud\Documents\GitHub\vidscope\.importlinter` — 9 contracts verified
- `C:\Users\joaud\Documents\GitHub\vidscope\pyproject.toml` — `[project.scripts]` entry + mypy strict + pytest markers
- `C:\Users\joaud\Documents\GitHub\vidscope\tests\unit\adapters\sqlite\conftest.py` — engine fixture pattern
- `C:\Users\joaud\Documents\GitHub\vidscope\tests\unit\adapters\sqlite\test_video_repository.py` — adapter test style
- `C:\Users\joaud\Documents\GitHub\vidscope\tests\unit\adapters\sqlite\test_watch_account_repository.py` — mirror target
- `C:\Users\joaud\Documents\GitHub\vidscope\tests\unit\adapters\sqlite\test_schema.py` — schema test pattern
- `C:\Users\joaud\Documents\GitHub\vidscope\tests\unit\application\conftest.py` — uow_factory + FrozenClock pattern
- `C:\Users\joaud\Documents\GitHub\vidscope\tests\unit\application\test_watchlist.py` — `_FakeDownloader` stub pattern (lines 213-237)
- `C:\Users\joaud\Documents\GitHub\vidscope\tests\architecture\test_layering.py` — EXPECTED_CONTRACTS list + drift observation
- `C:\Users\joaud\Documents\GitHub\vidscope\.gsd\DECISIONS.md` — D005, D006, D014, D018, D019, D020, D028, D029
- `C:\Users\joaud\Documents\GitHub\vidscope\.gsd\REQUIREMENTS.md` — R040, R041, R042

### Secondary (MEDIUM confidence — cross-referenced)
- SQLite documentation — `ALTER TABLE ADD COLUMN` with `REFERENCES` clause supported since 3.26 (2018); `DROP COLUMN` since 3.35 (2021). Both well above the Python 3.12 stdlib `sqlite3` floor (3.39+).
- yt-dlp info_dict fields — `uploader`, `uploader_id`, `uploader_url`, `channel_follower_count`, `uploader_thumbnail`: documented yt-dlp contract; already referenced in CONTEXT.md's source note and used for the `author` field in `_info_to_outcome` (`downloader.py:392`).

### Tertiary (LOW confidence — not a blocker)
- None. Every critical claim is backed by a codebase file path.

## RESEARCH COMPLETE
