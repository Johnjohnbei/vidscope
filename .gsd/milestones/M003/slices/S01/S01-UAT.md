# S01: Watchlist schema + WatchAccountRepository + channel listing — UAT

**Milestone:** M003
**Written:** 2026-04-07T17:49:44.076Z

## S01 UAT — Watchlist persistence foundation

### Manual checks
1. `python -m uv run pytest tests/unit/adapters/sqlite -q` → all sqlite tests pass
2. `python -m uv run pytest tests/unit/adapters/ytdlp -q` → 30 ytdlp tests pass

### Quality gates
- [x] 398 unit + 3 architecture tests
- [x] ruff, mypy strict (72 files), lint-imports (8 contracts) all clean
- [x] watched_accounts + watch_refreshes tables created via init_db
- [x] WatchAccountRepository + WatchRefreshRepository implement their ports
- [x] YtdlpDownloader.list_channel_videos returns ChannelEntry list

