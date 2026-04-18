---
phase: M008/S01
plan: P01
subsystem: domain-ports-adapters-vision-schema
tags: [ocr, vision, sqlite, fts5, ports, domain, import-linter]
dependency_graph:
  requires: []
  provides:
    - vidscope.domain.entities.FrameText
    - vidscope.domain.values.ContentShape
    - vidscope.domain.values.StageName.VISUAL_INTELLIGENCE
    - vidscope.ports.ocr_engine.OcrEngine
    - vidscope.ports.ocr_engine.FaceCounter
    - vidscope.ports.ocr_engine.OcrLine
    - vidscope.ports.repositories.FrameTextRepository
    - vidscope.adapters.vision.RapidOcrEngine
    - vidscope.adapters.vision.HaarcascadeFaceCounter
    - vidscope.adapters.sqlite.FrameTextRepositorySQLite
    - frame_texts SQLite table + frame_texts_fts FTS5 virtual table
    - vidscope doctor vision row
  affects:
    - vidscope.ports.unit_of_work.UnitOfWork (new frame_texts attribute)
    - vidscope.adapters.sqlite.unit_of_work.SqliteUnitOfWork (wired)
    - vidscope.adapters.sqlite.schema (extended with M008 columns + table)
    - .importlinter (11 contracts, was 10)
    - pyproject.toml (new [vision] optional dep + uv override)
tech_stack:
  added:
    - rapidocr-onnxruntime>=1.4.4,<2 (optional, [vision] extra)
    - opencv-python-headless>=4.8,<5 (optional, [vision] extra)
  patterns:
    - Lazy model load (RapidOcrEngine._get_engine() pattern mirrors FasterWhisperTranscriber)
    - FTS5 manual sync (frame_texts_fts pattern mirrors search_index)
    - _ensure_* idempotent ALTER TABLE helpers (mirrors M006/M007 pattern)
    - Protocol + runtime_checkable (mirrors OcrEngine, FaceCounter, FrameTextRepository)
key_files:
  created:
    - src/vidscope/ports/ocr_engine.py
    - src/vidscope/adapters/vision/__init__.py
    - src/vidscope/adapters/vision/rapidocr_engine.py
    - src/vidscope/adapters/vision/haarcascade_face_counter.py
    - src/vidscope/adapters/sqlite/frame_text_repository.py
    - tests/unit/ports/__init__.py
    - tests/unit/ports/test_ocr_engine.py
    - tests/unit/adapters/vision/__init__.py
    - tests/unit/adapters/vision/test_rapidocr_engine.py
    - tests/unit/adapters/vision/test_face_counter.py
    - tests/unit/adapters/sqlite/test_frame_text_repository.py
    - tests/fixtures/vision/__init__.py
    - tests/fixtures/vision/generate_fixtures.py
  modified:
    - src/vidscope/domain/values.py (ContentShape + StageName.VISUAL_INTELLIGENCE)
    - src/vidscope/domain/entities.py (FrameText dataclass)
    - src/vidscope/domain/__init__.py (re-exports)
    - src/vidscope/ports/repositories.py (FrameTextRepository Protocol)
    - src/vidscope/ports/unit_of_work.py (frame_texts attribute)
    - src/vidscope/ports/__init__.py (new exports)
    - src/vidscope/adapters/sqlite/schema.py (frame_texts table + FTS5 + visual columns)
    - src/vidscope/adapters/sqlite/unit_of_work.py (frame_texts wired in __enter__)
    - src/vidscope/infrastructure/startup.py (check_vision + run_all_checks)
    - pyproject.toml ([vision] optional dep + [tool.uv] override)
    - .importlinter (vision-adapter-is-self-contained + updated existing contracts)
    - tests/unit/domain/test_entities.py (TestFrameText)
    - tests/unit/domain/test_values.py (TestContentShape + TestStageName update)
    - tests/unit/adapters/sqlite/test_schema.py (TestM008Schema)
    - tests/unit/infrastructure/test_startup.py (TestCheckVision + count update)
    - tests/architecture/test_layering.py (updated EXPECTED_CONTRACTS)
decisions:
  - "D-M008-S01-01: vision adapter uses lazy model load (same pattern as FasterWhisperTranscriber) to avoid 50MB ONNX download at import time"
  - "D-M008-S01-02: frame_texts_fts FTS5 sync is manual (no triggers) — consistent with SearchIndexSQLite approach; FTS5 orphans on DELETE are accepted (documented T-M008-S01-06)"
  - "D-M008-S01-03: FrameText.video_id denormalised on frame_texts row so FTS5 can filter by video without JOIN"
