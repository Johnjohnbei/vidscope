---
id: T09
parent: S01
milestone: M001
key_files:
  - pyproject.toml
  - .importlinter
  - tests/architecture/__init__.py
  - tests/architecture/test_layering.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/adapters/sqlite/video_repository.py
  - src/vidscope/adapters/fs/local_media_storage.py
  - src/vidscope/pipeline/runner.py
  - src/vidscope/domain/values.py
  - src/vidscope/domain/__init__.py
key_decisions:
  - Use `StrEnum` (Python 3.11+) instead of `(str, Enum)` — ruff UP042 compliance, same runtime behavior, simpler intent
  - `SqliteUnitOfWork` declares repository attributes with Protocol types (`VideoRepository`, etc.) not concrete classes — makes it a structural subtype of `UnitOfWork` with zero casts in the container. The actual instances are still the concrete adapters; only the type annotations change.
  - `.importlinter` uses two directional `forbidden` contracts for cross-adapter prevention (sqlite→fs and fs→sqlite) instead of one bidirectional rule with `ignore_imports` hacks — cleaner, no warnings
  - `infrastructure/` is deliberately NOT in the layers stack — it's the composition root and must be free to import every layer to wire them. The layering contract enforces the inward-only rule on every OTHER package.
  - Architecture tests run `lint-imports` as a subprocess (with `shutil.which` guard + skip) rather than importing import-linter's Python API — authoritative because it's the exact command a human runs on the CLI
  - Test parses the subprocess stdout to verify every expected contract name is KEPT — catches silent contract drops due to `.importlinter` typos that would leave the architecture unprotected
  - ASCII hyphens in contract names instead of em-dashes for Windows CP1252 console compatibility — a tiny but real cross-platform gotcha
  - Disabled ruff TC001/TC002/TC003 (move runtime imports under TYPE_CHECKING) — at our scale the optimization is not worth the readability cost and hurts IDE hover tooltips
duration: 
verification_result: passed
completed_at: 2026-04-07T11:36:10.255Z
blocker_discovered: false
---

# T09: Landed the full quality-gate baseline: ruff clean, mypy strict clean on 47 files, import-linter with 7 hexagonal-architecture contracts enforced via a pytest architecture test, 185 total tests green.

**Landed the full quality-gate baseline: ruff clean, mypy strict clean on 47 files, import-linter with 7 hexagonal-architecture contracts enforced via a pytest architecture test, 185 total tests green.**

## What Happened

T09 turns "we have good architecture" into "the architecture can't silently rot". Four tools run over the full tree and all four are now clean and enforced as part of the test suite.

**pyproject.toml additions** — Added `[tool.pytest.ini_options]` with strict markers, explicit testpaths, and a filterwarnings entry to silence the deliberate DeprecationWarning from the `vidscope.config` shim. Registered three markers: `unit`, `integration`, `architecture`. Added `[tool.ruff]` with target-py312, line-length 100, and a comprehensive select list (E, W, F, I, UP, B, SIM, RUF, TCH, PL). Added `[tool.ruff.lint.per-file-ignores]` so tests can use magic numbers, `assert`, and local imports without noise, and so `cli/commands/list.py` is allowed to shadow the builtin. Added `[tool.mypy]` with `strict=true`, `warn_unused_ignores`, `warn_return_any`, `disallow_untyped_defs`, and a per-module override for `yt_dlp` (no stubs). Added `[tool.coverage.run]` with source=src/vidscope and branch coverage.

**.importlinter** — Seven contracts:
1. `Hexagonal layering - inward-only` — the layers contract declaring cli → application → pipeline → adapters → ports → domain. `infrastructure` is deliberately omitted from the layers stack because it is the composition root and must be free to import any layer to wire them together.
2. `sqlite adapter does not import fs adapter` — forbidden contract. Directional: prevents one adapter from knowing about another.
3. `fs adapter does not import sqlite adapter` — symmetric of above.
4. `Domain is pure Python - no third-party runtime deps` — forbidden contract banning sqlalchemy, typer, rich, platformdirs, yt_dlp, faster_whisper from vidscope.domain.
5. `Ports are pure Python - no third-party runtime deps` — same ban list for vidscope.ports.
6. `Pipeline layer depends only on ports and domain` — forbidden contract banning vidscope.adapters.*, vidscope.infrastructure, vidscope.cli from vidscope.pipeline.
7. `Application layer depends only on ports and domain` — forbidden contract banning vidscope.adapters.* and vidscope.cli from vidscope.application. Note: application IS allowed to import pipeline (because use cases orchestrate the pipeline runner).

First attempt used directional pairs with `ignore_imports` that didn't match anything, triggering a warning. Simplified to two directional forbidden contracts instead — cleaner, no warnings.

