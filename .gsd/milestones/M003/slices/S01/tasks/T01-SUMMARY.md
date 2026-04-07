---
id: T01
parent: S01
milestone: M003
key_files:
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/pipeline.py
  - src/vidscope/ports/unit_of_work.py
  - src/vidscope/ports/__init__.py
  - tests/unit/domain/test_entities.py
  - tests/unit/ports/test_protocols.py
key_decisions:
  - WatchedAccount.handle is unique per platform (compound UNIQUE constraint) — different platforms can have the same handle, same platform cannot
  - list_channel_videos returns ChannelEntry dataclasses (platform_id + url) not full IngestOutcome — listing is cheap, we want to dedupe before committing to a download
  - WatchRefresh.errors is a tuple of strings (one per account failure) not typed exceptions — we only need to display them to the user, not programmatically classify them
  - list_channel_videos added to the existing Downloader Protocol instead of a new ChannelLister Protocol — yt-dlp is the single source of truth for both downloading and listing, no benefit in separating the interface
duration: 
verification_result: passed
completed_at: 2026-04-07T17:42:21.619Z
blocker_discovered: false
---

# T01: Added WatchedAccount + WatchRefresh domain entities, WatchAccountRepository + WatchRefreshRepository + ChannelEntry ports, Downloader.list_channel_videos method + UnitOfWork.watch_accounts + watch_refreshes attributes. 113 domain + port tests green.

**Added WatchedAccount + WatchRefresh domain entities, WatchAccountRepository + WatchRefreshRepository + ChannelEntry ports, Downloader.list_channel_videos method + UnitOfWork.watch_accounts + watch_refreshes attributes. 113 domain + port tests green.**

## What Happened

T01 establishes the contracts M003 needs. Zero new business logic — just entities and ports.

**Domain entities:**
- `WatchedAccount(platform, handle, url, id, created_at, last_checked_at)` — a registered watched account. Handle is unique per platform (enforced at the DB level in T02).
- `WatchRefresh(started_at, accounts_checked, new_videos_ingested, errors, id, finished_at)` — one row per `vidscope watch refresh` invocation. Errors is a tuple of strings (one per account failure).

**Ports:**
- `WatchAccountRepository` Protocol with `add`, `get`, `get_by_handle`, `list_all`, `remove`, `update_last_checked` methods
- `WatchRefreshRepository` Protocol with `add` and `list_recent`
- `Downloader.list_channel_videos(url, limit) -> list[ChannelEntry]` — new method on the existing Downloader port. Returns ChannelEntry dataclasses with just `platform_id` + `url` so the refresh loop can dedupe cheaply against the videos table before committing to a download.
- `ChannelEntry` dataclass exported from `vidscope.ports`
- `UnitOfWork.watch_accounts` + `UnitOfWork.watch_refreshes` annotations added so adapters know to wire them

**Tests updated:**
- `test_protocols.py` adds WatchAccountRepository + WatchRefreshRepository to RUNTIME_CHECKABLE_PROTOCOLS, tests for the required methods, updated UnitOfWork annotation check to expect 8 repository fields (up from 6)
- `test_entities.py` adds TestWatchedAccount + TestWatchRefresh classes covering frozen-ness, default values, duration math for completed refreshes

113 domain + port tests pass in 130ms. The full suite has 2 expected failures in T02's territory: `test_conforms_to_unit_of_work_protocol` and `test_unit_of_work_is_usable` because `SqliteUnitOfWork` doesn't yet expose the new attributes. T02 will fix those by implementing the SQLite adapters.

## Verification

Ran `python -m uv run pytest tests/unit/ports tests/unit/domain -q` → 113 passed. Manually verified imports: `from vidscope.domain import WatchedAccount, WatchRefresh` and `from vidscope.ports import WatchAccountRepository, ChannelEntry, Downloader` all work.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/ports tests/unit/domain -q` | 0 | ✅ 113/113 domain + port tests green | 130ms |

## Deviations

None.

## Known Issues

2 test failures in adapters/sqlite and infrastructure/container test_unit_of_work that are expected — they check `isinstance(uow, UnitOfWork)` which now requires the new watch_accounts + watch_refreshes attributes. T02 implements those and the failures go away.

## Files Created/Modified

- `src/vidscope/domain/entities.py`
- `src/vidscope/domain/__init__.py`
- `src/vidscope/ports/repositories.py`
- `src/vidscope/ports/pipeline.py`
- `src/vidscope/ports/unit_of_work.py`
- `src/vidscope/ports/__init__.py`
- `tests/unit/domain/test_entities.py`
- `tests/unit/ports/test_protocols.py`
