---
id: T08
parent: S01
milestone: M001
key_files:
  - src/vidscope/cli/__init__.py
  - src/vidscope/cli/app.py
  - src/vidscope/cli/_support.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/commands/add.py
  - src/vidscope/cli/commands/show.py
  - src/vidscope/cli/commands/list.py
  - src/vidscope/cli/commands/search.py
  - src/vidscope/cli/commands/status.py
  - src/vidscope/cli/commands/doctor.py
  - pyproject.toml
  - tests/unit/cli/test_app.py
key_decisions:
  - CLI is a package, one file per command, so adding a command is one new file + one `app.command(...)` line — never touching any existing file. Pattern scales to M002's MCP server which will be a sibling `mcp/` package with the same shape.
  - Every command uses `handle_domain_errors()` context manager so typed DomainErrors become exit 1 with a clean message — no command needs to duplicate error-handling boilerplate
  - `acquire_container()` is the single function the command layer uses to reach infrastructure. Keeps the per-command import surface to exactly {use case, _support}, which makes import-linter contracts easy to write in T09.
  - Exit code discipline: 0 = success, 1 = user error (bad URL, missing id, typed domain error), 2 = system error (missing binary, crash). Each maps to a distinct semantic the user can test in shell scripts.
  - Typer entry point updated to `vidscope.cli.app:app` (package-qualified) to match the new layout. `uv sync` picked up the change without manual intervention.
  - `doctor` command deliberately bypasses the use-case layer and calls `run_all_checks()` directly — it's a pure infrastructure introspection command, not a business operation, so forcing it through a use case would be ceremony.
  - Status table uses color per RunStatus (green/red/yellow/cyan/blue) so operators can scan 10 rows at a glance without reading every status column — `vidscope status` is the 3am diagnostic tool, the visual hierarchy matters
duration: 
verification_result: passed
completed_at: 2026-04-07T11:27:54.210Z
blocker_discovered: false
---

# T08: Built the Typer CLI as a package with six commands (add, show, list, search, status, doctor) each in its own file — 10 CLI tests, 182 total green, full end-to-end smoke from install to add to status.

**Built the Typer CLI as a package with six commands (add, show, list, search, status, doctor) each in its own file — 10 CLI tests, 182 total green, full end-to-end smoke from install to add to status.**

## What Happened

T08 closes the outermost ring. The CLI is the only surface the user touches, and it is now a thin dispatch layer: every command does exactly three things — build the container, instantiate a use case, format the typed result with rich. No business logic, no SQL, no adapter references, no error-swallowing. Typed DomainErrors are caught at the boundary and turned into user-facing messages with exit code 1.

**cli/app.py** — Root Typer app. `no_args_is_help=True` so bare `vidscope` prints help rather than exits silently. `rich_markup_mode="rich"` enables `[bold]` / `[green]` tags directly in docstrings. A `--version` flag registered as a callback prints the package version and exits. Every command is registered with an explicit help string via `app.command("name", help="...")(handler)` so the signature of each command function doesn't need to carry Typer-specific decorators in two places.

Three exit codes defined as module constants: `EXIT_OK=0`, `EXIT_USER_ERROR=1`, `EXIT_SYSTEM_ERROR=2`. User error covers bad URLs, missing ids, typed domain errors from use cases. System error covers missing binaries (reported via doctor) and unexpected crashes.

**cli/_support.py** — Shared helpers. Three functions the command files reach for:
- `acquire_container()` — the single place in the command layer that calls `build_container()`. Keeps the import surface of each command file minimal.
- `fail_user(msg)` / `fail_system(msg)` — print a red prefixed message and return a `typer.Exit(1|2)` that callers raise. `fail_system` also prints a `Run vidscope doctor` hint.
- `handle_domain_errors()` — context manager that catches any `DomainError` and converts it to `fail_user(str(exc))`. Every command wraps its body in `with handle_domain_errors():`.

