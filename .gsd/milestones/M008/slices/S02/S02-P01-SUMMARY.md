---
phase: M008/S02
plan: P01
subsystem: pipeline-stages-container
tags: [ocr, vision, pipeline, visual-intelligence, metadata-extract, sqlite, integration]
dependency_graph:
  requires:
    - vidscope.ports.ocr_engine.OcrEngine (S01-P01)
    - vidscope.ports.repositories.FrameTextRepository (S01-P01)
    - vidscope.ports.unit_of_work.UnitOfWork.frame_texts (S01-P01)
    - vidscope.domain.entities.FrameText (S01-P01)
    - vidscope.domain.values.StageName.VISUAL_INTELLIGENCE (S01-P01)
    - vidscope.adapters.vision.RapidOcrEngine (S01-P01)
    - vidscope.adapters.sqlite.FrameTextRepositorySQLite (S01-P01)
  provides:
    - vidscope.pipeline.stages.VisualIntelligenceStage
    - MetadataExtractStage.is_satisfied ignores OCR-only links
    - 7-stage pipeline order: ingest, transcribe, frames, analyze, visual_intelligence, metadata_extract, index
  affects:
    - src/vidscope/pipeline/stages/__init__.py (new export)
    - src/vidscope/pipeline/stages/metadata_extract.py (is_satisfied logic)
    - src/vidscope/infrastructure/container.py (7th stage wired)
tech_stack:
  added: []
  patterns:
    - Stage protocol: is_satisfied + execute + name class attribute (mirrors MetadataExtractStage)
    - Graceful degradation via _unavailable sentinel on OcrEngine (no library = SKIPPED result)
    - Idempotent is_satisfied via uow.frame_texts.has_any_for_video
    - OCR links carry position_ms=frame.timestamp_ms (first-seen frame wins on dedup)
    - MetadataExtractStage.is_satisfied uses list_for_video(source=...) not has_any_for_video
key_files:
  created:
    - src/vidscope/pipeline/stages/visual_intelligence.py
    - tests/unit/pipeline/stages/test_visual_intelligence.py
    - tests/integration/pipeline/__init__.py
    - tests/integration/pipeline/test_visual_intelligence_stage.py
  modified:
    - src/vidscope/pipeline/stages/__init__.py (VisualIntelligenceStage export)
    - src/vidscope/pipeline/stages/metadata_extract.py (is_satisfied fix + docstring)
    - src/vidscope/infrastructure/container.py (RapidOcrEngine + VisualIntelligenceStage wired)
    - tests/unit/pipeline/test_metadata_extract_stage.py (5 new OCR-interaction tests)
    - tests/unit/infrastructure/test_container.py (7-stage tuple assertion)
    - tests/unit/cli/test_app.py (pipeline_runs 6->7)
decisions:
  - "D-M008-S02-01: _unavailable sentinel on OcrEngine used for graceful-degradation detection — avoids adding new error type; consistent with RapidOcrEngine.rapidocr_available flag from S01-P01"
  - "D-M008-S02-02: link deduplication by (normalized_url, source) in add_many_for_video means same URL across multiple frames produces one row with first-seen position_ms — documented as accepted design (T-M008-S02-06)"
  - "D-M008-S02-03: MetadataExtractStage.is_satisfied switched from has_any_for_video to list_for_video(source='description') + list_for_video(source='transcript') to exclude OCR-only links"
metrics:
  duration: ~8 minutes
  completed_at: "2026-04-18T13:46:47Z"
  tasks: 3
  files_created: 4
  files_modified: 6
  tests_added: 29
  total_tests: 1009
---

# Phase M008 Slice S02 Plan P01 Summary

**One-liner:** VisualIntelligenceStage — sixième stage du pipeline qui OCR chaque frame via OcrEngine, persiste les FrameText rows, route le texte vers RegexLinkExtractor pour produire des Link rows avec source='ocr' et position_ms=frame.timestamp_ms, câblé dans le container entre analyze et metadata_extract avec MetadataExtractStage.is_satisfied corrigé pour ignorer les liens OCR-only.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| T01 | VisualIntelligenceStage (TDD) | b72c969 | pipeline/stages/visual_intelligence.py, test_visual_intelligence.py |
| T02 | MetadataExtractStage.is_satisfied fix (TDD) | acb39fd | metadata_extract.py, test_metadata_extract_stage.py |
| T03 | Container wiring + integration tests | cebc706 | container.py, tests/integration/pipeline/ |
| fix | Ruff warnings in new files | 89a1408 | visual_intelligence.py, test files |

