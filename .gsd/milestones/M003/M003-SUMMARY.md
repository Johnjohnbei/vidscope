---
id: M003
title: "Account monitoring and scheduled refresh"
status: complete
completed_at: 2026-04-07T18:04:43.719Z
key_decisions:
  - Compound UNIQUE on (platform, handle) — same handle can exist on YouTube and TikTok
  - list_channel_videos added to existing Downloader Protocol — no new ChannelLister Protocol
  - Snapshot existing video IDs once at refresh start — O(1) dedupe inside the loop
  - Per-account error capture: catch + record + continue, persist a summary row at the end
  - RefreshWatchlistUseCase reuses PipelineRunner unchanged — every newly discovered video flows through the same 5 stages as a manual `vidscope add`
  - VidScope is not a daemon — scheduling delegated to OS cron/launchd/Task Scheduler
  - Sub-application via add_typer — same shape as vidscope mcp
  - verify-m003.sh uses stubbed pipeline for CI determinism — manual live smoke documented in docs/watchlist.md
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
  - src/vidscope/application/watchlist.py
  - src/vidscope/cli/commands/watch.py
  - src/vidscope/cli/app.py
  - tests/unit/adapters/sqlite/test_watch_account_repository.py
  - tests/unit/adapters/sqlite/test_watch_refresh_repository.py
  - tests/unit/adapters/ytdlp/test_downloader.py
  - tests/unit/application/test_watchlist.py
  - tests/unit/cli/test_app.py
  - scripts/verify-m003.sh
  - docs/watchlist.md
lessons_learned:
  - When extending an existing Protocol with a new method, prefer extension over creating a new Protocol — keeps the import surface narrow
  - Snapshot-then-iterate is the right pattern for batch operations needing O(1) dedupe
  - Per-iteration error capture is more useful than fail-fast for long-running batch jobs that touch external services
  - OS-level scheduling is simpler than baking in a scheduler — ship a one-shot CLI command and let cron/launchd/Task Scheduler handle the cadence
  - Rapid task progression for additive features is fine when the foundation is solid — M003 was 6 tasks across 3 slices, no replans, no blockers
---

# M003: Account monitoring and scheduled refresh

**Shipped the watchlist: track public accounts on YouTube/TikTok/Instagram, refresh on demand, idempotent dedupe, per-account error capture, full CLI surface.**

## What Happened

M003 layered the watchlist on top of the M001 pipeline + M002 surface area without disturbing either. Three slices: persistence + listing primitives (S01), use cases + CLI sub-application (S02), docs + verify script + closure (S03).

The design philosophy: VidScope is not a daemon. The watchlist refresh is a short-lived operation that can be invoked manually (`vidscope watch refresh`) or scheduled by the OS (cron/launchd/Task Scheduler — documented in docs/watchlist.md). This keeps the implementation tiny: no background process, no message queue, no scheduler dependency. Just a SQLite-backed list of accounts and a use case that iterates them.

Idempotence was the key correctness invariant: running `vidscope watch refresh` twice in a row must ingest new videos on the first call and zero on the second. Achieved by snapshotting existing video platform_ids into an in-memory set at refresh start, then deduplicating each ChannelEntry against the set + adding newly-ingested ids back to the set during the iteration. Validated end-to-end by verify-m003.sh.

Per-account error capture was the second invariant: a broken account (rate-limited, deleted, requires login) must not block the rest of the watchlist. Achieved by a per-account try/except that records the error in the RefreshSummary and continues. The errors persist in the watch_refreshes.errors JSON column so users can audit what failed across runs.

Three external surfaces ship: the SQLite tables (with the existing init_db path), the YtdlpDownloader.list_channel_videos method (extending the Downloader Protocol), and the vidscope watch sub-application (registered via add_typer like vidscope mcp). All four quality gates stayed clean throughout — mypy strict on 74 source files, lint-imports 8 contracts kept, ruff clean, 432 unit tests passing.

## Success Criteria Results

All 6 success criteria met — see M003-VALIDATION.md for the audit trail.

- [x] Watchlist persistence layer (14 SQLite tests)
- [x] Channel listing via yt-dlp (7 tests + real probe)
- [x] 4 watchlist use cases (23 application tests)
- [x] CLI sub-application (11 CLI tests)
- [x] End-to-end refresh flow (verify-m003.sh 9/9)
- [x] All 4 quality gates clean

## Definition of Done Results

- [x] R021 + R022 validated via gsd_requirement_update
- [x] verify-m003.sh exits 0 with all 9 steps green
- [x] docs/watchlist.md user-facing documentation
- [x] PROJECT.md updated to reflect M003 completion
- [x] All 4 quality gates clean (ruff/mypy strict/pytest/import-linter)
- [x] Hexagonal architecture preserved (no new contracts needed)

## Requirement Outcomes

## Requirement Status Transitions

- **R021** (Watchlist for public accounts) → `active` → `validated`
  Evidence: `WatchAccountRepositorySQLite` + 4 use cases + `vidscope watch` CLI sub-application + 14 + 23 + 11 tests covering CRUD, error paths, and end-to-end CLI flow.

- **R022** (Scheduled refresh) → `active` → `validated`
  Evidence: `RefreshWatchlistUseCase` with idempotent dedupe + per-account error capture + WatchRefresh persistence. Idempotence validated by verify-m003.sh (second refresh = 0 new). Scheduling delegated to OS schedulers per docs/watchlist.md.

## Deviations

None.

## Follow-ups

None.
