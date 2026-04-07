---
id: T04
parent: S05
milestone: M001
key_files:
  - src/vidscope/infrastructure/container.py
  - tests/unit/infrastructure/test_container.py
  - tests/unit/cli/test_app.py
  - tests/integration/test_ingest_live.py
  - scripts/verify-s05.sh
key_decisions:
  - Container picks the analyzer via build_analyzer(config.analyzer_name) — the default is 'heuristic' via VIDSCOPE_ANALYZER. Switching providers in M004 = changing the env var.
  - AnalyzeStage runs unconditionally (not gated by ffmpeg presence) — it only needs the transcript from the database, not the media file
duration: 
verification_result: passed
completed_at: 2026-04-07T16:00:40.508Z
blocker_discovered: false
---

# T04: Wired analyzer + analyze stage into the container as the 4th stage; pipeline now runs ingest → transcribe → frames → analyze; live integration confirms 4-stage chain on YouTube + TikTok in ~10s; verify-s05.sh ships.

**Wired analyzer + analyze stage into the container as the 4th stage; pipeline now runs ingest → transcribe → frames → analyze; live integration confirms 4-stage chain on YouTube + TikTok in ~10s; verify-s05.sh ships.**

## What Happened

Container extension: new `analyzer: Analyzer` field, instantiated via `build_analyzer(resolved_config.analyzer_name)` from the registry. AnalyzeStage constructed with the analyzer. PipelineRunner stages list now `[ingest, transcribe, frames, analyze]`.

Tests updated: container test asserts `stage_names == ('ingest', 'transcribe', 'frames', 'analyze')` and `analyzer.provider_name == 'heuristic'` (default). CLI test_after_add expects 4 pipeline_runs. Integration helper asserts `analyses` row exists with a provider name and score in [0, 100] (or None for stub).

Live result on dev machine with ffmpeg installed: TikTok + YouTube full 4-stage pipeline in 10.52s. Instagram xfailed (cookies). 331 unit tests + 3 architecture + 3 integration. Ruff/mypy/lint-imports all clean (8 ruff auto-fixes for unused imports + minor formatting in new test files).

## Verification

Ran `python -m uv run pytest -q` → 331 passed, 3 deselected. Ran `python -m uv run pytest tests/integration -m 'integration and slow' -v` (with ffmpeg) → 2 passed, 1 xfailed in 10.52s. Ran `bash scripts/verify-s05.sh --skip-integration` → 7/7 green. All quality gates clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/integration -m 'integration and slow' -v` | 0 | ✅ 4-stage pipeline live on TikTok + YouTube in 10.52s | 10520ms |
| 2 | `bash scripts/verify-s05.sh --skip-integration` | 0 | ✅ 7/7 fast-mode green | 25000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/infrastructure/container.py`
- `tests/unit/infrastructure/test_container.py`
- `tests/unit/cli/test_app.py`
- `tests/integration/test_ingest_live.py`
- `scripts/verify-s05.sh`
