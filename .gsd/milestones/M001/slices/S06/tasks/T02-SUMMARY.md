---
id: T02
parent: S06
milestone: M001
key_files:
  - src/vidscope/infrastructure/container.py
  - tests/unit/infrastructure/test_container.py
  - tests/unit/cli/test_app.py
key_decisions:
  - IndexStage takes no constructor dependencies — the search_index port is reached via the UnitOfWork passed at execute time. Cleanest possible stage interface.
duration: 
verification_result: passed
completed_at: 2026-04-07T16:05:03.827Z
blocker_discovered: false
---

# T02: Wired IndexStage as the 5th and final pipeline stage; pipeline now runs ingest → transcribe → frames → analyze → index; 337 tests green.

**Wired IndexStage as the 5th and final pipeline stage; pipeline now runs ingest → transcribe → frames → analyze → index; 337 tests green.**

## What Happened

Container extension: appended `IndexStage()` to the pipeline runner stages list. The stage doesn't need any dependencies — it pulls everything from the UnitOfWork passed by the runner. Container test asserts stage_names is now `('ingest', 'transcribe', 'frames', 'analyze', 'index')`. CLI test_after_add expects 5 pipeline_runs.

337 unit tests pass (336 unit + 1 architecture, accounting for the new index stage tests). Quality gates clean.

## Verification

Ran `python -m uv run pytest -q` → 337 passed, 3 deselected. Ruff/mypy/lint-imports all clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest -q` | 0 | ✅ pass (337 tests, 3 deselected) | 2560ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/infrastructure/container.py`
- `tests/unit/infrastructure/test_container.py`
- `tests/unit/cli/test_app.py`
