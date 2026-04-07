---
estimated_steps: 1
estimated_files: 8
skills_used: []
---

# T01: Domain entities + ports for watched accounts and refreshes

Add src/vidscope/domain/entities.py: WatchedAccount dataclass (id, platform, handle, url, created_at, last_checked_at) and WatchRefresh dataclass (id, started_at, finished_at, accounts_checked, new_videos_ingested, errors as tuple of strings). Add WatchAccountRepository + WatchRefreshRepository Protocols in src/vidscope/ports/repositories.py. Add `list_channel_videos` method to the Downloader Protocol in src/vidscope/ports/pipeline.py with signature `list_channel_videos(url: str, limit: int = 10) -> list[ChannelEntry]` returning a list of ChannelEntry dataclasses (platform_id, url). Update UnitOfWork Protocol to include watch_accounts + watch_refreshes attributes. Update tests/unit/ports to assert the new Protocols exist.

## Inputs

- ``src/vidscope/domain/entities.py``
- ``src/vidscope/ports/repositories.py``
- ``src/vidscope/ports/pipeline.py``

## Expected Output

- `Entities + Protocols + updated tests`

## Verification

python -m uv run pytest tests/unit/domain tests/unit/ports -q
