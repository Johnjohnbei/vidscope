---
id: T02
parent: S01
milestone: M001
key_files:
  - src/vidscope/__init__.py
  - src/vidscope/config.py
key_decisions:
  - Use `appauthor=False` with platformdirs so Windows path is %LOCALAPPDATA%/vidscope, not %LOCALAPPDATA%/Johnjohnbei/vidscope — matches Linux/macOS shape
  - Config is `frozen=True, slots=True` — no accidental mutation, lower memory
  - Config creates the directory tree but NOT the DB file — that's the data layer's responsibility (T03), keeps concerns separate
  - Expose `reset_config_cache()` as a documented test hook instead of letting tests reach into `_cached_config` directly
duration: 
verification_result: passed
completed_at: 2026-04-07T10:44:24.970Z
blocker_discovered: false
---

# T02: Created the src/vidscope/ package and a frozen-dataclass Config module with platformdirs-based path resolution and an env override.

**Created the src/vidscope/ package and a frozen-dataclass Config module with platformdirs-based path resolution and an env override.**

## What Happened

Created `src/vidscope/__init__.py` exporting `__version__ = "0.1.0"` and a short module docstring that names the tool's purpose. No re-exports of submodules — keeping the top-level namespace clean so future agents see exactly one public symbol per import level.

Implemented `src/vidscope/config.py` as specified in the plan. Key design choices:

- `Config` is a `frozen=True, slots=True` dataclass. Six fields: `data_dir`, `cache_dir`, `db_path`, `downloads_dir`, `frames_dir`, `models_dir`. All are `pathlib.Path`. Frozen means callers can't mutate the resolved config by accident — any new path must come through `get_config()` rebuilding.
- Default resolution via `platformdirs.user_data_dir(appname="vidscope", appauthor=False)`. `appauthor=False` is important on Windows: without it, platformdirs inserts a "Johnjohnbei" (or whatever author) segment into the path, which is both ugly and inconsistent with the Linux/macOS conventions we want to mirror.
- Override via `VIDSCOPE_DATA_DIR` env var. When set, the value is expanded (`~`) and resolved to an absolute path, then every subdirectory is rooted under it. This is the escape hatch tests will use.
- Five directories get created eagerly in `_build_config()` with `mkdir(parents=True, exist_ok=True)`: data_dir itself, cache, downloads, frames, models. The DB file is deliberately NOT created here — that's the data layer's job in T03. Config only guarantees the parent dir exists.
- Memoization via a module-level `_cached_config`. `get_config()` builds once per process. `reset_config_cache()` is exposed for tests (documented as "tests only") and drops the cache so the next call re-reads the env.

Smoke-tested by setting `VIDSCOPE_DATA_DIR` to a tempdir, calling `reset_config_cache()` + `get_config()`, and asserting: all five directories exist, the db_path parent exists, and the db_path file itself does not yet exist. All assertions passed.

## Verification

Ran an inline Python script under `python -m uv run` that: (1) sets VIDSCOPE_DATA_DIR to a fresh tempdir, (2) calls reset_config_cache() + get_config(), (3) asserts all five directories exist and the db file does not. Output: `ok`. Exit code 0.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run python -c "import os, tempfile; tmp = tempfile.mkdtemp(...); os.environ['VIDSCOPE_DATA_DIR'] = tmp; from vidscope.config import get_config, reset_config_cache; reset_config_cache(); c = get_config(); assert c.data_dir.exists(); assert c.cache_dir.exists(); assert c.downloads_dir.exists(); assert c.frames_dir.exists(); assert c.models_dir.exists(); assert not c.db_path.exists(); print('ok')"` | 0 | ✅ pass | 1200ms |

## Deviations

None. The plan's verify command passed as written.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/__init__.py`
- `src/vidscope/config.py`
