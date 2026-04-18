# Phase M006/S01: Creator domain entity + SQLite adapter + migration — Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

S01 delivers the **structural foundation** for creator-as-first-class-entity:
- `Creator` frozen dataclass (domain/entities.py)
- Value objects: `CreatorId`, `PlatformUserId` (domain/values.py)
- `CreatorRepository` Protocol (ports/creator_repository.py)
- `SqlCreatorRepository` concrete adapter (adapters/sqlite/creator_repository.py)
- Migration `003_creators.py` adds `creators` table + `videos.creator_id` FK (nullable)
- `videos.author` column **preserved** as denormalised cache (see D-03)
- Container wires the new repo
- Backfill script `scripts/backfill_creators.py` uses `Downloader.probe()` to populate `videos.creator_id` for existing M001–M005 rows
- All 9 import-linter contracts stay green; mypy strict stays clean; 80%+ line coverage on new modules

**Out of S01 (delivered in S02/S03 or later milestones):**
- yt-dlp extraction of creator info during live ingest → S02
- CLI `vidscope creator show/list/videos` → S03
- MCP tool `vidscope_get_creator` → S03
- `creator_stats` time-series table (creator-level velocity) → M009 (deferred; see below)
- Avatar image download & cache → out-of-scope (D-05 chose URL string only)
- Cross-platform identity resolution (same person on IG + TikTok) → out of M006 entirely
</domain>

<decisions>
## Implementation Decisions

### Identity & schema

- **D-01: Primary UNIQUE key = `(platform, platform_user_id)`** — `platform_user_id` stores yt-dlp's stable `uploader_id` (never changes on rename). `creators.id` remains a surrogate autoincrement INT PK so FKs and CLI arguments stay ergonomic, matching the 5 existing repos. `handle` is stored but **not** UNIQUE — renames are supported without data loss.
- **D-02: Backfill strategy = re-probe yt-dlp via `Downloader.probe()`** — The existing probe method (shipped in M005 for cookies test) returns platform metadata without downloading media. Script iterates every pre-M006 video, upserts the creator row, sets `videos.creator_id`. Mandatory `--dry-run` flag for preview. A video whose URL now 404s (deleted account) produces a creator row with `is_orphan=true` so the FK is populated and no data is lost.
- **D-03: `videos.author` preserved as denormalised cache** — The column stays. On every video upsert, `creator.display_name` is copied into `videos.author` inside the same transaction (write-through cache). Protects: (1) legacy SQL queries that read `videos.author`, (2) the existing FTS5 index on author, (3) minimal CLI display paths that don't need a JOIN. Sync is structurally enforced at the repository layer — no application code writes `videos.author` directly.

### Data shape

- **D-04: `follower_count` = scalar field on `creators`** — No time-series table in M006. M009's existing plan (per D031) already owns temporal engagement data through `video_stats`. If creator-level velocity becomes a requirement, M009 adds a symmetric `creator_stats` table; M006 stays lean (YAGNI).
- **D-05: Avatar = `avatar_url` string only** — No download, no MediaStorage write, no image I/O. Respects D010 (zero-cost default). If the creator later privatises their profile the URL may 404 — acceptable for a personal local tool.

### Creator entity final shape (canonical)

```python
@dataclass(frozen=True, slots=True)
class Creator:
    platform: Platform
    platform_user_id: PlatformUserId  # yt-dlp uploader_id — stable
    id: CreatorId | None = None        # surrogate autoincrement
    handle: str | None = None          # @username — may change
    display_name: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None      # URL string only (D-05)
    follower_count: int | None = None  # current value only (D-04)
    is_verified: bool | None = None
    is_orphan: bool = False             # True when backfill probe hit 404 (D-02)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime | None = None
```

### SQL migration shape (canonical)

```sql
CREATE TABLE creators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    platform_user_id TEXT NOT NULL,
    handle TEXT,
    display_name TEXT,
    profile_url TEXT,
    avatar_url TEXT,
    follower_count INTEGER,
    is_verified INTEGER,  -- 0/1
    is_orphan INTEGER NOT NULL DEFAULT 0,
    first_seen_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (platform, platform_user_id)
);
CREATE INDEX idx_creators_handle ON creators (platform, handle);
ALTER TABLE videos ADD COLUMN creator_id INTEGER REFERENCES creators(id) ON DELETE SET NULL;
CREATE INDEX idx_videos_creator_id ON videos (creator_id);
-- videos.author stays untouched (D-03)
```

### Claude's Discretion

- Exact SQLAlchemy Core column types — follow the conventions of the existing 5 adapters (`adapters/sqlite/schema.py`).
- `CreatorRepository` Protocol method signatures (keep idiomatic: `find_by_platform_user_id`, `upsert`, `find_by_handle`, `list_by_platform`, `list_by_min_followers` — the obvious shape).
- Internal test helpers (`InMemoryCreatorRepository` for application unit tests) — build as needed for ≥ 80% coverage.
- Exact wording of dry-run output in `backfill_creators.py` — informative but terse.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap and requirements
- `.gsd/milestones/M006/M006-ROADMAP.md` — slice breakdown, layer map, test strategy
- `.gsd/REQUIREMENTS.md` §R040, §R041, §R042 — creator entity, CLI surface, lossless backfill
- `.gsd/DECISIONS.md` D028, D029 — rationale for creator-as-entity + side-table pattern (upstream of M007)

