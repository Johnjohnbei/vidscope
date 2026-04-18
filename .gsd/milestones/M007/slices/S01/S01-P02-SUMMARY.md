---
plan_id: S01-P02
phase: M007/S01
subsystem: persistence
tags: [sqlite, schema, hashtags, mentions, repositories, unit-of-work]
dependency_graph:
  requires: [S01-P01]
  provides: [hashtag-persistence, mention-persistence, video-metadata-persistence]
  affects: [S03-pipeline-wiring, S04-search-facets]
tech_stack:
  added: []
  patterns:
    - DELETE-INSERT idempotent replace_for_video (mirrors CreatorRepositorySQLite)
    - ALTER TABLE idempotent helper (_ensure_videos_metadata_columns)
    - Protocol ports + SQLite adapters + UnitOfWork wiring
key_files:
  created:
    - src/vidscope/adapters/sqlite/hashtag_repository.py
    - src/vidscope/adapters/sqlite/mention_repository.py
    - tests/unit/adapters/sqlite/test_hashtag_repository.py
    - tests/unit/adapters/sqlite/test_mention_repository.py
  modified:
    - src/vidscope/adapters/sqlite/schema.py
    - src/vidscope/adapters/sqlite/video_repository.py
    - src/vidscope/adapters/sqlite/unit_of_work.py
    - src/vidscope/ports/repositories.py
    - src/vidscope/ports/unit_of_work.py
    - src/vidscope/ports/__init__.py
    - tests/unit/adapters/sqlite/test_video_repository.py
    - tests/unit/adapters/sqlite/test_schema.py
decisions:
  - "Schema inline + ALTER TABLE upgrade path for description/music_track/music_artist (mirrors _ensure_videos_creator_id)"
  - "HashtagRepositorySQLite and MentionRepositorySQLite created in T02 (not T03) to unblock mypy — Rule 3 deviation"
  - "Restored scripts/backfill_creators.py deleted by staged-reset side-effect — Rule 3 deviation"
metrics:
  duration: "~45 minutes"
  completed: "2026-04-18"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 8
  tests_added: 30
  tests_total_after: 778
---

# Phase M007 Plan S01-P02: SQLite persistence layer for rich content metadata

**One-liner:** SQLite side tables for hashtags and mentions with FK-CASCADE + idempotent ALTER TABLE migration for `description`/`music_track`/`music_artist` columns on `videos`, wired into ports Protocols and `SqliteUnitOfWork`.

## Tasks Executed

| # | Task | Commit | Status |
|---|------|--------|--------|
| T01 | Étendre schema.py : ALTER TABLE videos + tables hashtags/mentions (idempotent) | `6669f2f` | Done |
| T02 | Ajouter HashtagRepository + MentionRepository Protocols et les wire dans UnitOfWork | `867931f` | Done |
| T03 | Implémenter HashtagRepositorySQLite + MentionRepositorySQLite, étendre VideoRepositorySQLite + tests | `889871c` | Done |

## What Was Built

### T01 — Schema extension
- Added `description TEXT`, `music_track VARCHAR(255)`, `music_artist VARCHAR(255)` columns inline on `videos` table (fresh installs via `metadata.create_all`)
- Added `hashtags` side table: `id`, `video_id FK CASCADE`, `tag VARCHAR(255)`, `created_at` + 2 indexes (`idx_hashtags_video_id`, `idx_hashtags_tag`)
- Added `mentions` side table: `id`, `video_id FK CASCADE`, `handle VARCHAR(255)`, `platform VARCHAR(32) nullable`, `created_at` + 2 indexes
- Added `_ensure_videos_metadata_columns` helper for idempotent ALTER TABLE on upgraded databases (mirrors `_ensure_videos_creator_id` pattern exactly)
- Updated `init_db` to call `_ensure_videos_metadata_columns`
- Updated `__all__` to export `hashtags` and `mentions`

