---
id: T05
parent: S01
milestone: M001
key_files:
  - src/vidscope/infrastructure/__init__.py
  - src/vidscope/infrastructure/config.py
  - src/vidscope/infrastructure/sqlite_engine.py
  - src/vidscope/infrastructure/startup.py
  - src/vidscope/infrastructure/container.py
  - src/vidscope/config.py
  - tests/unit/infrastructure/test_config.py
  - tests/unit/infrastructure/test_startup.py
  - tests/unit/infrastructure/test_container.py
key_decisions:
  - SQLite engine factory enables `PRAGMA foreign_keys=ON` AND `PRAGMA journal_mode=WAL` on every connection via a `connect` event listener — the two pragmas that turn SQLite from a fragile toy into a safe concurrent data store for a local CLI
  - Schema creation is explicitly NOT a responsibility of the engine factory — that's an adapter concern. Keeps the layer boundary clean and means tests can build engines against temp databases without triggering schema I/O.
  - `SystemClock` is a module-level class (not a nested one inside `build_container`) so mypy sees a named type and import-linter sees an importable symbol — both needed for T09's strict type checking and layering rules
  - Container stays tiny in T05 (config/engine/clock) and is extended purely additively by T06/T07. No placeholder None fields, no fake adapters just to pass a verify command — honest incremental growth.
  - Startup checks have platform-aware remediation strings with the exact install command per OS. The user sees `winget install Gyan.FFmpeg` on Windows, `brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Linux — no Googling required at 3am.
  - ffmpeg check runs `shutil.which` FIRST (cheap) and only then subprocess (expensive). All five distinct failure modes (missing, timeout, non-zero exit, OS error, missing version line) produce separate, debuggable messages.
duration: 
verification_result: passed
completed_at: 2026-04-07T11:08:01.463Z
blocker_discovered: false
---

# T05: Built the infrastructure layer: relocated Config, added SQLite engine factory with FK + WAL pragmas, startup checks for ffmpeg/yt-dlp, and the composition-root Container — 26 unit tests, 103 total green.

**Built the infrastructure layer: relocated Config, added SQLite engine factory with FK + WAL pragmas, startup checks for ffmpeg/yt-dlp, and the composition-root Container — 26 unit tests, 103 total green.**

## What Happened

T05 closes the outer ring of the architecture (together with T08's CLI). The infrastructure layer is the only layer allowed to touch the environment, compose adapters, and build transactional engines. Everything else receives its dependencies via constructor injection from a :class:`Container`.

**infrastructure/config.py** — Relocated from `src/vidscope/config.py` with the same public API (`Config`, `get_config`, `reset_config_cache`). The original T02 module is now a compatibility shim that re-exports from infrastructure and emits a `DeprecationWarning` pointing callers at the correct import path. Zero behavior change for existing callers, correct architectural placement going forward. The shim is cheap insurance: no existing caller imports the old path yet, but the pattern is now documented for future relocations.

**infrastructure/sqlite_engine.py** — A `build_engine(db_path: Path) -> Engine` factory. This is the single place in the codebase that constructs a raw SQLAlchemy engine. Two SQLite-specific pragmas applied via a `connect` listener on every new connection: `PRAGMA foreign_keys=ON` (without it, every `ON DELETE CASCADE` in the schema is silently ignored — classic SQLite footgun) and `PRAGMA journal_mode=WAL` (lets `vidscope search` read concurrently with `vidscope add` writing on the same file). `future=True` enables SQLAlchemy 2.0 style from the engine up. The module deliberately does NOT call `init_db` — schema creation is an adapter concern, not an infrastructure concern, and that separation is now enforceable.

**infrastructure/startup.py** — `check_ffmpeg()` and `check_ytdlp()` return a frozen `CheckResult(name, ok, version_or_error, remediation)` dataclass. The ffmpeg check runs `shutil.which` first (cheap), then `ffmpeg -version` with a 5-second timeout (expensive but authoritative). Five failure modes are all surfaced with distinct messages: binary missing, subprocess timeout, non-zero exit, OS error during exec, and missing version line. The remediation string is platform-aware and includes the exact install command for Windows/macOS/Linux. `check_ytdlp()` imports the Python module (yt-dlp is a runtime dep) and reads its version attribute with a fallback for builds that expose `__version__` directly vs via `version.__version__`. `run_all_checks()` is the single entry point the CLI doctor command consumes.

**infrastructure/container.py** — The composition root. `Container` is a frozen dataclass with three fields today: `config`, `engine`, `clock`. `build_container(config=None)` resolves the config (honoring the env override), builds the engine, and wires a `SystemClock` (module-level class, not nested, so mypy sees a named type and import-linter sees an importable symbol). T06 extends the dataclass with `media_storage` and `unit_of_work_factory`; T07 adds `pipeline_runner`. Every extension is purely additive — existing fields never change. This is what makes growing the container safe across slices.

`SystemClock.now()` returns `datetime.now(timezone.utc)` — timezone-aware, always. The test suite verifies the returned datetime has zero UTC offset and that `SystemClock` is a structural instance of the `Clock` port (it is — via `@runtime_checkable`).

**Tests — 26 new in `tests/unit/infrastructure/`:**

- `test_config.py` (9 tests): env override sandboxed with `tmp_path` + `monkeypatch`, memoization, reset-cache rebuild, frozen-ness, tilde expansion on Windows/Unix via monkeypatching `HOME`/`USERPROFILE`.
- `test_startup.py` (8 tests): every ffmpeg failure mode monkeypatched (`shutil.which` returning None, `subprocess.run` raising `TimeoutExpired`, non-zero exit, OSError). The happy path stubs subprocess with a fake `CompletedProcess`. yt-dlp happy path uses the real import so we get authentic version detection; the "missing version" failure path replaces the module in `sys.modules` with a stub.
- `test_container.py` (9 tests): container field presence, env sandboxing, accepting an explicit Config, frozen-ness, engine URL matches config.db_path, `SystemClock` is UTC-aware and conforms to `Clock` protocol, and two PRAGMA smoke tests (`PRAGMA foreign_keys` returns 1, `PRAGMA journal_mode` returns 'wal') that actually open a connection and read the pragmas back.

The PRAGMA tests are the most important: they prove the pragmas aren't just configured in code but actually applied on every connection. Without them we'd have a false sense of security if someone accidentally removed the `@event.listens_for` decorator.

**Full suite** — 103 tests pass in 410ms (domain 60 + ports 17 + infrastructure 26). The rest of S01 (T06–T10) builds on this foundation.

## Verification

Ran `python -m uv run pytest tests/unit/infrastructure -q` → 26 passed in 1.23s (first run hits the PRAGMA/connection cost, subsequent runs are faster). Ran `python -m uv run pytest tests/unit -q` → 103 passed in 410ms across domain + ports + infrastructure. Ran `python -m uv run python -c "from vidscope.infrastructure.container import build_container; c = build_container(); print(c.config.data_dir); print(c.engine.url); print(c.clock.now())"` → resolved the real Windows data dir, built a valid SQLAlchemy engine URL, and returned a UTC-aware timestamp. The real ffmpeg/yt-dlp checks against the host are exercised by the doctor command in T08 — for T05 they're covered via monkeypatching and a real yt-dlp import.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/infrastructure -q` | 0 | ✅ pass (26/26) | 1230ms |
| 2 | `python -m uv run pytest tests/unit -q` | 0 | ✅ pass (103/103 across domain + ports + infrastructure) | 410ms |
| 3 | `python -m uv run python -c 'from vidscope.infrastructure.container import build_container; c = build_container(); print(c.config.data_dir); print(c.engine.url); print(c.clock.now())'` | 0 | ✅ pass — container builds against real %LOCALAPPDATA%/vidscope, valid engine URL, UTC-aware timestamp | 500ms |

## Deviations

Plan said "build_container should wire media_storage" — I explicitly did NOT do that in T05 because the LocalMediaStorage adapter doesn't exist yet. Inventing a NullMediaStorage stub just to pass a verification check would be the kind of dishonest corner-cut this project is avoiding. T06 adds the real adapter and extends the Container dataclass with the missing fields. The Container class docstring explicitly documents the growth model so the next agent (me, in T06) has a clear mandate.

## Known Issues

None. The compatibility shim at `src/vidscope/config.py` will emit a DeprecationWarning on import — this is intentional. When ruff/mypy run over the whole tree in T09, I'll confirm no code currently imports the old path and consider removing the shim entirely. For now it stays as documentation of the pattern.

## Files Created/Modified

- `src/vidscope/infrastructure/__init__.py`
- `src/vidscope/infrastructure/config.py`
- `src/vidscope/infrastructure/sqlite_engine.py`
- `src/vidscope/infrastructure/startup.py`
- `src/vidscope/infrastructure/container.py`
- `src/vidscope/config.py`
- `tests/unit/infrastructure/test_config.py`
- `tests/unit/infrastructure/test_startup.py`
- `tests/unit/infrastructure/test_container.py`
