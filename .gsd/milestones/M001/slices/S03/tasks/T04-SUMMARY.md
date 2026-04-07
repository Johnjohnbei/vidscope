---
id: T04
parent: S03
milestone: M001
key_files:
  - src/vidscope/infrastructure/container.py
  - tests/unit/infrastructure/test_container.py
  - tests/unit/cli/test_app.py
key_decisions:
  - Stage order locked in: ingest → transcribe. Container test asserts stage_names tuple order.
  - CLI test fixture renamed `stub_ytdlp` → `stub_pipeline` to reflect that it now stubs both external adapters. Pattern will extend to S04 (ffmpeg) and S05 (analyzer).
  - FasterWhisperTranscriber model loading remains lazy — build_container() does not download anything
duration: 
verification_result: passed
completed_at: 2026-04-07T15:34:54.433Z
blocker_discovered: false
---

# T04: Wired FasterWhisperTranscriber + TranscribeStage into the container; pipeline now chains ingest → transcribe; updated CLI test fixture to stub WhisperModel; 284 tests green.

**Wired FasterWhisperTranscriber + TranscribeStage into the container; pipeline now chains ingest → transcribe; updated CLI test fixture to stub WhisperModel; 284 tests green.**

## What Happened

Container extension is purely additive: new `transcriber: Transcriber` field on Container, instantiated as `FasterWhisperTranscriber(model_name=resolved_config.whisper_model, models_dir=resolved_config.models_dir)`. The TranscribeStage is constructed with the transcriber + media_storage and appended to the PipelineRunner stages list right after IngestStage. Stage execution order is now `ingest → transcribe`. The container test asserts `stage_names == ('ingest', 'transcribe')` so the order is locked in.

Updated `tests/unit/cli/test_app.py`: renamed the `stub_ytdlp` fixture to `stub_pipeline` and extended it to also stub `faster_whisper.WhisperModel` with a fake that returns one stub segment. Without this, the CLI add tests would trigger a real ~150MB model download from HuggingFace Hub. Updated the `test_after_add_shows_one_run` test to expect 2 pipeline_runs instead of 1 (ingest + transcribe), and to assert `transcribe` appears in the status output.

Quality gates clean: 284 tests pass, ruff/mypy/lint-imports all green, 7 import-linter contracts still kept.

## Verification

Ran `python -m uv run pytest tests/unit/cli -q` → 11 passed. Ran full suite `pytest -q` → 284 passed, 3 deselected. Ruff/mypy/lint-imports clean. Container.pipeline_runner.stage_names is now `('ingest', 'transcribe')`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest -q` | 0 | ✅ pass (284 tests, 3 deselected) | 2200ms |
| 2 | `ruff + mypy + lint-imports` | 0 | ✅ all clean | 4000ms |

## Deviations

Renamed the CLI test fixture from `stub_ytdlp` to `stub_pipeline` to reflect that it now stubs both yt_dlp AND faster_whisper. This is a test-only rename, no production code affected. Two test references updated automatically via sed.

## Known Issues

None. The pipeline now has two real stages chained together, both stubbed cleanly in unit tests.

## Files Created/Modified

- `src/vidscope/infrastructure/container.py`
- `tests/unit/infrastructure/test_container.py`
- `tests/unit/cli/test_app.py`
