---
id: T02
parent: S02
milestone: M003
key_files:
  - src/vidscope/cli/commands/watch.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - tests/unit/cli/test_app.py
key_decisions:
  - Sub-application via add_typer pattern — same shape as the existing mcp sub-application, keeps the root command list short
  - Direct monkeypatch of YtdlpDownloader.list_channel_videos in the E2E test — stub_pipeline only stubs the download path, listing needs its own override
  - Refresh prints a per-account table + a warnings section — the watchlist refresh is the main observability surface, keep it human-friendly
  - Unknown --platform values rejected with a clear error before any DB call
duration: 
verification_result: passed
completed_at: 2026-04-07T17:58:29.340Z
blocker_discovered: false
---

# T02: Shipped vidscope watch sub-application with add/list/remove/refresh commands. End-to-end CLI test seeds an account, refreshes via stubbed yt-dlp + pipeline, validates idempotence. 432 total tests, all 4 gates clean.

**Shipped vidscope watch sub-application with add/list/remove/refresh commands. End-to-end CLI test seeds an account, refreshes via stubbed yt-dlp + pipeline, validates idempotence. 432 total tests, all 4 gates clean.**

## What Happened

Created `src/vidscope/cli/commands/watch.py` — a Typer sub-application registered on the root app via `add_typer(watch_app, name="watch")`.

**4 commands:**
- `vidscope watch add <url>` — calls AddWatchedAccountUseCase, prints `added platform/handle` on success or fails with EXIT_USER_ERROR if URL is invalid/duplicate
- `vidscope watch list` — calls ListWatchedAccountsUseCase, renders a rich Table with id/platform/handle/url/last_checked
- `vidscope watch remove <handle> [--platform]` — parses `--platform` string into a Platform enum (rejects unknown values cleanly), calls RemoveWatchedAccountUseCase
- `vidscope watch refresh [-n LIMIT]` — wires the full RefreshWatchlistUseCase from the container (uow_factory + pipeline_runner + downloader + clock), prints a summary table with per-account results + a warnings section if any errors occurred

Each command follows the established CLI pattern: `with handle_domain_errors(): container = acquire_container(); use_case = ...; result = use_case.execute(...); format and print`. No business logic in the CLI layer.

**11 new CLI tests** in `TestWatch`:
- Help lists 4 subcommands
- list empty
- add persists + list shows it
- add duplicate returns EXIT_USER_ERROR
- add invalid URL fails
- remove by handle (single match)
- remove with explicit --platform
- remove unknown platform fails cleanly
- remove missing fails with "no watched account"
- refresh with no accounts (uses stub_pipeline so no network)
- refresh with one account (end-to-end with stubbed yt-dlp + idempotence: second run = 0 new)

**Key trick in the end-to-end refresh test:** The existing `stub_pipeline` fixture stubs `YoutubeDL.extract_info` (the download path) but `list_channel_videos` uses a different code path. The test patches `YtdlpDownloader.list_channel_videos` directly via `monkeypatch.setattr` to return a single ChannelEntry, then runs the full CLI → use case → pipeline_runner → all 5 stages. This validates that the entire wiring works without any network access.

**Quality gate status after T02:**
- 432 unit tests pass (421 + 11 new)
- 1 ruff auto-fix for import organization
- mypy strict clean on 74 source files
- lint-imports 8 contracts kept
- `vidscope watch --help` from the shell confirms the subcommand is registered

S02 is complete: persistence + use cases + CLI sub-application all wired and tested. Ready for S03 (docs + verify-m003.sh + closure).

## Verification

Ran `python -m uv run pytest tests/unit/cli/test_app.py -q` → 25 passed (14 + 11 new). Full suite → 432 passed, 5 deselected. All 4 quality gates clean. Manual `vidscope watch --help` from PowerShell shows the 4 subcommands.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/cli/test_app.py -q` | 0 | ✅ 25/25 CLI tests green (11 new for watch) | 1280ms |
| 2 | `python -m uv run pytest -q && mypy + ruff + lint-imports` | 0 | ✅ 432/432 unit tests, all 4 quality gates clean | 5500ms |
| 3 | `python -m uv run vidscope watch --help` | 0 | ✅ Help shows add/list/remove/refresh | 800ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/cli/commands/watch.py`
- `src/vidscope/cli/commands/__init__.py`
- `src/vidscope/cli/app.py`
- `tests/unit/cli/test_app.py`