### T02 — Ports and UnitOfWork
- Added `HashtagRepository` Protocol: `replace_for_video`, `list_for_video`, `find_video_ids_by_tag`
- Added `MentionRepository` Protocol: `replace_for_video`, `list_for_video`, `find_video_ids_by_handle`
- Added `Hashtag` and `Mention` to `repositories.py` domain imports
- Added `hashtags: HashtagRepository` and `mentions: MentionRepository` to `UnitOfWork` Protocol
- Updated `ports/__init__.py` to re-export both new Protocols

### T03 — SQLite adapters and tests
- `HashtagRepositorySQLite`: canonicalises tags (`#Coding` → `coding`), DELETE-INSERT idempotent, deduplication within call
- `MentionRepositorySQLite`: canonicalises handles (`@Alice` → `alice`), deduplication by `(handle, platform)`, optional `platform`
- `VideoRepositorySQLite`: `_video_to_row` and `_row_to_video` extended with `description`/`music_track`/`music_artist`
- `SqliteUnitOfWork`: `hashtags` and `mentions` slots declared and instantiated in `__enter__`
- Tests: 9 hashtag tests, 11 mention tests, 2 video M007 round-trip tests, 8 schema M007 tests

## Verification Results

```
778 tests pass, 5 deselected
ruff check: exit 0 (no errors in src/ and tests/)
mypy src: Success, no issues found in 91 source files
lint-imports: 9 contracts kept, 0 broken
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] HashtagRepositorySQLite and MentionRepositorySQLite created in T02**
- **Found during:** T02 — mypy reported `SqliteUnitOfWork` missing `hashtags`/`mentions` protocol members after ports were extended
- **Issue:** Adding `hashtags: HashtagRepository` and `mentions: MentionRepository` to the `UnitOfWork` Protocol caused mypy to reject `SqliteUnitOfWork.__enter__` return type (missing members)
- **Fix:** Created `hashtag_repository.py` and `mention_repository.py` SQLite adapters and wired them into `SqliteUnitOfWork` during T02 rather than waiting for T03
- **Files modified:** `src/vidscope/adapters/sqlite/hashtag_repository.py`, `src/vidscope/adapters/sqlite/mention_repository.py`, `src/vidscope/adapters/sqlite/unit_of_work.py`
- **Commit:** `867931f`

**2. [Rule 3 - Blocking] Restored scripts/backfill_creators.py**
- **Found during:** T03 full test suite run — `tests/unit/scripts/test_backfill_creators.py` raised `FileNotFoundError` during collection
- **Issue:** The `git reset --soft d9e5b003` + `git checkout d9e5b003 -- src/ tests/` at worktree initialization staged a deletion of `scripts/backfill_creators.py` (M006 script not present in the target commit tree). The T01 commit included this deletion. The test file referencing it was not deleted (it's under `tests/`).
- **Fix:** Restored `scripts/backfill_creators.py` from git history (`e855580`)
- **Files modified:** `scripts/backfill_creators.py`
- **Commit:** `889871c`

## Known Stubs

None — all repository methods are fully implemented (not stubs). The `...` notation in Protocol definitions is the correct Python Protocol stub syntax, not placeholder implementations.

## Threat Flags

None — new surfaces (hashtags/mentions tables) were already in the plan's threat model (T-S01P02-01 through T-S01P02-05). No additional unplanned network endpoints, auth paths, or trust-boundary schema changes were introduced.

## Self-Check: PASSED

Files exist:
- FOUND: src/vidscope/adapters/sqlite/hashtag_repository.py
- FOUND: src/vidscope/adapters/sqlite/mention_repository.py
- FOUND: tests/unit/adapters/sqlite/test_hashtag_repository.py
- FOUND: tests/unit/adapters/sqlite/test_mention_repository.py

Commits exist:
- FOUND: 6669f2f (T01 schema)
- FOUND: 867931f (T02 ports + adapters)
- FOUND: 889871c (T03 tests + video_repository)
