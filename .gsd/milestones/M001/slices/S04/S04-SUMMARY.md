---
id: S04
parent: M001
milestone: M001
provides:
  - FfmpegFrameExtractor implementing the FrameExtractor port
  - FramesStage implementing Stage protocol
  - Container.frame_extractor field + 3-stage pipeline runner
  - Frame rows in DB with canonical storage keys
  - Frame files on disk under MediaStorage
  - Pattern for any future external-binary adapter (shutil.which preflight, subprocess wrapper, typed errors, glob fallback)
requires:
  - slice: S03
    provides: TranscribeStage and the 2-stage pipeline. S04 appends a third stage.
affects:
  - S05 (analyze) — reads transcripts from S03, runs heuristic analyzer, doesn't touch frames directly
  - S06 (FTS5 + show) — vidscope show will display the frames list from this slice's output
key_files:
  - src/vidscope/adapters/ffmpeg/__init__.py
  - src/vidscope/adapters/ffmpeg/frame_extractor.py
  - src/vidscope/pipeline/stages/frames.py
  - src/vidscope/pipeline/stages/__init__.py
  - src/vidscope/infrastructure/container.py
  - tests/unit/adapters/ffmpeg/test_frame_extractor.py
  - tests/unit/pipeline/stages/test_frames.py
  - tests/unit/cli/test_app.py
  - tests/integration/test_ingest_live.py
  - scripts/verify-s04.sh
key_decisions:
  - ffmpeg shelled out from exactly one file (`adapters/ffmpeg/frame_extractor.py`). Same one-file-isolation pattern as yt_dlp and faster_whisper.
  - FfmpegFrameExtractor checks ffmpeg lazily at extract_frames time — container always builds even on machines without ffmpeg. The frames stage fails at runtime with a typed error and the runner marks it FAILED while keeping ingest+transcribe rows OK. R009 cross-platform install preserved.
  - Default 0.2 fps + 30-frame cap tuned for short-form vertical content per D026
  - Frames stored under MediaStorage at canonical keys videos/{platform}/{platform_id}/frames/{index:04d}.{ext} — same shape as media files for consistency
  - Integration test helper iterates outcomes individually instead of demanding result.success — lets the frames stage fail gracefully when ffmpeg is missing
  - ffmpeg installed via winget background job mid-slice; PATH manually prepended for the running session; system-wide PATH update is permanent for future sessions
patterns_established:
  - External binary adapter pattern: shutil.which preflight + subprocess.run with timeout + typed error translation + glob fallback for output discovery. Works for ffmpeg, will work for any future binary integration.
  - Conditional integration test assertions: skip blocks when an external dependency is unavailable (cookies for Instagram, ffmpeg for frames). The test suite remains meaningful across environments without sacrificing rigor where the deps exist.
observability_surfaces:
  - Pipeline now produces 3 pipeline_runs rows per video (ingest + transcribe + frames) visible in vidscope status
  - When ffmpeg is missing, the frames row is FAILED with the install instructions in the error column — grep-able diagnostic
drill_down_paths:
  - .gsd/milestones/M001/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S04/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001/slices/S04/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T15:52:20.400Z
blocker_discovered: false
---

# S04: Frame extraction brick (ffmpeg)

**Shipped frame extraction: FfmpegFrameExtractor + FramesStage + container wiring + ffmpeg installed via winget mid-slice. Pipeline now runs ingest → transcribe → frames in ~7s on real YouTube Shorts.**

## What Happened

S04 added the third pipeline stage in 4 tasks. ffmpeg was installed via winget in a background job during T01 so the live integration could exercise real frame extraction.

**T01**: FfmpegFrameExtractor with subprocess wrapper, shutil.which preflight, configurable fps (default 0.2 = 1 frame/5s), max_frames cap (default 30), JPEG quality 3, 60s subprocess timeout, typed errors for all 6 failure modes (missing binary, missing source, non-zero exit, timeout, OSError, no-frames-produced). 9 stubbed tests.

**T02**: FramesStage orchestrates FrameExtractor + MediaStorage + FrameRepository. Extracts frames into a sandboxed temp dir under cache, copies each into MediaStorage at the canonical key `videos/{platform}/{platform_id}/frames/{index:04d}.{ext}`, persists Frame entities via add_many. Cheap is_satisfied DB check for resume-from-failure. 9 stage tests.

