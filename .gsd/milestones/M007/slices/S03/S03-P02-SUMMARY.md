---
plan_id: S03-P02
phase: M007/S03
subsystem: pipeline
tags: [pipeline, stage, link-extraction, container, di, tdd]
dependency_graph:
  requires: [S02-P02, S03-P01]
  provides: [MetadataExtractStage, pipeline-6-stages]
  affects: [container, pipeline_runner, test_app, test_container]
tech_stack:
  added: []
  patterns: [TDD-RED-GREEN, Stage-Protocol, DI-LinkExtractor, resume-safe-is_satisfied]
key_files:
  created:
    - src/vidscope/pipeline/stages/metadata_extract.py
    - tests/unit/pipeline/test_metadata_extract_stage.py
  modified:
    - src/vidscope/pipeline/stages/__init__.py
    - src/vidscope/infrastructure/container.py
    - tests/unit/infrastructure/test_container.py
    - tests/unit/cli/test_app.py
decisions:
  - MetadataExtractStage always calls add_many_for_video even with empty list for idempotence consistency
  - link_extractor kept as local variable in build_container (not exposed as Container field) — no use case reads it outside the stage in M007
  - Pre-existing ruff F401 in test_list_creator_videos.py deferred (out of scope)
metrics:
  duration: ~15min
  completed: 2026-04-18
  tasks_completed: 2
  files_modified: 6
requirements: [R044]
---

# Phase M007 Plan S03-P02: MetadataExtractStage + Container Wiring Summary

MetadataExtractStage extracts URLs from video description and transcript via RegexLinkExtractor port, persists to links table, and is wired as the fifth stage in the 6-stage pipeline between AnalyzeStage and IndexStage.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T01 RED | Failing tests for MetadataExtractStage | 6fdba6e | tests/unit/pipeline/test_metadata_extract_stage.py |
| T01 GREEN | Create MetadataExtractStage + export | 9b2f027 | stages/metadata_extract.py, stages/__init__.py |
| T02 | Wire MetadataExtractStage in container | e148bed | container.py, test_container.py, test_app.py, test_metadata_extract_stage.py |

## What Was Built

### T01 — MetadataExtractStage (TDD)

**RED phase:** 10 unit tests covering all behaviors — is_satisfied (3 tests) and execute (7 tests) — written first and confirmed failing with `ModuleNotFoundError`.

**GREEN phase:** Created `src/vidscope/pipeline/stages/metadata_extract.py` with:
- `name: str = StageName.METADATA_EXTRACT.value` — value `"metadata_extract"`
- `__init__(*, link_extractor: LinkExtractor)` — pure DI, no concrete adapter reference
- `is_satisfied(ctx, uow)` — returns `False` if `ctx.video_id is None`, else delegates to `uow.links.has_any_for_video(ctx.video_id)` (resume-safe, cheap DB query)
- `execute(ctx, uow)` — reads `video.description` + `transcript.full_text`, runs LinkExtractor on each source, builds `Link` domain entities, calls `uow.links.add_many_for_video(video_id, links)` (always called, even with empty list for idempotence), returns `StageResult` with count message
- Raises `IndexingError` when `ctx.video_id is None` (mirrors IndexStage pattern)

Exported from `src/vidscope/pipeline/stages/__init__.py` in alphabetical order within `__all__`.

### T02 — Container Wiring

Modified `src/vidscope/infrastructure/container.py`:
- Added `from vidscope.adapters.text import RegexLinkExtractor` (in alphabetical order among adapter imports)
- Added `MetadataExtractStage` to stages import block
- In `build_container()`: instantiates `link_extractor = RegexLinkExtractor()` and `metadata_extract_stage = MetadataExtractStage(link_extractor=link_extractor)` between `analyze_stage` and `index_stage`
- `PipelineRunner` stages list now has 6 entries in canonical order

Updated tests to reflect 6-stage reality:
- `test_container.py`: stage_names assertion updated from 5 to 6 stages
- `test_app.py`: `test_after_add_shows_runs_for_each_stage` updated to expect 6 pipeline_runs and includes `metadata_extract` in assertions

## Verification Results

```
python -m uv run pytest tests/unit/pipeline/test_metadata_extract_stage.py -x -q
→ 10 passed in 0.30s

python -m uv run pytest -q
→ 878 passed, 5 deselected in 23.97s

python -m uv run mypy src
→ Success: no issues found in 97 source files

python -m uv run lint-imports
→ Contracts: 10 kept, 0 broken

python -m uv run ruff check src tests
→ 1 pre-existing error in test_list_creator_videos.py (F401, out of scope)

python -m uv run python -c "from vidscope.infrastructure.container import build_container; c = build_container(); print(c.pipeline_runner.stage_names)"
→ ('ingest', 'transcribe', 'frames', 'analyze', 'metadata_extract', 'index')
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated CLI test expecting 5 pipeline_runs to expect 6**
- **Found during:** T02 full test suite run
- **Issue:** `test_after_add_shows_runs_for_each_stage` in `tests/unit/cli/test_app.py` asserted `"pipeline runs: 5"` — correct before M007/S03-P02, now broken because the 6th stage (metadata_extract) produces a new pipeline_run on each `vidscope add`
- **Fix:** Updated assertion to `"pipeline runs: 6"` and added `assert "metadata_extract" in status_result.stdout`
- **Files modified:** `tests/unit/cli/test_app.py`
- **Commit:** e148bed

**2. [Rule 3 - Blocking] Fixed ruff I001 import order in test file**
- **Found during:** T02 ruff check
- **Issue:** Import block in `test_metadata_extract_stage.py` had `from vidscope.ports.link_extractor import RawLink` which triggered I001 (import from sub-module when parent module re-exports)
- **Fix:** Changed to `from vidscope.ports import RawLink` and ran `ruff --fix` to resolve sort order
- **Files modified:** `tests/unit/pipeline/test_metadata_extract_stage.py`
- **Commit:** e148bed

## Deferred Issues

- **Pre-existing ruff F401** in `tests/unit/application/test_list_creator_videos.py` (line 8): `ListCreatorVideosResult` imported but unused. Not caused by this plan's changes — deferred.

## Known Stubs

None — MetadataExtractStage is fully wired and functional. Links extracted from real video descriptions/transcripts via `RegexLinkExtractor`.

## Threat Flags

No new security-relevant surface introduced. `MetadataExtractStage` is an internal pipeline stage with no new network endpoints, auth paths, or file access patterns. All threat model items T-S03P02-01 through T-S03P02-05 were pre-assessed in the plan; mitigations confirmed present (SQLAlchemy bindings via `uow.links`, linear regex, `is_satisfied` short-circuit on `has_any_for_video`).

## Self-Check: PASSED

- `src/vidscope/pipeline/stages/metadata_extract.py` — FOUND
- `tests/unit/pipeline/test_metadata_extract_stage.py` — FOUND
- Commit `6fdba6e` (RED) — FOUND
- Commit `9b2f027` (GREEN) — FOUND
- Commit `e148bed` (T02) — FOUND
- 878 tests passing — CONFIRMED
- mypy clean — CONFIRMED
- 10 import-linter contracts green — CONFIRMED
- Pipeline has 6 stages in canonical order — CONFIRMED
