---
id: S02
parent: M003
milestone: M003
provides:
  - AddWatchedAccountUseCase, ListWatchedAccountsUseCase, RemoveWatchedAccountUseCase, RefreshWatchlistUseCase
  - vidscope watch add/list/remove/refresh CLI subcommands
  - Idempotent refresh path validated end-to-end via CLI tests
requires:
  - slice: S01
    provides: WatchedAccount, WatchRefresh, WatchAccountRepository, WatchRefreshRepository, ChannelEntry, list_channel_videos
affects:
  - S03 — ships docs/watchlist.md + verify-m003.sh + closes the milestone
key_files:
  - src/vidscope/application/watchlist.py
  - src/vidscope/application/__init__.py
  - src/vidscope/cli/commands/watch.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - tests/unit/application/test_watchlist.py
  - tests/unit/cli/test_app.py
key_decisions:
  - 4 small use cases instead of 1 facade — each one matches a CLI subcommand and is independently testable
  - Snapshot existing video IDs once at refresh start — O(1) dedupe inside the loop
  - Per-account error capture — a broken account never blocks the rest of the watchlist
  - Refresh reuses PipelineRunner unchanged — every newly discovered video flows through the same 5-stage pipeline as a manual `vidscope add`
  - Sub-application pattern via add_typer — same shape as the mcp sub-application
patterns_established:
  - Sub-application via add_typer for command groups (mcp, watch, future packs)
  - Snapshot-then-iterate for batch operations that need O(1) dedupe
  - Per-account error capture pattern: catch + record + continue, persist a summary row at the end
observability_surfaces:
  - vidscope watch list — inspection surface for the watchlist
  - vidscope watch refresh prints a per-account table with new-videos counts and errors
  - watch_refreshes table is the historical record of past refresh runs
drill_down_paths:
  - .gsd/milestones/M003/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S02/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T17:59:10.245Z
blocker_discovered: false
---

# S02: WatchRefreshUseCase + vidscope watch CLI sub-application

**Wired the full watchlist flow end-to-end via the CLI: 4 use cases + 4 subcommands, idempotent refresh validated through stubbed pipeline. R021 + R022 functionally validated, 432 unit tests green.**

## What Happened

Two tasks: 4 watchlist use cases (T01) + Typer sub-application wiring them to the CLI (T02). The CLI surface is now complete for M003 — users can register accounts, list them, remove them, and trigger a refresh that ingests new videos through the existing M001 pipeline.

**T01 — 4 use cases.** AddWatchedAccountUseCase derives @handle from URL, persists. ListWatchedAccountsUseCase returns ordered tuple. RemoveWatchedAccountUseCase handles ambiguous-handle case (same handle on multiple platforms requires --platform). RefreshWatchlistUseCase is the heart of M003: snapshots existing video IDs once at the start, iterates accounts, dedupes via the in-memory set, runs new URLs through PipelineRunner, captures per-account errors without stopping iteration, persists a WatchRefresh row at the end. 23 unit tests including idempotence (running twice → 0 new on second).

**T02 — vidscope watch CLI.** Typer sub-application registered via add_typer. Each command instantiates the matching use case from the container. List + refresh render rich Tables. Refresh prints a summary + per-account breakdown + warnings section. 11 new CLI tests including an end-to-end refresh that patches `list_channel_videos` directly and validates idempotence through the full Typer → use case → runner → 5-stage pipeline path.

**Final state:** 432 unit tests green (398 → 421 → 432), all 4 quality gates clean, 8 import-linter contracts kept. R021 + R022 are functionally validated by the unit + CLI tests; live integration validation lands in S03's verify-m003.sh.

## Verification

Full suite: 432 passed, 5 deselected. mypy strict on 74 source files clean. ruff clean. lint-imports 8 contracts kept. CLI smoke: `vidscope watch --help` shows the 4 subcommands.

## Requirements Advanced

- R021 — Watchlist CRUD + refresh pipeline functionally validated via 23 unit tests + 11 CLI tests
- R022 — Refresh use case + vidscope watch refresh subcommand operational

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

No live integration test for the full refresh path with real yt-dlp listing — that lands in S03 via verify-m003.sh.

## Follow-ups

S03: docs/watchlist.md + verify-m003.sh + R021 + R022 promotion to validated.

## Files Created/Modified

- `src/vidscope/application/watchlist.py` — 4 use cases + DTOs + helper
- `src/vidscope/cli/commands/watch.py` — Typer sub-application with 4 commands
- `src/vidscope/cli/app.py` — Registers watch_app
- `tests/unit/application/test_watchlist.py` — 23 unit tests
- `tests/unit/cli/test_app.py` — 11 new CLI tests for watch