**T03**: Container wiring. New Container.frame_extractor field, FfmpegFrameExtractor instantiated (lazy ffmpeg check at extract_frames time, NOT at construction — preserves R009 cross-platform install), FramesStage appended to runner stages list. CLI test fixture stub_pipeline grew a third sub-stub for ffmpeg subprocess. test_after_add expects 3 pipeline_runs.

**T04**: Integration test helper adapted to handle the 3-stage pipeline gracefully across two environments: with ffmpeg (full chain succeeds + frame assertions run) and without ffmpeg (frames stage marked FAILED but ingest+transcribe still validated). `_ffmpeg_available()` helper guards the frame assertions. Frame assertions verify rows + canonical keys + actual files on disk.

**ffmpeg installation**: dev machine had no ffmpeg. Installed `Gyan.FFmpeg 8.1` via `winget install` in a background async_bash job during T01 (~3 min download). The PATH didn't propagate to the running shell, so I prepended the bin dir manually for this session: `/c/Users/joaud/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1-full_build/bin`. System PATH update is permanent.

**Live results**: TikTok + YouTube full 3-stage pipeline in 10.31s. Each video produces ~6-12 frames (depends on duration). Instagram still xfailed for cookies.

**Pipeline state**: 3 stages (ingest, transcribe, frames). Each video produces 3 pipeline_runs rows + 1 video row + 1 transcript row + N frames rows. R001 (TikTok+YouTube), R002 (validated), R003 (validated) all advanced.

**Quality gates**: 300 unit + 3 architecture + 3 integration. Ruff/mypy strict/lint-imports all clean. ffmpeg subprocess is the only place ffmpeg is invoked across the entire codebase.

## Verification

Ran `python -m uv run pytest -q` → 300 passed, 3 deselected. Ran `python -m uv run pytest tests/integration -m 'integration and slow' -v` (with ffmpeg) → 2 passed, 1 xfailed in 10.31s. Ran `bash scripts/verify-s04.sh --skip-integration` → 7/7 green. ffmpeg, ruff, mypy, lint-imports all clean.

## Requirements Advanced

- R003 — Real frame extraction validated end-to-end on TikTok + YouTube. Frames persisted with canonical keys, files on disk.

## Requirements Validated

- R003 — Live integration tests on TikTok + YouTube produce real frame files in MediaStorage at videos/{platform}/{platform_id}/frames/{index:04d}.jpg, with corresponding rows in the frames table linked to the video.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

ffmpeg installed mid-slice via background winget job. PATH workaround for current session documented. No production code deviations.

## Known Limitations

Frame extraction strategy is fixed at 0.2 fps + 30-frame cap. No keyframe-aware extraction yet (all frames are sampled, none are flagged is_keyframe=True). Future enhancement: a second ffmpeg pass with `-vf select='eq(pict_type,I)'` to also extract keyframes.

## Follow-ups

Optionally add keyframe extraction as a second pass. Optionally add a `--max-frames` CLI flag.

## Files Created/Modified

- `src/vidscope/adapters/ffmpeg/frame_extractor.py` — New: FfmpegFrameExtractor with subprocess wrapper, shutil.which preflight, typed error translation, configurable fps + max_frames
- `src/vidscope/pipeline/stages/frames.py` — New: FramesStage orchestrating extractor + MediaStorage + FrameRepository, with cheap is_satisfied check
- `src/vidscope/infrastructure/container.py` — Wired frame_extractor + frames stage as the third stage in the runner
- `tests/unit/adapters/ffmpeg/test_frame_extractor.py` — New: 9 stubbed tests for FfmpegFrameExtractor
- `tests/unit/pipeline/stages/test_frames.py` — New: 9 tests for FramesStage with real adapters
- `tests/unit/cli/test_app.py` — stub_pipeline fixture extended to also stub ffmpeg subprocess
- `tests/integration/test_ingest_live.py` — Helper updated for 3-stage pipeline with conditional frame assertions
- `scripts/verify-s04.sh` — New verification script with ffmpeg-presence detection
