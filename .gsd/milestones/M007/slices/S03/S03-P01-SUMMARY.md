---
plan_id: S03-P01
phase: M007/S03
subsystem: pipeline
tags: [ingest, ytdlp, hashtags, mentions, music, metadata, m007]
dependency_graph:
  requires: [M007/S01-P01, M007/S01-P02, M007/S02-P01, M007/S02-P02]
  provides: [ingest-outcome-rich-metadata, ingest-stage-hashtags-mentions-persistence]
  affects: [pipeline/stages/ingest.py, ports/pipeline.py, adapters/ytdlp/downloader.py]
tech_stack:
  added: []
  patterns: [TDD RED-GREEN-REFACTOR, frozen dataclass extension, DELETE-INSERT idempotent side tables]
key_files:
  created:
    - tests/unit/ports/test_ingest_outcome.py
  modified:
    - src/vidscope/ports/pipeline.py
    - src/vidscope/adapters/ytdlp/downloader.py
    - src/vidscope/pipeline/stages/ingest.py
    - tests/unit/adapters/ytdlp/test_downloader.py
    - tests/unit/pipeline/stages/test_ingest.py
decisions:
  - Uses stdlib re directly in ytdlp adapter (not adapters.text) to honour import-linter contract
  - _extract_mentions returns VideoId(0) placeholder; IngestStage rebinds to persisted.id
  - replace_for_video called unconditionally (even empty) to support idempotent re-ingest
metrics:
  duration_minutes: 45
  completed_date: "2026-04-18"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 4
  tests_added: 33
---

# Phase M007 Plan S03-P01: Pipeline Wiring — IngestOutcome + YtdlpDownloader + IngestStage Summary

JWT-style one-liner: IngestOutcome extended with 5 optional M007 fields; YtdlpDownloader extracts description/hashtags/mentions/music from info_dict; IngestStage persists all M007 data including side-table hashtags and mentions with VideoId rebinding.

## What Was Built

### T01 — IngestOutcome extension (backward-compatible)

`IngestOutcome` (frozen dataclass in `ports/pipeline.py`) gained 5 new optional fields with safe defaults:

- `description: str | None = None`
- `hashtags: tuple[str, ...] = ()`
- `mentions: tuple[Mention, ...] = ()`
- `music_track: str | None = None`
- `music_artist: str | None = None`

`Mention` was added to the domain import list. All M006 callers (4-field construction) continue working without change.

### T02 — YtdlpDownloader metadata extraction

Three new private helpers added to `adapters/ytdlp/downloader.py`:

- `_MENTION_PATTERN = re.compile(r"@([\w][\w.]{0,63})")` — bounded regex, ReDoS-safe (T-S03P01-02 mitigated)
- `_extract_mentions(description, platform)` — deduplicates by lowercased handle, returns `Mention` with `video_id=VideoId(0)` placeholder, `platform=None`
- `_extract_hashtags(info)` — extracts verbatim from `info["tags"]`, drops falsy entries
- `_extract_music_artist(info)` — prefers `info["artists"][0]`, falls back to `info["artist"]`

`_info_to_outcome` updated to populate all 5 new `IngestOutcome` fields.

Import: `re` stdlib only (no `adapters.text` — import-linter contract `ytdlp-never-imports-other-adapters` remains green).

### T03 — IngestStage persistence wiring

`IngestStage.execute()` modified in two places:

1. `Video(...)` construction now passes `description=`, `music_track=`, `music_artist=` (M007 D-01 direct columns).
2. After `uow.videos.upsert_by_platform_id(video, creator=creator)`:
   - `uow.hashtags.replace_for_video(persisted.id, list(outcome.hashtags))` — always called (DELETE-INSERT idempotence for re-ingest)
   - `rebound_mentions` list replaces `VideoId(0)` with `persisted.id` for each `Mention`
   - `uow.mentions.replace_for_video(persisted.id, rebound_mentions)` — same pattern

All writes happen in the same `UnitOfWork` transaction.

## Tests

| Suite | Added | Total |
|-------|-------|-------|
| `tests/unit/ports/test_ingest_outcome.py` | 4 | 4 (new file) |
| `tests/unit/adapters/ytdlp/test_downloader.py` | 24 | 76 |
| `tests/unit/pipeline/stages/test_ingest.py` | 5 | 48 |
| **Total suite** | **33** | **868 passing** |

## Verification

```
python -m uv run pytest -q                 → 868 passed, 5 deselected
python -m uv run mypy src                  → Success: no issues found in 96 source files
python -m uv run lint-imports              → Contracts: 10 kept, 0 broken
python -m uv run ruff check src tests      → All checks passed (modified files)
```

Backward-compat smoke test passed:
```
IngestOutcome(platform=YOUTUBE, platform_id='x', url='u', media_path='/tmp/x.mp4')
→ description=None, hashtags=(), mentions=(), music_track=None, music_artist=None
```

## Commits

| Task | Hash | Message |
|------|------|---------|
| T01 | 57c9b89 | feat(M007/S03-P01): extend IngestOutcome with 5 M007 fields |
| T02 | fc014c1 | feat(M007/S03-P01): extend YtdlpDownloader with M007 metadata extraction |
| T03 | 118eb93 | feat(M007/S03-P01): extend IngestStage to persist description/music/hashtags/mentions |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test used `for_video` instead of `list_for_video`**
- **Found during:** T03 RED→GREEN
- **Issue:** Plan doc and initial tests used `uow.hashtags.for_video()` / `uow.mentions.for_video()` but the actual repository method is `list_for_video()` (as defined in S01-P02)
- **Fix:** Replaced all 6 occurrences in test_ingest.py with `list_for_video()`
- **Files modified:** `tests/unit/pipeline/stages/test_ingest.py`
- **Commit:** 118eb93

**2. [Rule 2 - Cleanup] Removed unused imports in test_ingest.py**
- **Found during:** T03 ruff check
- **Issue:** `from vidscope.domain import Mention, VideoId` in `test_description_and_music_persisted_on_video_row` was unused (that test doesn't construct Mention objects)
- **Fix:** Removed the unused import line
- **Files modified:** `tests/unit/pipeline/stages/test_ingest.py`
- **Commit:** 118eb93

## Known Stubs

None — all M007 fields flow from yt-dlp info_dict through IngestOutcome to the database. No hardcoded placeholders or TODO markers in production code.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. The `_MENTION_PATTERN` regex is bounded (`{0,63}`) — T-S03P01-02 mitigated. All DB writes go through parameterised SQLAlchemy Core bindings (T-S03P01-03 mitigated by S01-P02 foundation).

## Self-Check: PASSED

Files exist:
- `src/vidscope/ports/pipeline.py` — FOUND (modified)
- `src/vidscope/adapters/ytdlp/downloader.py` — FOUND (modified)
- `src/vidscope/pipeline/stages/ingest.py` — FOUND (modified)
- `tests/unit/ports/test_ingest_outcome.py` — FOUND (created)

Commits exist:
- 57c9b89 — FOUND
- fc014c1 — FOUND
- 118eb93 — FOUND