**cli/commands/** — Six files, one per subcommand. Each imports exactly one use case, `acquire_container`, and `console`. That's the import budget.

- `add.py` — calls `IngestVideoUseCase`. On `RunStatus.FAILED` from the use case (e.g. empty URL) it raises `fail_user(message)`. On success it prints a rich `Panel` showing URL, status, run id, and the placeholder message about S02 being where real ingest lands.
- `status.py` — calls `GetStatusUseCase`. Prints the aggregate counts then either an empty-state hint or a rich `Table` with columns: id, phase, status (color-coded per status), video, started, duration, error (truncated to 80 chars). Status colors: green=OK, red=FAILED, yellow=SKIPPED, cyan=PENDING, blue=RUNNING.
- `list.py` — calls `ListVideosUseCase`. Same pattern: counts + table or empty hint. Columns: id, platform, title, author, duration, ingested date.
- `show.py` — calls `ShowVideoUseCase`. On `result.found=False` raises `fail_user(f"no video with id {id}")`. On found, prints a rich `Panel` for the video metadata plus inline lines for transcript, frames count, and analysis presence.
- `search.py` — calls `SearchLibraryUseCase`. Prints query + hit count, then a table of (video, source, rank, snippet) or the empty-state hint.
- `doctor.py` — calls `run_all_checks()` from infrastructure directly (the only command that bypasses the use-case layer because doctor is purely infrastructural). Prints a table with ok/fail per check, then for each failure prints the remediation block and exits with code 2.

**pyproject.toml** entry point updated from `vidscope.cli:app` to `vidscope.cli.app:app` to match the new package layout. `uv sync` picked up the change and rebuilt the package; `vidscope --help` now works from the shell.

**End-to-end manual smoke:**
- `vidscope --version` → `vidscope 0.1.0`
- `vidscope --help` → lists all 6 commands with descriptions
- `vidscope status` → `videos: 0 pipeline runs: 0` + empty-state hint, exit 0
- `vidscope doctor` → table showing ffmpeg=fail (not on PATH on this machine), yt-dlp=ok (2026.03.17), followed by the Windows/macOS/Linux install hint for ffmpeg, exit 2
- `vidscope list` → `total videos: 0`, empty hint, exit 0
- `vidscope search hello` → `query: 'hello' hits: 0`, empty hint, exit 0
- `vidscope add "https://www.youtube.com/watch?v=smoke"` → Panel: URL, status=pending, run id=1, S02 hint, exit 0
- `vidscope status` (after add) → `pipeline runs: 1`, table with the run, exit 0
- `vidscope add ""` → `error: url is empty`, exit 1
- `vidscope show 999` → `error: no video with id 999`, exit 1

Every exit code is correct. Every code path exercised.

**Tests (10 new in tests/unit/cli/test_app.py):**

Uses Typer's `CliRunner` which invokes the app in-process with a captured stdout. Every test gets a `tmp_path` sandboxed data dir via `VIDSCOPE_DATA_DIR` + `monkeypatch` + `reset_config_cache`. Tests: help lists every command, `--version` prints, status on empty DB shows 0 counts, status after add shows 1 run, add registers PENDING on a valid URL, add fails with exit 1 on empty URL, list shows empty state, search on empty index returns 0 hits, show fails with exit 1 for missing id, doctor runs and prints both check names (exit code 0 or 2 depending on ffmpeg presence, we accept both).

**Full suite** — 182 tests pass in 1.33s: domain 60 + ports 17 + infrastructure 29 + adapters 52 + pipeline 8 + application 6 + cli 10. Zero regressions.

**Observation worth recording:** This machine runs Python 3.13 from the Microsoft Store, which sandboxes `%LOCALAPPDATA%` through a per-package virtual layer (`AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\Local\vidscope`). The tool works correctly there — all I/O, DB writes, and reads function normally — it just lives in a different path than a non-Store Python would produce. Users who install from python.org or via `uv python install` get the canonical `%LOCALAPPDATA%\vidscope`. Documenting it here so the next agent investigating "where is my DB?" doesn't get confused.

## Verification

Ran `python -m uv run vidscope --help` → showed all six commands. Ran `python -m uv run vidscope --version` → `vidscope 0.1.0`. Ran `python -m uv run vidscope status` → empty state, exit 0. Ran `python -m uv run vidscope doctor` → ffmpeg=fail (not on PATH), yt-dlp=ok, remediation printed, exit 2. Ran `python -m uv run vidscope add "https://www.youtube.com/watch?v=smoke_t08"` → Panel with PENDING row. Ran `python -m uv run vidscope status` → showed the new row in a color-coded table. Ran `python -m uv run vidscope add ""` → exit 1 with "url is empty". Ran `python -m uv run vidscope show 999` → exit 1 with "no video with id 999". Ran `python -m uv run pytest tests/unit/cli -q` → 10 passed. Ran `python -m uv run pytest tests/unit -q` → 182 passed in 1.33s.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run vidscope --help` | 0 | ✅ pass — all six commands listed | 400ms |
| 2 | `python -m uv run vidscope add 'https://www.youtube.com/watch?v=smoke' && python -m uv run vidscope status` | 0 | ✅ pass — PENDING row written and displayed in the status table | 800ms |
| 3 | `python -m uv run vidscope add '' ; echo $?` | 1 | ✅ pass — exit 1 on empty URL with 'url is empty' message | 350ms |
| 4 | `python -m uv run vidscope show 999 ; echo $?` | 1 | ✅ pass — exit 1 with 'no video with id 999' | 350ms |
| 5 | `python -m uv run vidscope doctor` | 2 | ✅ pass — ffmpeg=fail (not installed), yt-dlp=ok, exit 2 with remediation printed | 400ms |
| 6 | `python -m uv run pytest tests/unit/cli -q` | 0 | ✅ pass (10/10) | 730ms |
| 7 | `python -m uv run pytest tests/unit -q` | 0 | ✅ pass (182/182 full suite) | 1330ms |

## Deviations

None. Every planned command exists, every test passes, the entry point update in pyproject.toml took effect after `uv sync`.

## Known Issues

Windows Store Python sandboxes %LOCALAPPDATA% under a package-specific path. Not a bug in vidscope — just a platform quirk worth knowing about. Documented in the narrative for future debugging.

## Files Created/Modified

- `src/vidscope/cli/__init__.py`
- `src/vidscope/cli/app.py`
- `src/vidscope/cli/_support.py`
- `src/vidscope/cli/commands/__init__.py`
- `src/vidscope/cli/commands/add.py`
- `src/vidscope/cli/commands/show.py`
- `src/vidscope/cli/commands/list.py`
- `src/vidscope/cli/commands/search.py`
- `src/vidscope/cli/commands/status.py`
- `src/vidscope/cli/commands/doctor.py`
- `pyproject.toml`
- `tests/unit/cli/test_app.py`