### Architectural contracts to preserve
- `.gsd/DECISIONS.md` D005 (SQLite + FTS5), D006 (thin repo over SQLAlchemy Core), D014 (pytest+ruff+mypy strict), D018 (cross-platform), D019 (import-linter enforcement), D020 (hexagonal layer map)
- `.importlinter` (project root) — 9 existing contracts must remain green

### Existing patterns to mirror
- `src/vidscope/domain/entities.py` — Video/Transcript/Frame/Analysis frozen-dataclass style
- `src/vidscope/ports/` — existing Protocol definitions (video_repository, transcript_repository, etc.)
- `src/vidscope/adapters/sqlite/` — repository adapters, schema module, migration files
- `src/vidscope/adapters/sqlite/migrations/` — numbering and up/down pattern
- `src/vidscope/infrastructure/container.py` — DI wiring convention

### Probe reuse (backfill)
- `src/vidscope/ports/downloader.py` — `Downloader.probe()` Protocol method (shipped M005)
- `src/vidscope/adapters/ytdlp/ytdlp_downloader.py` — reference implementation of probe (metadata-only, download=False)

### Tests to not break
- `tests/unit/adapters/sqlite/` — existing migration + repo tests (add new but do not alter existing)
- `tests/architecture/test_import_linter.py` — 9 contracts must stay green
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **`Downloader.probe()` port method (M005)** — reused by the backfill script without any port change. Metadata-only, network but no disk write.
- **`InfrastructureContainer`** — DI pattern already handles all 5 existing repos; add `creator_repository` identically.
- **Migration harness** — numbered migrations with up/down halves. Follow exact pattern of `002_*.py`.
- **SQLAlchemy Core `MetaData` registry** in `adapters/sqlite/schema.py` — add `creators` table definition here, update `videos` table definition to include `creator_id` column.

### Established patterns
- Frozen slotted dataclasses with domain value-object types (`VideoId`, etc.) — `CreatorId` + `PlatformUserId` follow the exact pattern.
- Repository methods return domain entities, never SQLAlchemy rows. Upsert returns the entity with populated `id`.
- Every repo adapter has an adapter-level test file under `tests/unit/adapters/sqlite/` covering CRUD + UNIQUE + FK cascade.
- Transactional writes use the existing `UnitOfWork`; new creator upsert + video upsert must share the same UoW instance when called from IngestStage (S02 concern, but the UoW must expose both repos).

### Integration points
- `videos` table already carries `author: str | None` — migration adds `creator_id` as nullable INTEGER FK with `ON DELETE SET NULL` so deleting a creator does not cascade-delete videos.
- FTS5 `search_index` virtual table currently indexes `author` via triggers — this stays untouched since `videos.author` stays (D-03).
- `InfrastructureContainer.build()` must construct the new repo and pass it into the UnitOfWork. S02 consumers come later, but the wiring must be in place at end of S01 so S02 can plug in without re-wiring.
</code_context>

<specifics>
## Specific Ideas

- **Backfill dry-run is mandatory** — the CLI must default to dry-run; the destructive mode requires an explicit flag (e.g. `--apply`). One-shot scripts that silently mutate user data are a no-go.
- **`is_orphan=true`** for 404'd creators during backfill (rather than aborting or skipping) — every video gets a creator row, the FK is populated, and the orphan flag surfaces later in listings so the user can decide what to do.
- **Write-through cache on `videos.author`** is the explicit pattern: repository layer owns the sync, application code never sets `videos.author` directly. This is tested by a regression test: "updating `creator.display_name` and re-upserting the video updates `videos.author`".
</specifics>

<deferred>
## Deferred Ideas

### Scope creep redirected

- **"Vérification du nombre de likes / resends pour calculer la viralité"** (raised during gray-area selection) — **this is M009's scope**, already planned in `.gsd/milestones/M009/M009-ROADMAP.md`. Per-video engagement time-series (view/like/comment/share/save counts) lives in the append-only `video_stats` table (D031). If *creator-level* velocity becomes needed later, M009 will add a symmetric `creator_stats` table following the exact same append-only pattern — **M006/S01 leaves the door open by not pre-allocating that table (D-04)**.

### Future additive work (out of M006 entirely)

- **Avatar image download-and-cache** — possible as additive work if URL 404s become painful in practice. Adds a new adapter path using existing MediaStorage, no schema change needed (reuse `avatar_url` field as cache-key indirection).
- **Cross-platform identity resolution** — same person on IG + TikTok. Requires ML or user manual linking. Out of M006.
- **Creator clustering / niche auto-detection** — requires content analysis across a creator's catalogue. M010 territory at earliest.

</deferred>

---

*Phase: M006/S01*
*Context gathered: 2026-04-17*
