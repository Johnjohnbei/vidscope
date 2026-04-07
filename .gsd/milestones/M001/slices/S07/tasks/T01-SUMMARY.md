---
id: T01
parent: S07
milestone: M001
key_files:
  - src/vidscope/infrastructure/config.py
  - tests/unit/infrastructure/test_config.py
key_decisions:
  - Three-step cookies resolution: env var > data_dir default > None. Each step is an honest signal about user intent (explicit override / convention / opt-out).
  - Config does NOT validate that the env-var-pointed file exists — T02 (downloader) does, so a typo surfaces as a typed IngestError at downloader init, not as a silent fallback to 'no cookies'
  - Default cookies path uses the data_dir convention (<data_dir>/cookies.txt) so users get a zero-config path: drop the file in their vidscope dir and it just works
  - cookies_file field defaults to None on the dataclass so existing test code that constructs Config directly (without passing cookies_file) continues to compile — backward-compat with the S05/S06 test fixtures
  - Module-level constants for the env var name and default filename so they're discoverable via grep and easy to reuse from T02-T07
duration: 
verification_result: passed
completed_at: 2026-04-07T13:42:36.578Z
blocker_discovered: false
---

# T01: Added cookies_file field to Config with three-step resolution (VIDSCOPE_COOKIES_FILE env > data_dir/cookies.txt > None) — 6 new tests, 249 total green, all gates clean.

**Added cookies_file field to Config with three-step resolution (VIDSCOPE_COOKIES_FILE env > data_dir/cookies.txt > None) — 6 new tests, 249 total green, all gates clean.**

## What Happened

T01 lays the configuration foundation for cookie-based authentication. The change is purely additive: existing public-content workflows continue to work because `cookies_file` defaults to None.

**Three-step resolution priority:**

1. **`VIDSCOPE_COOKIES_FILE` env var.** If set, the path is expanded (`~`) and resolved to absolute. The path is **NOT** validated for existence here — that's the downloader's job in T02. This preserves the typed-error pattern: a misconfigured env var becomes an `IngestError("cookies file not found")` from `YtdlpDownloader.__init__`, not a silent fall-through to "no cookies".

2. **Default `<data_dir>/cookies.txt`.** Only used when the env var is NOT set AND the file actually exists. This gives users a zero-config path: drop a `cookies.txt` in their vidscope data dir and it just works.

3. **None.** The opt-in feature is off when neither path resolves.

**Why config doesn't validate the env-var path:**

A natural reflex would be "if VIDSCOPE_COOKIES_FILE is set but the file doesn't exist, return None" or "raise". Both are wrong. Returning None silently masks an obvious user error (typo in the path). Raising a `ConfigError` would be too eager — it would break `vidscope --help` and other commands that don't actually need cookies. The clean answer is: Config returns the path the user told us, T02 validates it at downloader init time, and the failure surfaces as a typed `IngestError` only when something tries to actually use the cookies. T02's tests will cover the file-missing case explicitly.

**Tests — 6 new in `TestCookiesFileResolution`:**

- `test_no_cookies_configured_returns_none` — sandboxed temp dir, no env var, no default file → cookies_file is None
- `test_env_var_override_resolves_to_absolute_path` — set env var to a real file, verify cookies_file equals the resolved absolute path
- `test_default_cookies_path_picked_up_when_file_exists` — pre-create `<data_dir>/cookies.txt`, no env var → cookies_file is the default
- `test_default_cookies_path_ignored_when_file_missing` — no env var, no default file → None (the existence check matters)
- `test_env_var_takes_precedence_over_default` — both files exist, env var wins
- `test_env_var_path_returned_even_when_file_does_not_exist` — env var points at non-existent file → Config still returns it; documents the explicit decision that T02 will validate

**Module changes:**

- Module docstring updated with the cookies field and the three-step resolution rules
- Two new module-level constants: `_ENV_COOKIES_FILE = "VIDSCOPE_COOKIES_FILE"` and `_DEFAULT_COOKIES_FILENAME = "cookies.txt"`
- New helper `_resolve_cookies_file(data_dir)` with the priority logic
- `Config` dataclass gains `cookies_file: Path | None = None` (default None preserves backward compatibility — older code constructing Config directly doesn't break)
- `_build_config()` calls `_resolve_cookies_file(data_dir)` and passes the result

**Quality gates after T01:** pytest 249 passed (3 deselected integration), mypy strict clean on 52 files, ruff clean, import-linter 7 contracts kept. No regressions in any existing test.

## Verification

Ran `python -m uv run pytest tests/unit/infrastructure/test_config.py -q` → 15 passed in 310ms. Ran `python -m uv run pytest -q` → 249 passed, 3 deselected in 1.95s. Ran `python -m uv run mypy src` → Success: no issues found in 52 source files. Ran `python -m uv run lint-imports` → 7 contracts kept, 0 broken. Verified the field is present on Config: `python -m uv run python -c "from vidscope.infrastructure.config import Config; import dataclasses; print([f.name for f in dataclasses.fields(Config)])"` shows cookies_file in the list.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/infrastructure/test_config.py -q` | 0 | ✅ pass (15/15) | 310ms |
| 2 | `python -m uv run pytest -q` | 0 | ✅ pass (249 passed, 3 deselected) | 1950ms |
| 3 | `python -m uv run mypy src && python -m uv run lint-imports` | 0 | ✅ pass — mypy strict on 52 files, 7 contracts kept | 2000ms |

## Deviations

None. The T01 plan called for env var resolution, default file fallback, and tests covering all paths — all delivered as specified.

## Known Issues

None. The path validation gap (env var pointing at non-existent file returns the bad path instead of None) is intentional and documented — it's the seam T02 will close with a typed error at downloader init.

## Files Created/Modified

- `src/vidscope/infrastructure/config.py`
- `tests/unit/infrastructure/test_config.py`
