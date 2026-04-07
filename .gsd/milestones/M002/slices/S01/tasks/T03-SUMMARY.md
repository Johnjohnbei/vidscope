---
id: T03
parent: S01
milestone: M002
key_files:
  - src/vidscope/cli/commands/mcp.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - src/vidscope/infrastructure/startup.py
  - tests/unit/infrastructure/test_startup.py
key_decisions:
  - Lazy import of `vidscope.mcp.server.main` inside the CLI serve() function — `vidscope --help` stays fast, users browsing help don't pay the mcp+pydantic+starlette load cost
  - check_mcp_sdk uses `importlib.metadata.version('mcp')` instead of reading `mcp.__version__` — the SDK doesn't expose `__version__` at module level in 1.27.0, but the package metadata always does
  - Import-failure test uses `monkeypatch.setattr(PathFinder, 'find_spec', ...)` to block imports at the machinery level — cleaner than swapping sys.modules entries which can have weird caching effects
  - mcp_app registered via add_typer so `vidscope mcp serve` is the full path, not `vidscope mcp-serve` or `vidscope serve-mcp`. Matches the existing pattern used by Typer sub-applications elsewhere.
duration: 
verification_result: passed
completed_at: 2026-04-07T17:13:50.580Z
blocker_discovered: false
---

# T03: Added `vidscope mcp serve` CLI subcommand + check_mcp_sdk doctor check (mcp 1.27.0 confirmed). doctor now shows 4 rows (ffmpeg, yt-dlp, mcp, cookies). 353 tests green.

**Added `vidscope mcp serve` CLI subcommand + check_mcp_sdk doctor check (mcp 1.27.0 confirmed). doctor now shows 4 rows (ffmpeg, yt-dlp, mcp, cookies). 353 tests green.**

## What Happened

Created `src/vidscope/cli/commands/mcp.py` with a Typer sub-application. The `serve` command lazily imports `vidscope.mcp.server.main` and calls it — the lazy import matters because it keeps `vidscope --help` fast: users browsing help don't pay the cost of loading mcp + pydantic + starlette + uvicorn unless they actually run `mcp serve`. Sub-application registered on the root app via `app.add_typer(mcp_app, name="mcp")` in `cli/app.py`.

Added `check_mcp_sdk()` to `infrastructure/startup.py`. Imports the mcp package, reads the version via `importlib.metadata.version("mcp")`, returns a CheckResult. Three failure paths covered: ImportError, metadata unavailable, success with version string. `run_all_checks()` now returns 4 results (ffmpeg, yt-dlp, mcp, cookies). The order matters for the doctor display: I chose to put mcp before cookies since mcp is a hard dep while cookies is optional.

Tests updated: `test_returns_one_result_per_check` expects 4 results with the new `{ffmpeg, yt-dlp, mcp, cookies}` set. Added a `TestCheckMcpSdk` class with two tests: happy path against the real mcp import (works because mcp is a runtime dep), and an import-failure path that uses `monkeypatch.setattr` on `importlib.machinery.PathFinder.find_spec` to block the `mcp` import and force the ImportError branch.

**Live doctor output** (with ffmpeg on PATH):
```
                                vidscope doctor                                
+-----------------------------------------------------------------------------+
| check   | status | detail                                                   |
|---------+--------+----------------------------------------------------------|
| ffmpeg  | ok     | ffmpeg version 8.1-full_build-www.gyan.dev               |
| yt-dlp  | ok     | 2026.03.17                                               |
| mcp     | ok     | 1.27.0                                                   |
| cookies | ok     | not configured (optional)                                |
+-----------------------------------------------------------------------------+
```

Exit 0 — every check passes on the dev machine.

**Live mcp help** confirms the sub-application is wired:
```
 Usage: vidscope mcp [OPTIONS] COMMAND [ARGS]...                               
 MCP (Model Context Protocol) server for AI agents.                            
 Commands:
 | serve  Start the vidscope MCP server on stdio.                              |
```

**Quality gates:** 353 passed (351 + 2 new mcp-check tests), 3 deselected, ruff clean (1 auto-fix), mypy strict clean on 68 files, import-linter 7 contracts kept (the new `mcp` layer contract comes in T04).

## Verification

Ran `python -m uv run vidscope doctor` → 4 rows shown (ffmpeg+yt-dlp+mcp+cookies), exit 0 with ffmpeg on PATH. Ran `python -m uv run vidscope mcp --help` → sub-app with `serve` command visible. Ran `python -m uv run pytest tests/unit/infrastructure -q` → 27 passed. Ran full suite → 353 passed, 3 deselected. All gates clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run vidscope doctor` | 0 | ✅ 4 rows: ffmpeg+yt-dlp+mcp+cookies all green | 600ms |
| 2 | `python -m uv run vidscope mcp --help` | 0 | ✅ mcp sub-app visible with serve command | 400ms |
| 3 | `python -m uv run pytest -q` | 0 | ✅ 353 passed, 3 deselected | 3140ms |

## Deviations

None.

## Known Issues

None. The server process hasn't actually been tested over stdio yet — that's T05's subprocess integration test.

## Files Created/Modified

- `src/vidscope/cli/commands/mcp.py`
- `src/vidscope/cli/commands/__init__.py`
- `src/vidscope/cli/app.py`
- `src/vidscope/infrastructure/startup.py`
- `tests/unit/infrastructure/test_startup.py`