metrics:
  duration: ~45 minutes
  completed_at: "2026-04-18T13:34:00Z"
  tasks: 5
  files_created: 13
  files_modified: 16
  tests_added: 57
  total_tests: 992
---

# Phase M008 Slice S01 Plan P01 Summary

**One-liner:** Poser les fondations M008 — FrameText entity + ContentShape + StageName.VISUAL_INTELLIGENCE, ports OcrEngine/FaceCounter/FrameTextRepository, adapters vision lazy-load (RapidOCR + OpenCV haarcascade), schéma SQLite frame_texts + FTS5 frame_texts_fts, FrameTextRepositorySQLite avec sync FTS5, doctor check vision, et contrat import-linter vision-adapter-is-self-contained.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| T01 | Domain extensions | 8358fd4 | values.py, entities.py, domain/__init__.py |
| T02 | Ports OCR + FrameTextRepository | 371d836 | ports/ocr_engine.py, repositories.py, unit_of_work.py |
| T03 | Vision adapters + import-linter | 9e979a6 | adapters/vision/*.py, .importlinter |
| T04 | SQLite schema + FrameTextRepositorySQLite | 4700323 | schema.py, frame_text_repository.py, uow.py |
| T05 | pyproject + doctor + fixtures | 0c91010 | startup.py, pyproject.toml, fixtures/vision/ |

## Verification Results

```
uv run pytest -q → 992 passed, 5 deselected
uv run mypy src → Success: no issues found in 104 source files
uv run lint-imports → Contracts: 11 kept, 0 broken
uv run vidscope doctor → vision row: ok / not installed (optional)
Schema idempotence → ok (init_db called twice → no error)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FrameRepositorySQLite API mismatch in T04 test**
- **Found during:** T04 tests (RED phase)
- **Issue:** Test used `repo.add(frame)` but `FrameRepositorySQLite` exposes `add_many(frames)` not `add(frame)`
- **Fix:** Changed `_make_frame` helper to use `repo.add_many([frame])[0]`
- **Files modified:** `tests/unit/adapters/sqlite/test_frame_text_repository.py`
- **Commit:** 4700323 (included in T04 commit)

**2. [Rule 2 - Missing critical functionality] mypy overrides for optional vision deps**
- **Found during:** T03 mypy check
- **Issue:** mypy complained about missing stubs for `cv2` and `rapidocr_onnxruntime` (not installed in dev env)
- **Fix:** Added `[[tool.mypy.overrides]]` section in pyproject.toml for both modules with `ignore_missing_imports = true`
- **Files modified:** `pyproject.toml`
- **Commit:** 9e979a6

**3. [Rule 1 - Bug] Architecture test EXPECTED_CONTRACTS out of sync**
- **Found during:** Full suite run after T05
- **Issue:** `test_layering.py` checked old contract names; renaming sqlite/fs contracts and adding vision contract caused 1 failure
- **Fix:** Updated `EXPECTED_CONTRACTS` tuple to match new names (11 contracts)
- **Files modified:** `tests/architecture/test_layering.py`
- **Commit:** 01d9868

**4. [Rule 1 - Bug] test_startup.py run_all_checks count was 5, now 6**
- **Found during:** T05 regression check
- **Issue:** Existing test `test_returns_one_result_per_check` hardcoded `len(results) == 5` and the expected names set
- **Fix:** Updated to 6 and added "vision" to the expected names set
- **Files modified:** `tests/unit/infrastructure/test_startup.py`
- **Commit:** 0c91010

## Known Stubs

None — all new functionality is fully wired. The vision optional deps (rapidocr, opencv) are intentionally not installed; their absence is gracefully handled by lazy load returning [] / 0.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: FTS5-orphan | src/vidscope/adapters/sqlite/frame_text_repository.py | frame_texts_fts rows not deleted when parent frame/video deleted (accepted — documented as T-M008-S01-06, consistent with SearchIndexSQLite) |

## Self-Check: PASSED

Files verified:
- src/vidscope/ports/ocr_engine.py — FOUND
- src/vidscope/adapters/vision/__init__.py — FOUND
- src/vidscope/adapters/vision/rapidocr_engine.py — FOUND
- src/vidscope/adapters/vision/haarcascade_face_counter.py — FOUND
- src/vidscope/adapters/sqlite/frame_text_repository.py — FOUND
- tests/fixtures/vision/__init__.py — FOUND
- tests/fixtures/vision/generate_fixtures.py — FOUND

Commits verified:
- 8358fd4 T01 domain — FOUND
- 371d836 T02 ports — FOUND
- 9e979a6 T03 vision adapters — FOUND
- 4700323 T04 schema + repository — FOUND
- 0c91010 T05 pyproject + doctor — FOUND
- 01d9868 fix architecture test — FOUND
