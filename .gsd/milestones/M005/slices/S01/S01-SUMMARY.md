---
id: S01
parent: M005
milestone: M005
provides:
  - validate_cookies_file helper (pure-Python, application layer)
  - 3 cookies use cases ready for S02 to extend
  - vidscope cookies sub-application ready for S02 to add 'test' subcommand
  - Architectural enforcement: application is now strictly forbidden from importing infrastructure
requires:
  []
affects:
  - S02: TestCookiesUseCase will reuse the validator + the existing Path-arg constructor pattern
  - All future application use cases: tightened import-linter rule means they cannot accidentally depend on infrastructure
key_files:
  - src/vidscope/application/cookies_validator.py
  - src/vidscope/application/cookies.py
  - src/vidscope/cli/commands/cookies.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - tests/unit/application/test_cookies_validator.py
  - tests/unit/application/test_cookies.py
  - tests/unit/cli/test_cookies.py
  - tests/unit/cli/test_app.py
  - .importlinter
key_decisions:
  - Permissive Netscape format validator: header optional, comments skipped, 7 tab-columns required, non-empty domain only
  - Use cases take simple Path args, not Config — application stays decoupled from infrastructure
  - Tightened application-has-no-adapters to forbid vidscope.infrastructure imports — closes a pre-existing architectural gap
  - cookies_validator moved from infrastructure to application — it's pure-Python and naturally consumed by the application layer
  - All cookies subcommands operate on <data_dir>/cookies.txt only; env-override files are owned by the user
  - set warns when env override is in effect — user knows immediately why installation won't take effect
  - clear prompts by default; --yes / -y skips — destructive operations never silent without explicit consent
  - Annotated[T, typer.Argument(...)] style for Path defaults to avoid ruff B008
patterns_established:
  - Application use cases take simple primitives (Path, str, int) as constructor args, never Config or other infrastructure types
  - Sub-application Typer pattern established by mcp + watch is now used by cookies too
  - Validator helpers that return frozen result dataclasses (ok/reason/...) instead of raising — caller can format the error however it likes
observability_surfaces:
  - vidscope cookies status — rich table showing default path / size / mtime / format valid / env override / active path
  - set warns on env override — yellow text
  - clear confirmation prompt by default
drill_down_paths:
  - .gsd/milestones/M005/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T18:51:51.972Z
blocker_discovered: false
---

# S01: Cookies file validation + status + clear (read-only + simple writes)

**Shipped the read-only and simple-write half of the M005 cookies UX: validate_cookies_file helper + 3 use cases + vidscope cookies set/status/clear sub-application. Tightened application-has-no-adapters contract to forbid infrastructure imports.**

## What Happened

S01 was the foundation slice for M005. Three tasks delivered the validator + use cases + CLI sub-application without touching yt_dlp at all — that part lives in S02.

**T01** built `validate_cookies_file()` + `CookiesValidation` dataclass in `src/vidscope/application/cookies_validator.py` (originally placed in infrastructure, moved to application in T02 for architectural cleanliness). 15 unit tests covering valid files, no-header exports, mixed comments, CRLF, missing files, empty files, malformed rows, wrong column counts. Permissive parser: header line is optional, comments and blank lines skipped, data rows must have exactly 7 tab-separated columns with non-empty domain.

**T02** built three use cases in `src/vidscope/application/cookies.py`: `SetCookiesUseCase`, `GetCookiesStatusUseCase`, `ClearCookiesUseCase`. Each takes simple Path arguments (`data_dir` and optionally `configured_cookies_file`) instead of the full Config — keeps the application layer decoupled from infrastructure.

**Architectural improvement surfaced and fixed in T02**: the original use case design imported `Config` from `vidscope.infrastructure.config`. The `application-has-no-adapters` import-linter contract had a gap: it forbade `vidscope.adapters.*` and `vidscope.cli` but did NOT forbid `vidscope.infrastructure`. Tightened the contract to forbid `vidscope.infrastructure` and refactored the use cases to take Path arguments. Also moved `cookies_validator.py` from infrastructure to application since it's pure-Python (only stdlib). Every other application file was already clean by convention — this slice surfaced and structurally enforced the rule.

**T03** built the Typer sub-application in `src/vidscope/cli/commands/cookies.py` with 3 commands (set, status, clear) wired to the use cases via `acquire_container()`. Registered via `add_typer(cookies_app, name="cookies")` in `app.py` alongside `mcp_app` and `watch_app`. 12 CLI tests via `CliRunner`. Used `Annotated[T, typer.Argument(...)]` style to avoid ruff B008 on `Path` defaults — modern typer-recommended pattern.

**Status command surfaces the env override**: when `VIDSCOPE_COOKIES_FILE` points elsewhere, the status command shows it and the active path explicitly so the user knows their `vidscope cookies set` won't take effect. The set command also warns when this is the case. The clear command never touches an env-override file because that file is owned by the user.

**Test progression**: 558 (M004) → 598 (S01: +40 = 15 validator + 13 use-case + 12 CLI tests).

**No deviations, no replans, no blockers.** S02 is next: `vidscope cookies test` (probe via stubbed yt_dlp) + `CookieAuthError` typed domain error + better error remediation in `vidscope add`.

## Verification

All 4 quality gates clean: pytest 598 passed in 14.93s, mypy 84 source files OK, ruff clean (after Annotated refactor + 1 noqa), lint-imports 9 contracts kept (with the new tightened application-has-no-adapters rule).

## Requirements Advanced

- R025 — Cookies UX foundation built: validation, set/status/clear use cases, vidscope cookies sub-application registered. S02 will add the probe + typed CookieAuthError. R025 will be marked validated when M005 closes.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Tightened application-has-no-adapters import-linter contract to forbid infrastructure imports + moved cookies_validator from infrastructure to application. Both are positive architectural improvements surfaced by the cookies use cases.

## Known Limitations

- vidscope cookies test (probe) ships in S02
- vidscope add error messages don't yet point at vidscope cookies test — also S02
- No CookieAuthError typed domain error yet — also S02

## Follow-ups

- S02: TestCookiesUseCase + Downloader.probe_url port method + ytdlp adapter implementation + CookieAuthError + error remediation
- S03: docs/cookies.md rewrite + verify-m005.sh + R025 validation + closure

## Files Created/Modified

- `src/vidscope/application/cookies_validator.py` — New permissive Netscape format validator
- `src/vidscope/application/cookies.py` — New 3 use cases: SetCookiesUseCase, GetCookiesStatusUseCase, ClearCookiesUseCase
- `src/vidscope/cli/commands/cookies.py` — New Typer sub-application with set/status/clear subcommands
- `src/vidscope/cli/commands/__init__.py` — Export cookies_app
- `src/vidscope/cli/app.py` — Register cookies_app via add_typer
- `.importlinter` — Tightened application-has-no-adapters to forbid vidscope.infrastructure imports
- `tests/unit/application/test_cookies_validator.py` — 15 unit tests for the validator
- `tests/unit/application/test_cookies.py` — 13 unit tests for the use cases
- `tests/unit/cli/test_cookies.py` — 12 CLI unit tests via CliRunner
- `tests/unit/cli/test_app.py` — Updated test_help_lists_every_command to assert cookies + watch are listed
