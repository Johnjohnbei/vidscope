---
id: T03
parent: S04
milestone: M001
key_files:
  - src/vidscope/infrastructure/container.py
  - tests/unit/infrastructure/test_container.py
  - tests/unit/cli/test_app.py
key_decisions:
  - FfmpegFrameExtractor checks for ffmpeg lazily at extract_frames time, NOT at construction. Container always builds; only the FramesStage fails at runtime if ffmpeg is missing. Preserves R009 cross-platform install.
  - stub_pipeline fixture grew to 3 sub-stubs (yt_dlp, faster_whisper, ffmpeg) — the pattern scales as we add stages
duration: 
verification_result: passed
completed_at: 2026-04-07T15:48:22.716Z
blocker_discovered: false
---

# T03: Wired FfmpegFrameExtractor + FramesStage into the container as the third stage; CLI fixture extended to stub ffmpeg subprocess; pipeline now runs ingest → transcribe → frames; 300 tests green.

**Wired FfmpegFrameExtractor + FramesStage into the container as the third stage; CLI fixture extended to stub ffmpeg subprocess; pipeline now runs ingest → transcribe → frames; 300 tests green.**

## What Happened

Container extension: added `frame_extractor: FrameExtractor` field, instantiated `FfmpegFrameExtractor()` (no init validation — ffmpeg presence is checked at extract_frames time so the container builds even on machines without ffmpeg, the FramesStage will fail at runtime with a typed error and the runner will mark it FAILED while keeping ingest+transcribe OK). Added `FramesStage(frame_extractor, media_storage, cache_dir=resolved_config.cache_dir)` to the pipeline runner stages list. Pipeline order: ingest → transcribe → frames.

CLI test fixture extended: `stub_pipeline` now also patches `vidscope.adapters.ffmpeg.frame_extractor` shutil.which and subprocess.run with fakes that create 3 dummy .jpg files in the output template's directory. test_after_add updated to expect 3 pipeline_runs instead of 2.

300 unit tests + 3 architecture pass, ruff/mypy/lint-imports all clean.

## Verification

Ran `python -m uv run pytest -q` → 300 passed, 3 deselected in 2.47s. Ruff/mypy/lint-imports clean (2 ruff auto-fixes). container.frame_extractor is wired and pipeline_runner.stage_names is ('ingest', 'transcribe', 'frames').

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest -q` | 0 | ✅ pass (300 tests, 3 deselected) | 2470ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/infrastructure/container.py`
- `tests/unit/infrastructure/test_container.py`
- `tests/unit/cli/test_app.py`
