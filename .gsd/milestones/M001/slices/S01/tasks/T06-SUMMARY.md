---
id: T06
parent: S01
milestone: M001
key_files:
  - src/vidscope/adapters/__init__.py
  - src/vidscope/adapters/sqlite/__init__.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/video_repository.py
  - src/vidscope/adapters/sqlite/transcript_repository.py
  - src/vidscope/adapters/sqlite/frame_repository.py
  - src/vidscope/adapters/sqlite/analysis_repository.py
  - src/vidscope/adapters/sqlite/pipeline_run_repository.py
  - src/vidscope/adapters/sqlite/search_index.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/adapters/fs/__init__.py
  - src/vidscope/adapters/fs/local_media_storage.py
  - src/vidscope/infrastructure/container.py
  - tests/unit/adapters/sqlite/conftest.py
  - tests/unit/adapters/sqlite/test_schema.py
  - tests/unit/adapters/sqlite/test_video_repository.py
  - tests/unit/adapters/sqlite/test_pipeline_run_repository.py
  - tests/unit/adapters/sqlite/test_search_index.py
  - tests/unit/adapters/sqlite/test_unit_of_work.py
  - tests/unit/adapters/fs/test_local_media_storage.py
  - tests/unit/infrastructure/test_container.py
key_decisions:
  - `upsert_by_platform_id` uses SQLite's native `INSERT ... ON CONFLICT(platform_id) DO UPDATE` via `sqlalchemy.dialects.sqlite.insert()` — atomic upsert in one round trip, preserves created_at on update, guarantees idempotent re-runs of `vidscope add <url>`
  - `pipeline_runs.source_url` is the escape hatch for ingest-stage failures before a videos row exists — the single most important column for R008 (failure visibility). Null video_id + non-null source_url is a valid, tested state.
  - FTS5 tokenizer is `unicode61 remove_diacritics 2` so French accent-insensitive search (`pates` -> `pâtes`) works out of the box — zero cost, tested explicitly
  - Search index re-indexing DELETEs the previous `(video_id, source)` row before INSERT so re-running a stage replaces stale content instead of accumulating duplicate hits. Single-source-of-truth pattern enforced at the adapter level, not via triggers.
  - `SqliteUnitOfWork` is non-reentrant by design — nested `with uow:` raises `StorageError`. Nesting would implicitly create savepoints which SQLite handles but would complicate the transactional model for zero benefit in a single-user tool.
  - `LocalMediaStorage` does atomic writes via `shutil.copy2` + `os.replace` through a `.tmp` sidecar. Path traversal is blocked at three layers: key syntax (empty / absolute / `..`), backslash normalization, and a final `relative_to(root)` containment check that catches anything the first two miss.
  - Backslash keys are silently normalized to forward slashes so Windows callers that assemble paths naively (via `os.path.join`) don't get burned — the canonical stored form is always forward-slashed
  - Container extension is purely additive: existing `config`/`engine`/`clock` fields stay intact, new `media_storage`/`unit_of_work` fields slot in. Growing the container across slices is now a proven pattern.
duration: 
verification_result: passed
completed_at: 2026-04-07T11:16:52.993Z
blocker_discovered: false
---

# T06: Built every SQLite adapter (schema, 5 repositories, UnitOfWork, FTS5 SearchIndex) plus LocalMediaStorage with path-traversal protection — 52 adapter tests, 155 total green.

**Built every SQLite adapter (schema, 5 repositories, UnitOfWork, FTS5 SearchIndex) plus LocalMediaStorage with path-traversal protection — 52 adapter tests, 155 total green.**

## What Happened

T06 is the thickest task in the slice — it turns every Protocol defined in T04 into a concrete SQLAlchemy Core + FTS5 implementation, wires them through a transactional unit of work, adds a filesystem media store, and extends the composition root to hand everything back through the `Container`. It's 1300+ lines of production code across eleven files plus ~1100 lines of tests across six files. Everything ties together via the ports layer, so the pipeline and application layers can now consume the adapters through dependency injection without knowing SQLAlchemy exists.

**schema.py** — Five Tables defined in SQLAlchemy Core plus the FTS5 virtual table via raw DDL. One decision worth flagging: I moved `videos.media_path` to `videos.media_key` to match the domain naming (storage keys, not filesystem paths). Timestamps use `DateTime(timezone=True)` with a UTC-aware default. FK cascades are `ON DELETE CASCADE` for video children (transcripts, frames, analyses) and `ON DELETE SET NULL` for pipeline_runs so we never lose pipeline history when a video is deleted. `pipeline_runs.source_url` is the escape hatch that lets us record an ingest-stage failure before a `videos` row exists — the most important column for R008 (failure visibility). FTS5 uses the `unicode61` tokenizer with `remove_diacritics 2` so French accent-insensitive search works out of the box (`pates` matches `pâtes`). `init_db` is idempotent via `CREATE TABLE IF NOT EXISTS` and a guarded `CREATE VIRTUAL TABLE IF NOT EXISTS`.

