---
estimated_steps: 1
estimated_files: 10
skills_used: []
---

# T05: Infrastructure layer: relocate config, add composition root, SQLite engine, startup checks

Create src/vidscope/infrastructure/ and relocate config.py from src/vidscope/config.py into src/vidscope/infrastructure/config.py (same public API — get_config, reset_config_cache, Config dataclass — plus a compatibility shim at src/vidscope/config.py that re-exports from infrastructure.config with a DeprecationWarning that tells callers to import from vidscope.infrastructure.config). Add `infrastructure/sqlite_engine.py` exposing `build_engine(db_path: Path) -> Engine` that creates the engine and attaches the PRAGMA foreign_keys=ON listener. Add `infrastructure/startup.py` with `check_ffmpeg()` and `check_ytdlp()` returning a `CheckResult(name, ok, version_or_error, remediation)` dataclass + `run_all_checks() -> list[CheckResult]`; ffmpeg via subprocess `ffmpeg -version` with 5s timeout, yt-dlp via module import + version attribute. Add `infrastructure/container.py` — the composition root — exposing `build_container(config: Config | None = None) -> Container` where Container is a frozen dataclass holding every wired port (config, engine, unit_of_work_factory, media_storage, clock, and use-case-ready dependencies). build_container is THE only function in the codebase allowed to instantiate concrete adapters. Add tests/unit/infrastructure/ with test_config.py (env override + path creation), test_startup.py (monkeypatched subprocess for missing ffmpeg), test_container.py (build_container returns a fully wired container when given a tmp_path data dir via env var).

## Inputs

- ``src/vidscope/config.py` — existing config module from T02, to be relocated`
- ``src/vidscope/ports/__init__.py` — Protocol types the container wires`
- ``src/vidscope/domain/__init__.py` — value objects used by Config`

## Expected Output

- ``src/vidscope/infrastructure/config.py` — relocated Config + get_config + reset_config_cache`
- ``src/vidscope/infrastructure/sqlite_engine.py` — build_engine with PRAGMA FK listener`
- ``src/vidscope/infrastructure/startup.py` — CheckResult + check_ffmpeg + check_ytdlp + run_all_checks`
- ``src/vidscope/infrastructure/container.py` — Container dataclass + build_container composition root`
- ``src/vidscope/config.py` — compatibility shim re-exporting from infrastructure.config`
- ``tests/unit/infrastructure/test_config.py` — env override + path creation assertions`
- ``tests/unit/infrastructure/test_startup.py` — missing-ffmpeg path via monkeypatched subprocess`
- ``tests/unit/infrastructure/test_container.py` — build_container wires every port`

## Verification

python -m uv run pytest tests/unit/infrastructure -q && python -m uv run python -c "from vidscope.infrastructure.container import build_container; c = build_container(); assert c.config is not None; assert c.engine is not None; assert c.media_storage is not None; print('container ok')"
