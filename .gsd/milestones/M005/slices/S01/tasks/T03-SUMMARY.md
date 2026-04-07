---
id: T03
parent: S01
milestone: M005
key_files:
  - src/vidscope/cli/commands/cookies.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - tests/unit/cli/test_cookies.py
  - tests/unit/cli/test_app.py
  - src/vidscope/application/cookies_validator.py
key_decisions:
  - Cookies sub-application registered via add_typer alongside watch + mcp — same architectural shape as M002 and M003
  - Annotated[T, typer.Argument(...)] style for Path defaults — avoids B008 ruff warning + is the typer-recommended modern pattern
  - set warns the user when env override is in effect — unambiguous about why their installation won't take effect
  - clear prompts by default; --yes / -y skips — destructive operations never silent without explicit consent
  - validate_cookies_file's 7 return statements get noqa:PLR0911 because each represents a distinct validation state — collapsing would reduce readability
duration: 
verification_result: passed
completed_at: 2026-04-07T18:50:52.247Z
blocker_discovered: false
---

# T03: Shipped vidscope cookies sub-application (set/status/clear) wired to the M005 use cases. Registered alongside watch + mcp via add_typer. 12 CLI tests, all 4 quality gates clean (598 unit tests, 84 source files, 9 contracts).

**Shipped vidscope cookies sub-application (set/status/clear) wired to the M005 use cases. Registered alongside watch + mcp via add_typer. 12 CLI tests, all 4 quality gates clean (598 unit tests, 84 source files, 9 contracts).**

## What Happened

**Created `src/vidscope/cli/commands/cookies.py`** with a Typer sub-application exposing 3 commands:

`vidscope cookies set <source-path>`:
- Validates the source as Netscape format before copying (so a broken new file never overwrites a working existing file)
- Copies to `<data_dir>/cookies.txt` via the `SetCookiesUseCase`
- Prints `✓ copied N cookie rows to <path>` on success
- Surfaces a `[yellow]warning[/yellow]` when `VIDSCOPE_COOKIES_FILE` is set to a different path so the user knows their installation won't take effect

`vidscope cookies status`:
- Prints a Rich table with: default path, default exists, size, last modified, format valid (with row count), env override, active path
- Shows the env override row only when `VIDSCOPE_COOKIES_FILE` points elsewhere
- Shows "cookies feature disabled" when no cookies are configured at all

`vidscope cookies clear [--yes]`:
- Removes only the canonical `<data_dir>/cookies.txt` (never touches an env-override file owned by the user)
- Prompts for confirmation by default; `--yes` / `-y` skips
- Returns user-error exit code when no file exists at the canonical location

**Registered the sub-application** in `src/vidscope/cli/app.py` via `app.add_typer(cookies_app, name="cookies")`, same pattern as `mcp_app` and `watch_app`. Updated `src/vidscope/cli/commands/__init__.py` to export `cookies_app`. Updated `tests/unit/cli/test_app.py::test_help_lists_every_command` to assert `cookies` and `watch` are listed (they were previously missing).

**Annotated parameter style.** Used `Annotated[Path, typer.Argument(...)]` and `Annotated[bool, typer.Option(...)] = False` instead of the older `source: Path = typer.Argument(...)` style, because ruff's `B008` (function call in default) flags the older style for `Path` types. The `Annotated` style is the typer-recommended modern pattern and avoids the linter warning. All other CLI files use the older style with `str` defaults, which doesn't trip B008 — but `Path` defaults do.

**12 new CLI unit tests** in `tests/unit/cli/test_cookies.py` using Typer's `CliRunner`:
- `TestCookiesHelp` (1): `vidscope cookies --help` lists set/status/clear
- `TestCookiesStatus` (3): no cookies, valid file present, env override pointing elsewhere
- `TestCookiesSet` (4): valid file, invalid file → user error, missing source → user error, env override warns
- `TestCookiesClear` (4): removes file with --yes, no file → user error, prompt aborted, prompt confirmed

All tests use the existing `_sandbox` fixture pattern: `monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))` + `reset_config_cache()` so each test starts from a clean state.

**One small test fix**: the env-override status test originally asserted the full path string would appear in the Rich Table output, but Rich truncates long Windows temp paths. Switched to asserting only the filename (`elsewhere.txt`) which always survives the truncation.

**One ruff cleanup**: `validate_cookies_file()` had 7 return statements (PLR0911 max 6). Added `# noqa: PLR0911` because the 7 returns each express a distinct validation state — collapsing them would reduce readability. Pragmatic exception.

**Quality gates after T03**:
- ✅ pytest: **598 passed**, 5 deselected, in 14.93s (was 558 before M005, +40 = 15 validator + 13 use-case + 12 CLI cookies tests)
- ✅ mypy strict: **84 source files** OK (was 81, +3: cookies_validator.py, application/cookies.py, cli/commands/cookies.py)
- ✅ lint-imports: **9 contracts kept** (the tightened `application-has-no-adapters` from T02 now also forbids infrastructure imports, structurally enforced)
- ✅ ruff: clean (after the Annotated refactor + the noqa)

## Verification

All 4 quality gates clean in parallel: pytest 598 passed in 14.93s, mypy 84 source files OK, ruff clean, lint-imports 9 contracts kept.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest -q` | 0 | ✅ 598 passed | 14930ms |
| 2 | `python -m uv run mypy src` | 0 | ✅ 84 source files OK | 2100ms |
| 3 | `python -m uv run lint-imports` | 0 | ✅ 9 contracts kept | 2100ms |
| 4 | `python -m uv run ruff check .` | 0 | ✅ all checks passed | 800ms |

## Deviations

Used `Annotated[T, typer.Argument(...)]` style instead of the older `T = typer.Argument(...)` style used by other CLI files. The newer style is required to avoid `B008` for `Path` defaults and is the typer-recommended modern pattern.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/cli/commands/cookies.py`
- `src/vidscope/cli/commands/__init__.py`
- `src/vidscope/cli/app.py`
- `tests/unit/cli/test_cookies.py`
- `tests/unit/cli/test_app.py`
- `src/vidscope/application/cookies_validator.py`