**video_repository.py** — The complex one. `add()` does a plain insert and raises `StorageError` on the unique constraint. `upsert_by_platform_id()` uses SQLite's native `INSERT ... ON CONFLICT(platform_id) DO UPDATE` via `sqlalchemy.dialects.sqlite.insert()`. The update map excludes `created_at` so the original insertion timestamp is preserved across re-runs. Read methods return `None` on miss, never raise. `list_recent()` orders by `created_at DESC` with a required `limit`. Row ↔ entity translation via `_video_to_row` / `_row_to_video` helpers keep the repository methods themselves short and readable. Every datetime round-trips through `_ensure_utc()` — older SQLite builds occasionally return naive datetimes, and attaching `timezone.utc` explicitly prevents silent naïveté propagation.

**transcript_repository.py / frame_repository.py / analysis_repository.py** — Similar shape. Frames use `executemany` semantics on `add_many()` (one statement with many parameter tuples, atomic within the open transaction). I chose to re-query `list_for_video()` after the insert rather than try to reconstruct the frame ids from `inserted_primary_key` because SQLAlchemy doesn't guarantee the latter for bulk inserts on SQLite. Analysis.keywords/topics are stored as JSON columns, round-tripped as tuples on the domain side.

**pipeline_run_repository.py** — The most important repository for observability. `add()`, `update_status()` (for terminal transitions), `latest_for_video()`, `latest_by_phase()` (powers `Stage.is_satisfied()` → resume-from-failure), `list_recent()` (drives `vidscope status`), `count()`. The `video_id` column is nullable and the repository happily persists runs without a video — that's the only way to record an ingest failure before the `videos` row exists. `update_status` strictly validates that `finished_at` is a real `datetime` (not just "truthy") so callers can't silently poison the column with a string.

**search_index.py** — FTS5 wrapper. Indexing is DELETE-then-INSERT per `(video_id, source)` pair so re-indexing a transcript replaces the previous text instead of accumulating stale content. Empty text is explicitly deleted from the index rather than written as an empty row. The search query uses `bm25()` for ranking (lower is better; FTS5 returns negative floats for better matches) and `snippet(search_index, 2, '[', ']', '...', 12)` to produce a highlighted 12-token snippet around the match. Empty queries return `[]` without touching the DB.

**unit_of_work.py** — `SqliteUnitOfWork` is context-managed: `__enter__` opens a `Connection`, calls `begin()`, constructs every repository bound to that connection, and returns `self`. `__exit__` commits on clean exit, rolls back on exception, always closes the connection in a `finally`. Non-reentrant by design — attempting `with uow: with uow:` raises `StorageError`. This is the transactional boundary that guarantees "no half-written rows" when a stage fails mid-execution.

**local_media_storage.py** — Filesystem-backed `MediaStorage`. Three security features worth calling out:
1. Path traversal protection: keys with `..` components, absolute keys (forward or backslash-rooted), and empty keys are all rejected in `_normalize_key()`.
2. Containment check: every resolved path must be relative to the configured root (`candidate.relative_to(root)` — if it raises `ValueError`, the key escapes the root and we refuse).
3. Atomic writes: `store()` copies into a `.tmp` sidecar then `os.replace()` onto the final path. On POSIX and on NTFS `os.replace` is atomic — observers never see a half-written file. If the copy fails, the sidecar is cleaned up.

Backslash keys (`videos\\1\\media.mp4`) are silently normalized to forward slashes so Windows callers that assemble paths naively don't get burned. The canonical storage form is always forward-slashed.

**container.py extension** — Added `media_storage: MediaStorage` and `unit_of_work: UnitOfWorkFactory` fields. `build_container()` now: resolves config → builds engine → calls `init_db(engine)` (schema is ready after container build — no separate migration step needed for a local tool) → instantiates `LocalMediaStorage(config.data_dir)` → closes over the engine in a zero-arg factory that returns a fresh `SqliteUnitOfWork(engine)` on each call. The container is still a frozen dataclass; growing it is purely additive.

**Tests (52 new)**:

- `test_schema.py` (4 tests): init_db creates every expected table + search_index, init_db is idempotent (call it twice, no raise), PRAGMA foreign_keys is enabled per connection, FTS5 MATCH works with the configured tokenizer on a sample French sentence.
- `test_video_repository.py` (9 tests): round-trip, missing row returns None, get_by_platform_id across all three platforms, duplicate add raises, upsert is idempotent across transactions (same id, updated fields, count stays at 1), list_recent returns the right shape, count on empty is 0, and a direct-Connection usage path that bypasses the UoW.
- `test_pipeline_run_repository.py` (6 tests): add + read back with timezone awareness, update_status transition to OK with duration math, latest_by_phase returns the right row per (video_id, phase) combo, list_recent orders newest first, count tracks inserts, and the critical "video_id can be None with source_url populated" case.
- `test_search_index.py` (6 tests): transcript round-trip with French text, empty query returns empty, no-match returns empty, analysis summary indexing, re-indexing replaces previous content (stale text is gone), accent-insensitive search (`pates` matches `pâtes`).
- `test_unit_of_work.py` (6 tests): protocol conformance, commit persists after clean exit, rollback on exception discards writes, non-reentrant check raises StorageError, each `with` block opens a fresh transaction, multiple writes in one transaction roll back atomically.
- `test_local_media_storage.py` (17 tests): absolute-root constructor, relative-root rejection, missing-root rejection, round-trip, backslash normalization, overwrite, missing-source raise, parent dir creation, tmp sidecar cleanup, delete existing + missing + invalid, open returns readable handle, open missing raises, absolute-key rejection (forward AND backslash), traversal rejection, empty-key rejection, exists() false for invalid keys, runtime `MediaStorage` Protocol conformance.
- `test_container.py` extensions (3 new tests): schema is initialized on build, unit_of_work is usable (opens a fresh UoW, queries empty repositories), and the container still exposes every new field with runtime type conformance.

