---
plan_id: S02-P01
phase: M007/S02
subsystem: domain + ports + sqlite-adapter
tags: [link-entity, link-repository, link-extractor-port, sqlite, schema]
dependency_graph:
  requires: [M007/S01-P02]
  provides: [Link entity, LinkExtractor port, LinkRepository port, LinkRepositorySQLite, links table]
  affects: [M007/S02-P02, M007/S03, M007/S04]
tech_stack:
  added: []
  patterns: [frozen-dataclass-slots, protocol-port, sqlalchemy-core-side-table, in-memory-dedup]
key_files:
  created:
    - src/vidscope/ports/link_extractor.py
    - src/vidscope/adapters/sqlite/link_repository.py
    - tests/unit/adapters/sqlite/test_link_repository.py
  modified:
    - src/vidscope/domain/entities.py
    - src/vidscope/domain/__init__.py
    - src/vidscope/ports/repositories.py
    - src/vidscope/ports/unit_of_work.py
    - src/vidscope/ports/__init__.py
    - src/vidscope/adapters/sqlite/schema.py
    - src/vidscope/adapters/sqlite/unit_of_work.py
    - tests/unit/domain/test_entities.py
    - tests/unit/adapters/sqlite/test_schema.py
decisions:
  - "Link frozen dataclass uses slots=True, same pattern as Hashtag/Mention"
  - "LinkRepositorySQLite created alongside schema (T01) to unblock mypy — wired into UoW early (Rule 3 auto-fix)"
  - "Dedup by (normalized_url, source) within add_many_for_video call only — no cross-call enforcement per plan"
  - "Three indexes on links table: video_id, normalized_url, source"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-18T10:04:22Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 9
---

# Phase M007 Plan S02-P01: Link Entity + Ports + SQLite Persistence — Summary

**One-liner:** Link frozen dataclass with slots, LinkExtractor/LinkRepository protocols, LinkRepositorySQLite with in-call dedup by (normalized_url, source), wired into SqliteUnitOfWork.

## What Was Built

### T01 — Link entity + LinkExtractor port + LinkRepository port

- **`Link` entity** added to `domain/entities.py`: frozen dataclass with `slots=True`, fields `video_id`, `url`, `normalized_url`, `source`, `position_ms: int | None = None`, `id: int | None = None`, `created_at`. Re-exported from `domain/__init__.py`.
- **`src/vidscope/ports/link_extractor.py`** (new): `RawLink` TypedDict + `LinkExtractor` Protocol with `extract(text, *, source) -> list[RawLink]`. Decorated `@runtime_checkable`.
- **`LinkRepository` Protocol** added to `ports/repositories.py`: 4 methods — `add_many_for_video`, `list_for_video`, `has_any_for_video`, `find_video_ids_with_any_link`. `Link` added to domain imports.
- **`UnitOfWork` Protocol** updated (`ports/unit_of_work.py`): `links: LinkRepository` added after `mentions`.
- **`ports/__init__.py`** updated: re-exports `LinkExtractor`, `RawLink`, `LinkRepository`.
- **`TestLink`** class added to `tests/unit/domain/test_entities.py` (5 tests: defaults, frozen, slots, raw vs normalized preservation, position_ms).

### T02 — links table + LinkRepositorySQLite + wire UoW + tests

- **`links` Table** added to `adapters/sqlite/schema.py`: columns `id`, `video_id` (FK CASCADE), `url`, `normalized_url`, `source`, `position_ms` (nullable), `created_at`. Three indexes: `idx_links_video_id`, `idx_links_normalized_url`, `idx_links_source`. `"links"` added to `__all__`.
- **`src/vidscope/adapters/sqlite/link_repository.py`** (new): `LinkRepositorySQLite` with `add_many_for_video` (in-memory dedup by `(normalized_url, source)`), `list_for_video` (optional source filter, ordered by id asc), `has_any_for_video`, `find_video_ids_with_any_link`. Helper `_row_to_link` + `_ensure_utc`.
- **`SqliteUnitOfWork`** updated: `links: LinkRepository` slot declared; `self.links = LinkRepositorySQLite(self._connection)` in `__enter__`; `LinkRepositorySQLite` and `LinkRepository` imported.
- **`tests/unit/adapters/sqlite/test_link_repository.py`** (new): 10 tests covering all behaviors from the plan.
- **`tests/unit/adapters/sqlite/test_schema.py`** extended: `TestLinksSchema` with 6 tests (table existence, columns, 3 indexes, sqlite_master DDL).

## Verification

```
799 passed, 5 deselected (pre-existing deselects unchanged)
mypy: Success (93 files)
lint-imports: 9 contracts kept, 0 broken
ruff: All checks passed on plan files
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] LinkRepositorySQLite created in T01 to unblock mypy**
- **Found during:** T01 — after adding `links: LinkRepository` to the `UnitOfWork` Protocol and `SqliteUnitOfWork` slot declaration, mypy reported `SqliteUnitOfWork` missing the `links` member because `link_repository.py` did not exist yet.
- **Fix:** Created `link_repository.py` and wired it into `SqliteUnitOfWork` as part of T01 (before T02). The full implementation (schema table, tests) was still delivered as T02.
- **Files modified:** `src/vidscope/adapters/sqlite/link_repository.py` (created), `src/vidscope/adapters/sqlite/unit_of_work.py` (wired), `src/vidscope/adapters/sqlite/schema.py` (links table added early)
- **Commit:** `5d4d011`

## Known Stubs

None — `LinkRepositorySQLite` is fully implemented with all 4 protocol methods. No placeholder data flows to any caller.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary crossings introduced. `links.url`/`normalized_url` values pass through SQLAlchemy Core parameterized binding (T-S02P01-01 mitigated as planned).

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `src/vidscope/domain/entities.py` | FOUND |
| `src/vidscope/ports/link_extractor.py` | FOUND |
| `src/vidscope/adapters/sqlite/link_repository.py` | FOUND |
| `tests/unit/adapters/sqlite/test_link_repository.py` | FOUND |
| `.gsd/milestones/M007/slices/S02/S02-P01-SUMMARY.md` | FOUND |
| commit `5d4d011` (T01) | FOUND |
| commit `be3ce93` (T02) | FOUND |