## Verification Results

```
uv run pytest tests/unit/pipeline/stages/test_visual_intelligence.py -q → 12 passed
uv run pytest tests/unit/pipeline/test_metadata_extract_stage.py -q → 15 passed
uv run pytest tests/integration/pipeline -m integration -q → 2 passed
uv run pytest -q → 1009 passed, 7 deselected
uv run mypy src → Success: no issues found in 105 source files
uv run lint-imports → Contracts: 11 kept, 0 broken
uv run python -c "...assert stage_names == ('ingest','transcribe','frames','analyze','visual_intelligence','metadata_extract','index')..." → ok
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_container.py stage_names tuple out of sync**
- **Found during:** T03 full suite run
- **Issue:** `TestBuildContainer.test_returns_a_container_with_every_field_populated` hardcoded 6-stage tuple without `visual_intelligence`; caused AssertionError after container wiring
- **Fix:** Updated expected tuple to 7-stage order including `visual_intelligence`
- **Files modified:** `tests/unit/infrastructure/test_container.py`
- **Commit:** cebc706

**2. [Rule 1 - Bug] test_app.py pipeline_runs count 6 → 7**
- **Found during:** T03 full suite run
- **Issue:** `TestStatus.test_after_add_shows_runs_for_each_stage` asserted `"pipeline runs: 6"` and `"metadata_extract"` (which is truncated to `"metadata_extra…"` in the CLI table). After adding the 7th stage the count was wrong and the exact string failed.
- **Fix:** Updated to `"pipeline runs: 7"`, added `"visual_intelli"` assertion, changed `"metadata_extract"` to `"metadata_extra"` (17-char CLI truncation)
- **Files modified:** `tests/unit/cli/test_app.py`
- **Commit:** cebc706

**3. [Rule 1 - Bug] TestIsSatisfied.test_links_exist_returns_true used old API**
- **Found during:** T02 GREEN phase
- **Issue:** After changing `is_satisfied` to use `list_for_video(source=...)`, the existing test still used `FakeUoW(links_has_any=True)` which never feeds `list_for_video`. The test failed on GREEN.
- **Fix:** Updated test to use `links_rows=[Link(..., source="description")]` via the extended `FakeLinkRepo`
- **Files modified:** `tests/unit/pipeline/test_metadata_extract_stage.py`
- **Commit:** acb39fd

**4. [Rule 1 - Bug] Ruff violations in new files**
- **Found during:** Post-T03 `ruff check` run
- **Issue:** `visual_intelligence.py`: unused `noqa: BLE001` directive. `test_visual_intelligence.py`: unused `StageResult` import, un-sorted imports, quoted return type annotation, E501 lines. `test_visual_intelligence_stage.py`: unused `VideoId` and `OcrEngine` imports.
- **Fix:** Removed unused imports/noqa, fixed import sort, unquoted return type, reformatted long lines
- **Files modified:** `visual_intelligence.py`, `test_visual_intelligence.py`, `test_visual_intelligence_stage.py`
- **Commit:** 89a1408

## Known Stubs

None — all new functionality is fully wired. VisualIntelligenceStage reads real frames from the DB, calls real OcrEngine port (backed by RapidOcrEngine with lazy model load), persists real FrameText and Link rows. The test stubs are test-only fakes, not production stubs.

## Threat Flags

None — all surfaces introduced by this plan were covered by the plan's threat model (T-M008-S02-01 through T-M008-S02-06).

## Self-Check: PASSED

Files verified:
- src/vidscope/pipeline/stages/visual_intelligence.py — FOUND
- src/vidscope/pipeline/stages/__init__.py (VisualIntelligenceStage) — FOUND
- src/vidscope/pipeline/stages/metadata_extract.py (source="description") — FOUND
- src/vidscope/infrastructure/container.py (RapidOcrEngine, VisualIntelligenceStage) — FOUND
- tests/unit/pipeline/stages/test_visual_intelligence.py — FOUND
- tests/integration/pipeline/__init__.py — FOUND
- tests/integration/pipeline/test_visual_intelligence_stage.py — FOUND

Commits verified:
- b72c969 T01 VisualIntelligenceStage — FOUND
- acb39fd T02 MetadataExtractStage fix — FOUND
- cebc706 T03 container + integration — FOUND
- 89a1408 fix ruff warnings — FOUND
