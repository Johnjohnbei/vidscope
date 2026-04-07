---
id: T01
parent: S03
milestone: M005
key_files:
  - docs/cookies.md
  - scripts/verify-m005.sh
  - src/vidscope/cli/commands/cookies.py
  - .gsd/PROJECT.md
  - .gsd/KNOWLEDGE.md
  - .gsd/REQUIREMENTS.md
key_decisions:
  - docs/cookies.md leads with the 5-minute setup using the new subcommands; advanced env var usage is in a separate section
  - verify-m005.sh exercises probe via stubbed yt_dlp — zero real network
  - verify-m005.sh's CookieAuthError detection step uses the _translate_* helpers directly to test both download + extractor paths
  - Plain ASCII 'OK' in CLI output instead of unicode '✓' — Windows cp1252 / Rich / subprocess pipes don't mix
  - KNOWLEDGE.md captures 5 new reusable patterns from M005: app-no-infrastructure, CLI sub-app shape, Annotated style, no unicode in stdout, probe pattern
duration: 
verification_result: passed
completed_at: 2026-04-07T19:07:53.889Z
blocker_discovered: false
---

# T01: Closed M005: rewrote docs/cookies.md as a 5-minute walkthrough using the new subcommands, shipped verify-m005.sh (10/10 green), validated R025, updated PROJECT.md + KNOWLEDGE.md.

**Closed M005: rewrote docs/cookies.md as a 5-minute walkthrough using the new subcommands, shipped verify-m005.sh (10/10 green), validated R025, updated PROJECT.md + KNOWLEDGE.md.**

## What Happened

**`docs/cookies.md` rewritten** (~10KB). New structure: 5-minute setup at the top (export → set → test → ingest), per-browser export instructions (Firefox + Chrome/Edge/Brave), then `vidscope cookies status/clear` documentation, then the advanced `VIDSCOPE_COOKIES_FILE` env var section, then a comprehensive Troubleshooting section that walks through every failure mode users will hit. The troubleshooting section explicitly references `vidscope cookies test --url <url>` as the diagnostic to run for every cookie-related failure. Architecture notes at the bottom for curious users / contributors describing the validator + probe + CookieAuthError + auth marker detection design.

**`scripts/verify-m005.sh`** ships with 10 steps:
1. `uv sync`
2. `ruff check`
3. `mypy strict`
4. `lint-imports` (9 contracts)
5. `pytest -q` (full suite)
6. `vidscope --help` lists `cookies` sub-application
7. `vidscope cookies --help` lists set/status/test/clear
8. End-to-end set/status/clear cycle: writes a fake Netscape cookies file, calls `vidscope cookies set`, verifies `status` reports `2 entries`, calls `vidscope cookies clear --yes`, verifies `status` reports `feature disabled` again
9. Probe demo via stubbed `yt_dlp.YoutubeDL`: tests both `OK` (public URL) and `AUTH_REQUIRED` (private URL with `login required` error), confirms the use case interpretation includes `Stub Reel` and `expired`
10. CookieAuthError detection: imports the ytdlp `_translate_*` helpers directly and confirms they raise `CookieAuthError` (with `vidscope cookies test` mention) for auth-marker errors AND raise plain `IngestError` (NOT CookieAuthError) for non-auth errors

The script supports `--skip-integration` for the MCP subprocess tests. Verified locally: `bash scripts/verify-m005.sh --skip-integration` → 10/10 green, exit 0.

**Pre-existing Windows encoding bug surfaced and fixed**: the `vidscope cookies set` and `vidscope cookies clear` commands originally used `[green]✓[/green]` in their success output. When the verify script captures stdout via subprocess, Windows defaults to cp1252 encoding for non-TTY pipes, and Rich crashes with `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'`. Fixed by replacing `✓` with plain ASCII `OK`. The fix is documented in KNOWLEDGE.md as a project-wide rule: never use unicode glyphs in CLI output that goes to stdout — save them for verify-mNNN.sh scripts that print directly to the terminal.

**R025 marked validated** via `gsd_requirement_update`. Validation note records the full evidence chain across M001/S07 (plumbing), M005/S01 (validator + use cases + sub-application), M005/S02 (probe + CookieAuthError + auth marker detection), M005/S03 (docs + verify script). 60 new cookies-related unit tests across 4 test files. The cookies feature is now usable end-to-end without the user touching env vars or knowing paths.

**`.gsd/PROJECT.md` updated** to reflect "all 5 planned milestones complete":
- Top section now says M001+M002+M003+M004+M005 done
- Test count 558 → 618
- Source file count 81 → 84
- Contract count unchanged at 9 (but mention that S01 tightened application-has-no-adapters)
- Added the new `vidscope cookies set/status/test/clear` bullet
- R025 added to the validated list with the specific note "cookies UX complete with set/status/test/clear + CookieAuthError"
- Cookies feature description rewritten to mention the new commands
- Milestone sequence: all 5 checked
- "Next" section updated: "All 5 planned milestones are complete. Future work would be additive: semantic search (R026), expanded auth scenarios (Instagram stories, TikTok drafts), or a polish pass on the rich CLI output."

**`.gsd/KNOWLEDGE.md` updated** with 5 new sections:
1. **Application layer cannot import infrastructure (M005)** — documents the tightened import-linter rule + rationale + how to share helpers between use cases
2. **CLI sub-application pattern (M002, M003, M005)** — 8-step recipe for adding a new Typer sub-application
3. **Use Annotated[T, typer.Argument(...)] for non-str CLI defaults (M005)** — explains the B008 rule and the fix
4. **Don't use unicode glyphs in CLI output that goes to stdout (M005)** — Windows cp1252 + Rich + subprocess pipes = crash; rule is plain ASCII tags
5. **Probe pattern for diagnostic operations (M005)** — 6-step recipe for the diagnostic-operation pattern, applicable to any future "dry run" feature

**Quality gates after S03**:
- ✅ pytest: **618 passed**, 5 deselected, in 15.01s (no new tests in S03 — closure slice)
- ✅ mypy strict: **84 source files** OK
- ✅ ruff: clean
- ✅ lint-imports: **9 contracts kept**, 0 broken
- ✅ verify-m005.sh: **10/10 steps green**, exits 0

## Verification

All 4 quality gates clean in parallel + verify-m005.sh full run: 10 steps, 0 failures, exits 0. pytest 618 passed in 15.01s, mypy 84 source files OK, ruff clean, lint-imports 9 contracts kept.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest -q` | 0 | ✅ 618 passed | 15010ms |
| 2 | `python -m uv run mypy src` | 0 | ✅ 84 source files OK | 2100ms |
| 3 | `python -m uv run lint-imports` | 0 | ✅ 9 contracts kept | 2100ms |
| 4 | `python -m uv run ruff check .` | 0 | ✅ all checks passed | 800ms |
| 5 | `bash scripts/verify-m005.sh --skip-integration` | 0 | ✅ 10/10 steps green | 35000ms |

## Deviations

Pre-existing Windows cp1252 / Rich unicode bug surfaced and fixed. The fix replaces 2 unicode checkmarks with plain ASCII tags in `vidscope cookies set` and `vidscope cookies clear` output. New project-wide rule documented in KNOWLEDGE.md.

## Known Issues

None.

## Files Created/Modified

- `docs/cookies.md`
- `scripts/verify-m005.sh`
- `src/vidscope/cli/commands/cookies.py`
- `.gsd/PROJECT.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/REQUIREMENTS.md`
