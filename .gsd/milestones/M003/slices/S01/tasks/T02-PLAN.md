---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T02: SQLite schema + repositories for watched_accounts + watch_refreshes

Add Table definitions to src/vidscope/adapters/sqlite/schema.py for watched_accounts (id PK, platform, handle UNIQUE, url, created_at, last_checked_at) and watch_refreshes (id PK, started_at, finished_at, accounts_checked, new_videos_ingested, errors JSON). init_db creates both via metadata.create_all (idempotent). Create src/vidscope/adapters/sqlite/watch_account_repository.py and watch_refresh_repository.py implementing the ports. Update SqliteUnitOfWork to expose watch_accounts + watch_refreshes attributes. Tests cover CRUD round-trips + UNIQUE constraint on handle.

## Inputs

- ``src/vidscope/domain/entities.py` — new entities`
- ``src/vidscope/ports/repositories.py` — new Protocols`

## Expected Output

- `Schema + 2 repositories + tests`

## Verification

python -m uv run pytest tests/unit/adapters/sqlite -q
