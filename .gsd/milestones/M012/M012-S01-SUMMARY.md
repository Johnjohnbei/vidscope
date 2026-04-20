---
phase: M012
plan: S01
subsystem: ingest
tags: [metadata, description, engagement, instagram, ytdlp, schema-migration]
dependency_graph:
  requires: [M011/S01, M009/S01]
  provides: [R060, R061]
  affects: [ingest-pipeline, videos-table, video-stats-table]
tech_stack:
  added: []
  patterns: [additive-ALTER-TABLE-migration, idempotent-init_db, dataclass-extension, VideoStats-append]
key_files:
  created: []
  modified:
    - src/vidscope/ports/pipeline.py
    - src/vidscope/adapters/sqlite/schema.py
    - src/vidscope/adapters/sqlite/video_repository.py
    - src/vidscope/adapters/instaloader/downloader.py
    - src/vidscope/adapters/ytdlp/downloader.py
    - src/vidscope/pipeline/stages/ingest.py
    - tests/unit/ports/test_ingest_outcome.py
    - tests/unit/adapters/instaloader/test_downloader.py
    - tests/unit/adapters/ytdlp/test_downloader.py
    - tests/unit/adapters/sqlite/test_video_repository.py
    - tests/unit/adapters/sqlite/test_schema.py
    - tests/unit/pipeline/stages/test_ingest.py
decisions:
  - "description column added to SQLAlchemy Table definition (not only via ALTER TABLE) to allow Core INSERT/UPDATE to include it"
  - "IngestStage VideoStats append left inside the tempdir context manager (before message) to ensure rollback on failure"
  - "TestInfoToOutcomeEngagement uses YtdlpDownloader.download() + monkeypatch pattern (not _info_to_outcome directly) to stay consistent with TestInfoToOutcomeM007"
metrics:
  duration: ~60min
  completed: "2026-04-20T21:41:12Z"
  tasks_completed: 12
  files_changed: 12
---

# Phase M012 Plan S01: Metadata coherence at ingest — Summary

**One-liner:** Description (full caption) + initial engagement stats (like/comment) persisted at ingest time via schema migration, port extension, two downloader adapters, and IngestStage wiring — `vidscope show <id>` is now source of truth immediately after `add`.

## Tasks Completed

| Task | Name | Commit | Status |
|------|------|--------|--------|
| T01 | Schema migration: add description TEXT to videos | 99530fd | Done |
| T02 | Port: add like_count/comment_count to IngestOutcome | cf3d49c | Done |
| T03 | VideoRepository: map description field | 548c146 | Done |
| T04 | InstaLoaderDownloader: populate description + engagement | 063f3bd | Done |
| T05 | YtdlpDownloader: populate like_count + comment_count | 071ae9e | Done |
| T06 | IngestStage: wire description to Video + persist VideoStats | 00ff635 | Done |
| T07 | Test: IngestOutcome engagement fields | d594296 | Done |
| T08 | Test: InstaLoaderDownloader description + engagement | 6e9c0a0 | Done |
| T09 | Test: YtdlpDownloader._info_to_outcome engagement | dd5fa51 | Done |
| T10 | Test: IngestStage description + VideoStats persistence | ec2be9b | Done |
| T11 | Test: VideoRepository description round-trip | 671cd55 | Done |
| T12 | Test: Schema migration idempotence | 3878bc1 | Done |

## Requirements Coverage

**R060 — videos.description contains full caption at ingest:**
- T01: `_ensure_description_column` migration adds `TEXT` nullable column
- T03: `_video_to_row` / `_row_to_video` round-trip
- T04: `InstaLoaderDownloader` sets `description=post.caption` (full, non-truncated)
- T06: `IngestStage` passes `description=outcome.description` to `Video(...)`
- T11: Round-trip verified by test

**R061 — video_stats contains initial like_count/comment_count without refresh-stats:**
- T02: `IngestOutcome` extended with `like_count`, `comment_count`
- T04: `InstaLoaderDownloader` sets `like_count=post.likes`, `comment_count=post.comments`
- T05: `YtdlpDownloader._info_to_outcome` sets `like_count=_int_or_none(info.get("like_count"))`, etc.
- T06: `IngestStage` conditionally appends `VideoStats` when `like_count or comment_count is not None`
- T10: E2E test verifies the complete chain

## Test Results

```
162 tests in M012/S01 scope: PASSED
1658 tests total (tests/unit): PASSED
0 regressions
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing column in SQLAlchemy Table definition] description not declared in Core Table**
- **Found during:** T03 (VideoRepository tests)
- **Issue:** The plan instructed "Ne PAS modifier la définition SQLAlchemy Core de la table videos". However, SQLAlchemy Core `INSERT`/`UPDATE` via `videos_table.insert().values(**payload)` only knows declared columns — passing `description` caused `Unconsumed column names: description` error.
- **Fix:** Added `Column("description", Text, nullable=True)` to the `videos` Table definition in `schema.py`. The `_ensure_description_column` ALTER TABLE migration remains for pre-existing DBs without the column.
- **Files modified:** `src/vidscope/adapters/sqlite/schema.py`
- **Commit:** 548c146

## Known Stubs

None — all fields are wired end-to-end. `description` and engagement stats flow from downloader to DB to `vidscope show` without any placeholder.

## Threat Flags

No new network endpoints, auth paths, or file access patterns introduced. All mitigations from the plan's threat model are satisfied:
- T-M012-01: `_add_columns_if_missing` allowlist `{"TEXT"}` in place
- T-M012-02: SQLAlchemy bind params used throughout (no raw SQL with user data)
- T-M012-05: `VideoStats.append` uses existing `ON CONFLICT DO NOTHING` (M009/D-01)

## Self-Check: PASSED
