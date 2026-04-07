---
id: S01
parent: M003
milestone: M003
provides:
  - WatchedAccount + WatchRefresh entities
  - WatchAccountRepository + WatchRefreshRepository ports + SQLite implementations
  - ChannelEntry DTO
  - Downloader.list_channel_videos method (Protocol + YtdlpDownloader implementation)
  - UnitOfWork.watch_accounts + watch_refreshes wired in SqliteUnitOfWork
requires:
  - slice: M002 final state
    provides: All existing repositories, ports, and the YtdlpDownloader that S01 extends
affects:
  - S02 — builds WatchRefreshUseCase + vidscope watch CLI on top of these foundations
key_files:
  - src/vidscope/domain/entities.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/pipeline.py
  - src/vidscope/ports/unit_of_work.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/watch_account_repository.py
  - src/vidscope/adapters/sqlite/watch_refresh_repository.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/adapters/ytdlp/downloader.py
  - tests/unit/adapters/sqlite/test_watch_account_repository.py
  - tests/unit/adapters/sqlite/test_watch_refresh_repository.py
  - tests/unit/adapters/ytdlp/test_downloader.py
key_decisions:
  - Compound UNIQUE on (platform, handle) so the same handle can exist across platforms
  - list_channel_videos added to the existing Downloader Protocol — no new ChannelLister Protocol
  - Cookies honored on the listing path same as the download path
  - Separate yt-dlp options dict for listing (extract_flat + skip_download + playlist_items) vs downloads
patterns_established:
  - When extending an existing port with a new method, add it to the same Protocol if no new responsibility emerges — don't fragment for fragmentation's sake
observability_surfaces:
  - watched_accounts table is the inspection surface for the watchlist (visible via vidscope watch list in S02)
  - watch_refreshes table is the history of past refreshes
drill_down_paths:
  - .gsd/milestones/M003/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T17:49:44.075Z
blocker_discovered: false
---

# S01: Watchlist schema + WatchAccountRepository + channel listing

**Shipped the persistence + listing foundation for M003: WatchedAccount + WatchRefresh entities, 2 new SQLite tables with compound UNIQUE, 2 repositories, YtdlpDownloader.list_channel_videos via extract_flat. 398 tests green, 8 import-linter contracts kept.**

## What Happened

3 tasks: domain entities + ports (T01), SQLite schema + repositories (T02), YtdlpDownloader.list_channel_videos (T03). Pure additive extension of M002 — zero changes to existing pipeline stages or use cases.

**T01** added WatchedAccount + WatchRefresh dataclasses, WatchAccountRepository + WatchRefreshRepository Protocols, ChannelEntry DTO, list_channel_videos method on the Downloader Protocol, and watch_accounts + watch_refreshes attributes on the UnitOfWork Protocol.

**T02** added watched_accounts + watch_refreshes SQLite tables (compound UNIQUE on platform+handle), WatchAccountRepositorySQLite + WatchRefreshRepositorySQLite, SqliteUnitOfWork wires them. 14 new tests covering CRUD round-trips, compound UNIQUE behavior, list_recent ordering, errors-tuple JSON round-trip.

**T03** implemented YtdlpDownloader.list_channel_videos using `extract_flat=True` + `playlist_items='1-N'`. 7 new tests with stubbed yt-dlp. The approach was validated against the real @YouTube channel before T01 (~0.5s for 5 entries), so the design risk was retired upfront.

**Final state:** 398 unit tests pass, all 4 quality gates clean, 8 import-linter contracts kept (no new contract needed — the additions slot into existing layers cleanly).

## Verification

Ran `python -m uv run pytest -q` → 398 passed, 5 deselected. All 4 quality gates clean.

## Requirements Advanced

- R021 — Persistence layer for watched accounts shipped. CRUD operations validated.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

No live integration test for list_channel_videos in S01 — that ships in S02's verify-m003.sh. The probe test before T01 (extract_flat against @YouTube) already validated the approach works.

## Follow-ups

S02 builds WatchRefreshUseCase + CLI on top of these foundations.

## Files Created/Modified

- `src/vidscope/domain/entities.py` — Added WatchedAccount + WatchRefresh
- `src/vidscope/ports/repositories.py` — Added WatchAccountRepository + WatchRefreshRepository Protocols
- `src/vidscope/ports/pipeline.py` — Added ChannelEntry DTO + list_channel_videos method on Downloader Protocol
- `src/vidscope/ports/unit_of_work.py` — Added watch_accounts + watch_refreshes annotations
- `src/vidscope/adapters/sqlite/schema.py` — Added watched_accounts + watch_refreshes tables
- `src/vidscope/adapters/sqlite/watch_account_repository.py` — New repository implementation
- `src/vidscope/adapters/sqlite/watch_refresh_repository.py` — New repository implementation
- `src/vidscope/adapters/sqlite/unit_of_work.py` — Wires both new repositories
- `src/vidscope/adapters/ytdlp/downloader.py` — Added list_channel_videos using extract_flat
- `tests/unit/adapters/sqlite/test_watch_account_repository.py` — 10 new tests
- `tests/unit/adapters/sqlite/test_watch_refresh_repository.py` — 4 new tests
- `tests/unit/adapters/ytdlp/test_downloader.py` — 7 new tests for list_channel_videos
