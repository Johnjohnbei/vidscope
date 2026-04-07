# M003: Account monitoring and scheduled refresh

## Vision
Turn vidscope from a tool you invoke manually into a library that keeps itself fresh. Ship a watchlist feature: declare a public Instagram, TikTok, or YouTube account as "watched", then `vidscope watch refresh` detects new videos from every watched account and runs them through the existing M001 pipeline. Each watched account tracks its last-checked state so repeated refreshes only ingest genuinely new content. Schedule via cron / Task Scheduler by running the same command on a timer — no daemon, no background service, no new persistent process.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Watchlist schema + WatchAccountRepository + channel listing | high | — | ✅ | New SQLite tables + CRUD repository + a channel-listing method that calls yt-dlp's extract_flat and returns a list of (platform_id, url) tuples for a given channel URL. Verified by a live integration test against a YouTube channel. |
| S02 | WatchRefreshUseCase + vidscope watch CLI sub-application | medium | S01 | ✅ | `vidscope watch add https://www.youtube.com/@channel` registers the account. `vidscope watch list` shows the table. `vidscope watch refresh` iterates accounts, lists recent videos per account, deduplicates against existing videos, runs new ones through the pipeline. Idempotent (second run = 0 new). |
| S03 | Docs, verify-m003.sh, milestone closure | low | S01, S02 | ✅ | docs/watchlist.md explains usage + cron/Task Scheduler examples. verify-m003.sh runs quality gates + unit tests + live channel listing + idempotent refresh demo. |
