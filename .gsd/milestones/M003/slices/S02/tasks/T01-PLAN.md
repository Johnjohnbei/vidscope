---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: 4 watchlist use cases (add, list, remove, refresh)

Create src/vidscope/application/watchlist.py with 4 use cases: AddWatchedAccountUseCase(unit_of_work_factory), ListWatchedAccountsUseCase(unit_of_work_factory), RemoveWatchedAccountUseCase(unit_of_work_factory), RefreshWatchlistUseCase(unit_of_work_factory, pipeline_runner, downloader, clock). Add use case derives handle from URL via a `_handle_from_url(url, platform)` helper (extracts the @handle for YouTube/TikTok/Instagram URLs). Refresh use case iterates accounts, calls downloader.list_channel_videos with limit=10, dedupes against videos.get_by_platform_id, runs new URLs through pipeline_runner.run, catches per-account exceptions, persists a WatchRefresh row at the end with totals + errors. DTOs: AddedAccount + ListedAccounts + RemovedAccount + RefreshSummary. 12+ unit tests.

## Inputs

- ``src/vidscope/ports/repositories.py``
- ``src/vidscope/ports/pipeline.py``
- ``src/vidscope/pipeline/runner.py``

## Expected Output

- ``src/vidscope/application/watchlist.py``
- `Updated `__init__.py``
- ``tests/unit/application/test_watchlist.py``

## Verification

python -m uv run pytest tests/unit/application/test_watchlist.py -q
