# S01: Cookies file validation + status + clear (read-only + simple writes)

**Goal:** Ship the read-only and simple-write cookies subcommands first: set, status, clear. These don't need to talk to yt_dlp — just file operations + format validation. Builds the Typer sub-application skeleton + the validator helper + the application use cases.
**Demo:** After this: vidscope cookies status / clear / set work end-to-end with format validation.

## Tasks
- [x] **T01: Shipped permissive Netscape cookies validator with 15 unit tests covering valid files, no-header exports, mixed comments, CRLF, and every error path.** — Create src/vidscope/infrastructure/cookies_validator.py with validate_cookies_file(path) -> CookiesValidation. CookiesValidation is a frozen dataclass with: ok (bool), reason (str), entries_count (int). Format check: starts with '# Netscape HTTP Cookie File' or '# HTTP Cookie File' or any other header line that starts with '#', skips comment + blank lines, parses tab-separated rows, requires 7 columns per row. Permissive about whitespace. Tests: valid file, missing file, empty file, comments-only, malformed rows, mix of comments and valid rows.
  - Estimate: 1h
  - Files: src/vidscope/infrastructure/cookies_validator.py, tests/unit/infrastructure/test_cookies_validator.py
  - Verify: python -m uv run pytest tests/unit/infrastructure/test_cookies_validator.py -q
- [x] **T02: Shipped 3 cookies use cases (Set/GetStatus/Clear) + tightened the application-has-no-adapters contract to also forbid infrastructure imports. Surfaced an architectural hole and closed it.** — Create src/vidscope/application/cookies.py with 3 use cases: SetCookiesUseCase(config, validator) -> SetCookiesResult; GetCookiesStatusUseCase(config, validator) -> CookiesStatus; ClearCookiesUseCase(config) -> ClearCookiesResult. Set copies a source path into <data_dir>/cookies.txt after validating. Status reads the configured cookies file and returns path/size/mtime/validation. Clear removes the file (raises if missing or path is not under data_dir for safety). Each use case is a small dataclass with inputs and a typed result. Tests via tmp_path with sandboxed VIDSCOPE_DATA_DIR.
  - Estimate: 1h30m
  - Files: src/vidscope/application/cookies.py, tests/unit/application/test_cookies.py
  - Verify: python -m uv run pytest tests/unit/application/test_cookies.py -q
- [x] **T03: Shipped vidscope cookies sub-application (set/status/clear) wired to the M005 use cases. Registered alongside watch + mcp via add_typer. 12 CLI tests, all 4 quality gates clean (598 unit tests, 84 source files, 9 contracts).** — Create src/vidscope/cli/commands/cookies.py with a Typer sub-application exposing 3 commands: set <source-path>, status, clear [--yes]. set and clear print success/failure with rich formatting. status prints a small table with path/size/mtime/valid. Register cookies_app via add_typer in src/vidscope/cli/app.py. Tests via Typer's CliRunner.
  - Estimate: 1h30m
  - Files: src/vidscope/cli/commands/cookies.py, src/vidscope/cli/app.py, tests/unit/cli/test_cookies.py, tests/unit/cli/test_app.py
  - Verify: python -m uv run pytest tests/unit/cli/test_cookies.py tests/unit/cli/test_app.py -q && python -m uv run mypy src && python -m uv run lint-imports && python -m uv run ruff check .
