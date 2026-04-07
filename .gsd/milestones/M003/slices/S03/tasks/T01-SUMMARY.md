---
id: T01
parent: S03
milestone: M003
key_files:
  - docs/watchlist.md
  - scripts/verify-m003.sh
  - .gsd/PROJECT.md
  - .gsd/REQUIREMENTS.md
key_decisions:
  - verify-m003.sh uses stubbed pipeline + monkeypatched list_channel_videos for determinism — same pattern as verify-m002.sh's seed step
  - Documentation explicitly delegates scheduling to OS cron/launchd/Task Scheduler — VidScope is not a daemon
  - PROJECT.md "Current State" section rewritten as a feature-by-feature listing of what works today, not a chronological narrative
duration: 
verification_result: passed
completed_at: 2026-04-07T18:03:15.576Z
blocker_discovered: false
---

# T01: Shipped docs/watchlist.md, scripts/verify-m003.sh (9 steps, 9/9 green), updated PROJECT.md, marked R021 + R022 as validated. M003 ready for milestone closure.

**Shipped docs/watchlist.md, scripts/verify-m003.sh (9 steps, 9/9 green), updated PROJECT.md, marked R021 + R022 as validated. M003 ready for milestone closure.**

## What Happened

Closing slice for M003.

**docs/watchlist.md** (~7KB) explains the watchlist concepts (account, refresh, idempotence, per-account error capture), the 4 CLI commands with example outputs, OS-level scheduling examples for cron/launchd/Task Scheduler, the cookies story, and the database schema.

**scripts/verify-m003.sh** (9 steps): uv sync, ruff, mypy strict, lint-imports, pytest unit suite, vidscope --help check, vidscope watch --help check, end-to-end watchlist demo (deterministic, no network), watch_refreshes persistence check.

The end-to-end demo monkeypatches `yt_dlp.YoutubeDL`, `faster_whisper.WhisperModel`, the ffmpeg subprocess path, AND `YtdlpDownloader.list_channel_videos`, then runs the full flow: AddWatchedAccountUseCase → RefreshWatchlistUseCase (with the real PipelineRunner driving all 5 stages on each new entry) → ListWatchedAccountsUseCase. The demo asserts:
- 1 account checked, 2 new videos ingested on first refresh, 0 errors
- 0 new videos on second refresh (idempotence)
- last_checked_at is set on the account after refresh
- 2 watch_refreshes rows persisted

Result: 9/9 green, summary footer prints "M003 VERIFICATION PASSED — Watchlist + scheduled refresh ready."

**PROJECT.md** updated:
- "Current focus" line now lists M001/M002/M003 as complete
- "Current State" rewritten to reflect everything that works today (5 capabilities + observability + 432 unit tests + 8 import-linter contracts)
- Validated requirements list extended with R002/R003/R004/R006/R020/R021/R022/R023
- Milestone Sequence checkboxes ticked for M001-M003

**R021 + R022 marked validated** via gsd_requirement_update with explicit proof references (unit tests + CLI tests + verify-m003.sh demo).

Quality gates: still 432 unit + 3 architecture + 2 MCP subprocess tests, all green. mypy strict on 74 source files, lint-imports 8 contracts kept, ruff clean.

## Verification

Ran `bash scripts/verify-m003.sh --skip-integration` → 9/9 steps green, exit 0. Demo output: "first refresh: checked=1 new=2 errors=0", "second refresh: checked=1 new=0", "watch_refreshes count: 2".

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash scripts/verify-m003.sh --skip-integration` | 0 | ✅ 9/9 steps green, M003 VERIFICATION PASSED | 12000ms |

## Deviations

verify-m003.sh uses a stubbed-pipeline demo (deterministic, no real network) instead of a real `vidscope watch add @YouTube` + `refresh` against the live channel. Rationale: CI determinism + the same approach used by verify-m002.sh's seed step. Live network validation is the user's manual smoke check (documented in the script header).

## Known Issues

None.

## Files Created/Modified

- `docs/watchlist.md`
- `scripts/verify-m003.sh`
- `.gsd/PROJECT.md`
- `.gsd/REQUIREMENTS.md`
