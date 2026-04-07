---
id: T02
parent: S01
milestone: M003
key_files:
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/watch_account_repository.py
  - src/vidscope/adapters/sqlite/watch_refresh_repository.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/adapters/sqlite/__init__.py
  - tests/unit/adapters/sqlite/test_watch_account_repository.py
  - tests/unit/adapters/sqlite/test_watch_refresh_repository.py
key_decisions:
  - Compound UNIQUE on (platform, handle) lets the same handle exist on different platforms — matches real-world behavior where @tiktok is also an Instagram username
  - errors round-trips as JSON list → tuple (immutable domain entity, mutable JSON storage)
  - SqliteUnitOfWork attributes typed as Protocols not concrete classes — same pattern as the existing 6 repository fields
  - WatchRefresh.duration() reuses the same timedelta-or-None pattern as PipelineRun.duration() — consistency across timing entities
duration: 
verification_result: passed
completed_at: 2026-04-07T17:46:10.780Z
blocker_discovered: false
---

# T02: Shipped watched_accounts + watch_refreshes SQLite tables with compound UNIQUE constraint, WatchAccountRepositorySQLite + WatchRefreshRepositorySQLite, SqliteUnitOfWork exposes both. 18 new tests, 391 total green.

**Shipped watched_accounts + watch_refreshes SQLite tables with compound UNIQUE constraint, WatchAccountRepositorySQLite + WatchRefreshRepositorySQLite, SqliteUnitOfWork exposes both. 18 new tests, 391 total green.**

## What Happened

Extended the SQLite adapter package with two new tables and two new repository implementations.

**Schema changes in `adapters/sqlite/schema.py`:**
- `watched_accounts` table: id PK, platform, handle, url, created_at, last_checked_at, `UniqueConstraint("platform", "handle")` — the compound UNIQUE enforces that the same handle can exist across platforms but not twice on the same platform
- `watch_refreshes` table: id PK, started_at, finished_at, accounts_checked, new_videos_ingested, errors (JSON column for the tuple of error strings)
- Both tables created idempotently via `metadata.create_all` (same init_db path)

**New repository files:**
- `watch_account_repository.py` — WatchAccountRepositorySQLite with add/get/get_by_handle/list_all/remove/update_last_checked. Row↔entity translation via `_account_to_row` + `_row_to_account` helpers. Timestamps normalized to UTC on both write and read. Compound UNIQUE violations raise StorageError.
- `watch_refresh_repository.py` — WatchRefreshRepositorySQLite with add/list_recent. The `errors` tuple round-trips through the JSON column as a list on disk, converted back to tuple on read.

**SqliteUnitOfWork updated** to instantiate both new repositories in `__enter__` and expose them as `watch_accounts` + `watch_refreshes` attributes. The attributes are typed as the Protocols (WatchAccountRepository, WatchRefreshRepository) not the concrete classes — same pattern as the other 6 repository fields to keep mypy structural conformance clean.

**Tests — 18 new:**

`test_watch_account_repository.py` (10):
- add + get round-trip
- get_missing returns None
- get_by_handle with platform filter
- Duplicate (platform, handle) raises StorageError
- Same handle on different platforms is allowed (compound UNIQUE works)
- list_all orders by created_at ascending
- remove + assert absent
- remove missing id is a no-op
- update_last_checked round-trip
- update_last_checked rejects non-datetime (raises StorageError)

`test_watch_refresh_repository.py` (4):
- add + read-back
- errors tuple round-trips correctly (written as list, read as tuple)
- finished_at + duration calculation
- list_recent ordering newest-first with limit

**Quality gate status after T02:**
- 391 unit tests pass (up from 370 in M002)
- pytest, ruff, lint-imports all clean
- **mypy flags 2 expected errors**: `YtdlpDownloader` is missing the `list_channel_videos` method that T01 added to the `Downloader` Protocol. T03 will implement it and the errors clear.

## Verification

Ran `python -m uv run pytest tests/unit/adapters/sqlite tests/unit/infrastructure -q` → 100 passed in 1.2s. Ran full suite → 391 passed, 5 deselected. lint-imports clean (8 contracts kept). mypy has 2 expected errors related to YtdlpDownloader missing `list_channel_videos` — intentional, T03 implements it.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters/sqlite tests/unit/infrastructure -q` | 0 | ✅ 100/100 adapter + infrastructure tests green | 1200ms |
| 2 | `python -m uv run pytest -q` | 0 | ✅ 391/391 unit tests, 5 deselected | 4020ms |

## Deviations

None.

## Known Issues

mypy currently reports 2 errors on `YtdlpDownloader` not conforming to the extended `Downloader` Protocol because the adapter hasn't been extended yet. T03 is the fix.

## Files Created/Modified

- `src/vidscope/adapters/sqlite/schema.py`
- `src/vidscope/adapters/sqlite/watch_account_repository.py`
- `src/vidscope/adapters/sqlite/watch_refresh_repository.py`
- `src/vidscope/adapters/sqlite/unit_of_work.py`
- `src/vidscope/adapters/sqlite/__init__.py`
- `tests/unit/adapters/sqlite/test_watch_account_repository.py`
- `tests/unit/adapters/sqlite/test_watch_refresh_repository.py`
