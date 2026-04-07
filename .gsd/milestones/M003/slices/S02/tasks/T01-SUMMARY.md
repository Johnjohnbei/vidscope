---
id: T01
parent: S02
milestone: M003
key_files:
  - src/vidscope/application/watchlist.py
  - src/vidscope/application/__init__.py
  - tests/unit/application/test_watchlist.py
key_decisions:
  - 4 small use cases instead of 1 facade — each one matches a CLI subcommand and is independently testable
  - Snapshot existing video IDs once at refresh start — O(1) dedupe inside the loop, avoids repeated DB reads
  - Per-account error capture — a broken account never blocks the rest of the watchlist
  - RefreshWatchlistUseCase reuses PipelineRunner unchanged — every newly discovered video flows through the same 5-stage pipeline as a manual `vidscope add`
  - Removal with ambiguous handle requires explicit — platform — returns a failure with the matching platforms listed
duration: 
verification_result: passed
completed_at: 2026-04-07T17:55:47.630Z
blocker_discovered: false
---

# T01: Shipped 4 watchlist use cases (Add/List/Remove/Refresh). RefreshWatchlistUseCase iterates accounts, dedupes against existing videos, runs new URLs through PipelineRunner, captures per-account errors. 23 unit tests, 421 total green.

**Shipped 4 watchlist use cases (Add/List/Remove/Refresh). RefreshWatchlistUseCase iterates accounts, dedupes against existing videos, runs new URLs through PipelineRunner, captures per-account errors. 23 unit tests, 421 total green.**

## What Happened

Created `src/vidscope/application/watchlist.py` with 4 use cases and their DTOs:

**AddWatchedAccountUseCase** — parses URL via `detect_platform`, derives `@handle` via `_handle_from_url`, persists via WatchAccountRepository. Returns AddedAccountResult(success, account, message). Handles empty URLs, invalid URLs, and duplicate-account cases gracefully (returns failure result, never raises).

**ListWatchedAccountsUseCase** — returns ListedAccountsResult(accounts, total) ordered by creation time.

**RemoveWatchedAccountUseCase** — handles three cases: explicit (handle, platform) → direct lookup; handle alone with single match → unambiguous removal; handle alone with multiple matches → returns "specify --platform" failure. The compound UNIQUE on (platform, handle) means a handle can exist on YouTube AND TikTok, so the platform argument is needed for ambiguous removals.

**RefreshWatchlistUseCase** — the heart of M003. Snapshots the watchlist + existing video IDs in one transaction, then iterates accounts:
1. Calls `downloader.list_channel_videos(account.url, limit=10)` for each account
2. Catches IngestError + unexpected exceptions per account, records the error, continues
3. For each new entry not in existing_ids, builds a PipelineContext and calls `pipeline_runner.run(ctx)`
4. Updates last_checked_at for the account in a short transaction after each iteration
5. Persists a WatchRefresh row at the end with totals + errors tuple

Returns RefreshSummary(started_at, finished_at, accounts_checked, new_videos_ingested, errors, per_account).

**Key design decision: snapshot existing video IDs once.** The refresh loop reads `videos.list_recent(limit=10000)` once at the start and maintains a Python set throughout the iteration. This avoids re-querying the DB inside the loop and lets the dedupe logic skip already-ingested videos in O(1).

**`_handle_from_url` helper** — derives the canonical handle from a URL: `@handle` for YouTube/TikTok/Instagram, fallback to `channel/X` segment for legacy YouTube channel URLs. Pure-string parsing via `urlparse`, no third-party deps.

**23 unit tests:**
- TestHandleFromUrl (4): YouTube/TikTok/Instagram @handle + legacy /channel/X
- TestAddWatchedAccountUseCase (5): happy path + persistence + empty + invalid + duplicate
- TestListWatchedAccountsUseCase (2): empty + populated
- TestRemoveWatchedAccountUseCase (4): by handle + with platform + missing + ambiguous
- TestRefreshWatchlistUseCase (8): empty watchlist + ingest new + skip existing + per-account errors + pipeline failure + last_checked update + WatchRefresh persistence + idempotence (running twice → 0 new on second)

Stub `_FakeDownloader` records calls + can raise per URL. Stub `_FakeRunner` records calls + can return preset RunResults. The idempotence test uses a `_CreatingRunner` that actually inserts a video row so the second refresh's dedupe set sees it.

**Quality gate status after T01:** 421 unit tests pass (398 + 23 new), mypy strict clean on 73 source files, lint-imports 8 contracts kept, ruff clean after 3 auto-fixes.

## Verification

Ran `python -m uv run pytest tests/unit/application/test_watchlist.py -q` → 23 passed in 0.34s. Full suite → 421 passed, 5 deselected. mypy + lint-imports + ruff all clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/application/test_watchlist.py -q` | 0 | ✅ 23/23 watchlist use case tests green | 340ms |
| 2 | `python -m uv run pytest -q && mypy + ruff + lint-imports` | 0 | ✅ 421/421 unit tests, all 4 quality gates clean | 5500ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/application/watchlist.py`
- `src/vidscope/application/__init__.py`
- `tests/unit/application/test_watchlist.py`