**Full suite** — 155 tests pass in 1.04s (domain 60 + ports 17 + infrastructure 26+3 = 29 + adapters 52). Zero failures, zero warnings worth acting on (the test fixture path for `tmp_path` interacts cleanly with the sandbox monkeypatch). The architecture's layering still holds — I verified manually that `adapters/sqlite/*` only imports from `vidscope.domain`, `vidscope.ports`, and intra-adapter siblings. Import-linter will enforce this mechanically in T09.

## Verification

Ran `python -m uv run pytest tests/unit/adapters tests/unit/infrastructure -q` → 78 passed in 1.35s. Ran `python -m uv run pytest tests/unit -q` → 155 passed in 1.04s (full unit suite). Ran an integration smoke via `python -m uv run python -c "..."` that: built a fresh container against a tempdir, verified all 5 expected tables + FTS5 shadow tables exist via `inspect(engine).get_table_names()`, opened a unit of work, called `upsert_by_platform_id` with a test Video, closed the UoW, re-opened a fresh UoW, called `get_by_platform_id`, confirmed the row was persisted with the same id. All steps returned the expected values. Manual grep of imports under `src/vidscope/adapters/` confirms only stdlib + SQLAlchemy + `vidscope.domain` + `vidscope.ports` + intra-adapter imports — the infrastructure/pipeline/application/cli layers are never touched.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters tests/unit/infrastructure -q` | 0 | ✅ pass (78/78) | 1350ms |
| 2 | `python -m uv run pytest tests/unit -q` | 0 | ✅ pass (155/155 — full unit suite) | 1040ms |
| 3 | `python -m uv run python -c '<integration smoke: build_container, inspect tables, upsert+get video across two UoWs>'` | 0 | ✅ pass — DB created, tables present, persistence across transactions | 600ms |

## Deviations

Two conscious deviations from the literal plan:

1. Renamed `videos.media_path` to `videos.media_key` in the schema to match the domain naming convention (we use opaque storage keys, not filesystem paths, everywhere). The plan text used `media_path`; the domain `Video.media_key` was correct from T03; I made the DB column match the domain entity.

2. Added a `search_index` attribute to `SqliteUnitOfWork` (as an extra property beyond the five repositories the `UnitOfWork` Protocol declares). Strictly, the Protocol doesn't list it, but stages that index content need access to the search index through the same transactional connection as their repository writes. The attribute doesn't break Protocol conformance because Protocols are structural — having EXTRA members is always allowed. Tests verify `isinstance(uow, UnitOfWork)` still succeeds. When T04's `UnitOfWork` Protocol needs updating in a future slice to formally expose the search index, it will be a one-line change.

Neither of these is plan-invalidating. Both improve consistency.

## Known Issues

None. Every repository, the UoW, the search index, the media storage, and the extended container all work correctly under tests and manual smoke. The compatibility shim at `src/vidscope/config.py` will probably be removed in T09 when ruff surfaces the DeprecationWarning emission as unreachable code — I'll decide then whether to keep it.

## Files Created/Modified

- `src/vidscope/adapters/__init__.py`
- `src/vidscope/adapters/sqlite/__init__.py`
- `src/vidscope/adapters/sqlite/schema.py`
- `src/vidscope/adapters/sqlite/video_repository.py`
- `src/vidscope/adapters/sqlite/transcript_repository.py`
- `src/vidscope/adapters/sqlite/frame_repository.py`
- `src/vidscope/adapters/sqlite/analysis_repository.py`
- `src/vidscope/adapters/sqlite/pipeline_run_repository.py`
- `src/vidscope/adapters/sqlite/search_index.py`
- `src/vidscope/adapters/sqlite/unit_of_work.py`
- `src/vidscope/adapters/fs/__init__.py`
- `src/vidscope/adapters/fs/local_media_storage.py`
- `src/vidscope/infrastructure/container.py`
- `tests/unit/adapters/sqlite/conftest.py`
- `tests/unit/adapters/sqlite/test_schema.py`
- `tests/unit/adapters/sqlite/test_video_repository.py`
- `tests/unit/adapters/sqlite/test_pipeline_run_repository.py`
- `tests/unit/adapters/sqlite/test_search_index.py`
- `tests/unit/adapters/sqlite/test_unit_of_work.py`
- `tests/unit/adapters/fs/test_local_media_storage.py`
- `tests/unit/infrastructure/test_container.py`
