---
id: T01
parent: S04
milestone: M001
key_files:
  - src/vidscope/adapters/ffmpeg/__init__.py
  - src/vidscope/adapters/ffmpeg/frame_extractor.py
  - tests/unit/adapters/ffmpeg/test_frame_extractor.py
key_decisions:
  - ffmpeg shelled out from exactly one file via subprocess.run
  - Default 0.2 fps + 30-frame cap tuned for short-form vertical content per D026
  - JPEG quality 3 (high) — small files (<100KB typical) with good detail for visual analysis
  - shutil.which preflight before subprocess invocation — fail fast with install instructions instead of subprocess OSError
  - image_key returned from extractor is the local path; the stage rekeys to MediaStorage layout
duration: 
verification_result: passed
completed_at: 2026-04-07T15:44:30.553Z
blocker_discovered: false
---

# T01: Shipped FfmpegFrameExtractor: subprocess wrapper with shutil.which preflight, configurable fps, max_frames cap, typed errors for all 6 failure modes — 9 stubbed unit tests, ffmpeg subprocess never invoked.

**Shipped FfmpegFrameExtractor: subprocess wrapper with shutil.which preflight, configurable fps, max_frames cap, typed errors for all 6 failure modes — 9 stubbed unit tests, ffmpeg subprocess never invoked.**

## What Happened

FfmpegFrameExtractor follows the one-file-isolation pattern: ffmpeg is shelled out from exactly one place. Default strategy: 0.2 fps (one frame every 5 seconds), capped at 30 frames per video, JPEG quality 3. The math works out for short-form content: a 30-second Reel produces ~6 frames, a 60-second Short ~12, a 90-second Reel ~18 — all well under the cap.

`extract_frames(media_path, output_dir, max_frames=30)` flow: shutil.which preflight (raise FrameExtractionError with install instructions if ffmpeg missing), verify source exists, ensure output_dir exists, build the ffmpeg command with `-vf fps={fps}`, `-vframes {max_frames}`, `-q:v 3`, and the output template `frame_%04d.jpg`, run subprocess with 60s timeout. On non-zero exit, raise FrameExtractionError with the stderr tail (last 500 chars). On timeout, raise typed error with the configured timeout. On OSError, same. Glob the output dir for frames, sort lexicographically (%04d guarantees temporal order), cap at max_frames, build Frame entities with `timestamp_ms = index * (1000/fps)` and `image_key = local_path` (placeholder — the stage will copy + rekey).

**Tests** stub `shutil.which` and `subprocess.run` via monkeypatch. A `_FakeCompleted` class plays subprocess.CompletedProcess (with explicit `__init__` instead of class-level attributes that broke the first attempt with NameError on the closure). 9 tests cover: happy path with default fps, max_frames cap, custom fps changes timestamp interval, missing binary, missing media file, non-zero exit, timeout, OSError, ffmpeg-succeeded-but-no-frames-produced.

ffmpeg binary is never invoked in unit tests.

## Verification

Ran `python -m uv run pytest tests/unit/adapters/ffmpeg -q` → 9 passed in 70ms.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters/ffmpeg -q` | 0 | ✅ pass (9/9) | 70ms |

## Deviations

First attempt at the test fixture used a closure-captured `FakeCompleted` class with class-level attributes referencing the outer-function parameter `stderr`. Python class bodies don't see enclosing function scope for class-level attribute assignments — got NameError. Refactored to a module-level `_FakeCompleted` class with explicit `__init__`, which is cleaner anyway.

## Known Issues

None for unit tests. Real ffmpeg invocation tested in T04.

## Files Created/Modified

- `src/vidscope/adapters/ffmpeg/__init__.py`
- `src/vidscope/adapters/ffmpeg/frame_extractor.py`
- `tests/unit/adapters/ffmpeg/test_frame_extractor.py`