**ruff fixes applied:**
- 75 auto-fixes from the initial run (unused imports, datetime.UTC alias, pyupgrade syntax).
- `Platform`, `Language`, `StageName`, `RunStatus` migrated from `(str, Enum)` to `StrEnum` (UP042). Values and behavior unchanged, tests still pass.
- `local_media_storage.py`: `try/except/pass` replaced with `contextlib.suppress(OSError)` (SIM105).
- `video_repository.py`: `from sqlalchemy import func` moved from lazy inside `count()` to the top-level import block (PLC0415).
- `domain/__init__.py`: added `# noqa: RUF022` comment on `__all__` to keep the concern-grouped ordering (entities / errors / values) over strict alphabetical sort.
- Disabled TC001/TC002/TC003 in config — TYPE_CHECKING migration for runtime imports is optional and hurts IDE hover readability at our scale.
- Disabled PLW0603 for the `global _cached_config` singleton in config.py (intentional, documented via `reset_config_cache()`).
- Disabled RUF001/RUF002 for typographic apostrophes (French test strings in FTS5 tests).
- Added tests/**: PLC0415 ignore so tests can `from vidscope.domain import X` inside a test function body.

**mypy strict fixes applied:**
- `runner.py`: added `from datetime import datetime` at the top, typed the `uow: UnitOfWork` and `started_at: datetime` parameters on `_record_skipped` and `_record_failure`, removed the `# type: ignore[no-untyped-def]` markers. Also removed `return run` at the end of `_record_failure` (function already returned via the expression, and the variable was shadowing — mypy flagged it as "returning Any").
- `adapters/sqlite/unit_of_work.py`: typed `self._transaction: RootTransaction | None = None` (was inferred as plain `None`). Added import of `RootTransaction` from `sqlalchemy.engine.base`.
- `adapters/sqlite/unit_of_work.py`: **key fix**. Retyped the repository attributes from the concrete classes (`VideoRepositorySQLite`, etc.) to the Protocol types (`VideoRepository`, etc.). mypy was complaining that `SqliteUnitOfWork` wasn't assignable to the `UnitOfWork` Protocol because repository attribute types were more specific. Using Protocol types on the attributes makes `SqliteUnitOfWork` a structural subtype of `UnitOfWork` with zero casts required in the container.
- `pyproject.toml`: trimmed the mypy overrides to just `yt_dlp` — the `yt_dlp.*` and `faster_whisper.*` entries weren't matching anything and mypy was warning about the unused section.

**tests/architecture/test_layering.py** — Three tests with the `architecture` marker:
1. `test_importlinter_file_exists` — sanity check that `.importlinter` is on disk.
2. `test_lint_imports_exits_zero` — runs `lint-imports` as a subprocess (via `shutil.which`), asserts exit code 0. Skips if the binary isn't on PATH so the test file still imports cleanly in non-dev environments.
3. `test_every_expected_contract_is_kept` — parses the `lint-imports` stdout, asserts each of the seven expected contract names appears with a KEPT verdict. Catches the case where a contract silently gets dropped because of a typo in `.importlinter`.

Had to fix one encoding issue: the em-dashes (`—`) in the original contract names rendered as `?` in Windows CP1252 console output, so the test string comparison failed. Replaced every `—` with an ASCII hyphen across `.importlinter` and the test's EXPECTED_CONTRACTS tuple. Cross-platform safe now.

**Final verification suite — four green gates:**
- `uv run pytest -q` → 185/185 passed in 1.67s (60 domain + 17 ports + 29 infrastructure + 52 adapters + 8 pipeline + 6 application + 10 cli + 3 architecture)
- `uv run ruff check src tests` → All checks passed
- `uv run mypy src` (strict) → no issues in 47 files
- `uv run lint-imports` → 7 contracts kept, 0 broken, 65 files and 235 dependencies analyzed

The architecture is now under mechanical lock. Any future agent (or me, in a fresh context) who tries to import a concrete adapter from the pipeline layer, or SQLAlchemy from the domain, or yt-dlp from the ports, will get a loud red test before they get a chance to push.

## Verification

Ran each tool independently and all four pass clean: `python -m uv run pytest -q` → 185 passed in 1.67s. `python -m uv run ruff check src tests` → All checks passed. `python -m uv run mypy src` → Success: no issues found in 47 source files. `python -m uv run lint-imports` → Analyzed 65 files, 235 dependencies, Contracts: 7 kept, 0 broken. Also verified the architecture test integrates cleanly into the main pytest suite — it runs as part of `pytest` with the `@pytest.mark.architecture` marker and contributes 3 of the 185 total tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest -q` | 0 | ✅ pass (185/185 full suite including architecture tests) | 1670ms |
| 2 | `python -m uv run ruff check src tests` | 0 | ✅ pass — All checks passed | 200ms |
| 3 | `python -m uv run mypy src` | 0 | ✅ pass — no issues found in 47 source files (strict mode) | 6000ms |
| 4 | `python -m uv run lint-imports` | 0 | ✅ pass — 7 contracts kept, 0 broken, 65 files / 235 deps analyzed | 1500ms |

## Deviations

Two planned ignores turned into simplifications I wasn't expecting:

1. The `TC001/TC002/TC003` rules (move runtime imports under `TYPE_CHECKING`) generated 74 warnings on legitimate imports that are used in annotations but also inspected at runtime by Protocol machinery. Honoring them would have meant sprinkling `if TYPE_CHECKING:` blocks all over the ports layer without benefit. Disabled instead.

2. Initial `.importlinter` had directional cross-adapter rules with `ignore_imports` entries to skip intra-adapter imports — import-linter warned that the ignored imports didn't match anything. Replaced with two cleaner directional `forbidden` contracts (sqlite→fs and fs→sqlite) so neither package is ever asked to forbid itself.

Third deviation: ran into an encoding issue on Windows CP1252 console — em-dashes (`—`) in the contract names rendered as `?` in subprocess captured output, breaking the parse-the-output assertion. Replaced every `—` with an ASCII hyphen in both `.importlinter` and the test's expected tuple. Cross-platform safe now.

## Known Issues

None. All four gates are clean on the full tree. The architecture test is part of the main pytest suite and will fail loud on any layering regression.

## Files Created/Modified

- `pyproject.toml`
- `.importlinter`
- `tests/architecture/__init__.py`
- `tests/architecture/test_layering.py`
- `src/vidscope/adapters/sqlite/unit_of_work.py`
- `src/vidscope/adapters/sqlite/video_repository.py`
- `src/vidscope/adapters/fs/local_media_storage.py`
- `src/vidscope/pipeline/runner.py`
- `src/vidscope/domain/values.py`
- `src/vidscope/domain/__init__.py`
