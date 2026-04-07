---
id: T04
parent: S04
milestone: M001
key_files:
  - tests/integration/test_ingest_live.py
  - scripts/verify-s04.sh
key_decisions:
  - Integration test helper tolerates the frames stage failing when ffmpeg is missing — ingest+transcribe assertions still run. This means the test suite is meaningful on machines without ffmpeg installed.
  - Frame assertions run conditionally on _ffmpeg_available() — same pattern as cookies for Instagram
  - verify-s04.sh detects ffmpeg presence and adapts the summary message accordingly
duration: 
verification_result: passed
completed_at: 2026-04-07T15:51:06.680Z
blocker_discovered: false
---

# T04: Live integration tests now extract real frames via ffmpeg (installed via winget mid-slice) and verify_s04.sh ships — YouTube + TikTok run ingest+transcribe+frames in ~10s, frames stored under MediaStorage at canonical keys.

**Live integration tests now extract real frames via ffmpeg (installed via winget mid-slice) and verify_s04.sh ships — YouTube + TikTok run ingest+transcribe+frames in ~10s, frames stored under MediaStorage at canonical keys.**

## What Happened

T04 extended the integration test helper to handle the new 3-stage pipeline gracefully across two environments: with ffmpeg on PATH (full chain succeeds, frames assertions run) and without ffmpeg (frames stage marked FAILED but ingest+transcribe still validated). The helper iterates `result.outcomes`, lets the `frames` failure pass when `_ffmpeg_available()` returns False, and propagates any other failure as an IngestError.

Frame assertions run only when ffmpeg is available: at least one frame row exists, every frame's image_key starts with `videos/{platform}/`, the OK pipeline_runs row for the frames phase exists, and every frame's actual file exists on disk via `media_storage.resolve()`.

**ffmpeg installation mid-slice.** The dev machine had no ffmpeg at the start. I installed it via `winget install Gyan.FFmpeg` in a background async_bash job (~3 min download) and validated with `ffmpeg -version` before running the live tests. The PATH update from winget didn't propagate to the running shell session, so I prepended the bin dir explicitly: `/c/Users/joaud/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1-full_build/bin`. This is a one-time fix for this session — future shells will pick up the system-wide PATH update.

**Live results on dev machine with ffmpeg installed:**
- TestLiveYouTube: PASSED in 6.24s — full ingest + transcribe + frames extraction
- TestLiveTikTok: PASSED — full chain
- TestLiveInstagram: XFAIL (cookies needed per S07/R025)

**verify-s04.sh** detects ffmpeg presence at startup and prints the appropriate header line. The summary message adapts: "frames stage tolerated as failed because ffmpeg is missing" vs "frames extracted via ffmpeg". Fast mode 7/7 verified.

Quality gates clean: 300 unit + 3 architecture tests + 3 integration (2 passing + 1 xfail). Pipeline is now 3 stages.

## Verification

Ran `python -m uv run pytest tests/integration -m "integration and slow" -v` (with PATH including ffmpeg) → 2 passed, 1 xfailed in 10.31s. YouTube and TikTok both produced ingest + transcript + frames. Ran `python -m uv run pytest -q` → 300 passed, 3 deselected. Ran `bash scripts/verify-s04.sh --skip-integration` → 7/7 green. All 4 quality gates clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/integration -m 'integration and slow' -v (with ffmpeg on PATH)` | 0 | ✅ 2 passed (TikTok + YouTube full 3-stage pipeline), 1 xfailed (Instagram) | 10310ms |
| 2 | `bash scripts/verify-s04.sh --skip-integration` | 0 | ✅ 7/7 fast-mode green | 25000ms |

## Deviations

ffmpeg installed mid-slice via winget background job. PATH manually prepended in this session. The install is system-wide so future sessions don't need the workaround. Documented in the slice closure for future reference.

## Known Issues

Frame extraction takes ~1s per video on this dev machine for short-form content. Acceptable for the use case.

## Files Created/Modified

- `tests/integration/test_ingest_live.py`
- `scripts/verify-s04.sh`
