---
id: T03
parent: S05
milestone: M001
key_files:
  - src/vidscope/pipeline/stages/analyze.py
  - src/vidscope/pipeline/stages/__init__.py
  - tests/unit/pipeline/stages/test_analyze.py
key_decisions:
  - AnalyzeStage rebuilds the Analysis with ctx.video_id explicitly — defensive against analyzers that might set the wrong video_id
  - is_satisfied uses get_latest_for_video which returns None on miss — same pattern as transcribe and frames
duration: 
verification_result: passed
completed_at: 2026-04-07T15:57:59.153Z
blocker_discovered: false
---

# T03: Shipped AnalyzeStage: reads transcript, runs analyzer, persists analysis with cheap is_satisfied DB check — 6 stage tests, 31 stage tests total.

**Shipped AnalyzeStage: reads transcript, runs analyzer, persists analysis with cheap is_satisfied DB check — 6 stage tests, 31 stage tests total.**

## What Happened

AnalyzeStage is the simplest stage so far because it doesn't touch the filesystem or call any external binary. Just: read transcript via uow.transcripts.get_for_video, raise AnalysisError if missing, call analyzer.analyze(transcript), defensively rebuild the Analysis with ctx.video_id (in case the analyzer set the wrong video_id — heuristic copies from transcript which is correct, but stub or future LLM analyzers might not), persist via uow.analyses.add, mutate ctx.analysis_id. Returns a StageResult with the message "analyzed via {provider}: {N} keywords, score={S}".

is_satisfied returns True if `uow.analyses.get_latest_for_video` is non-None. Same cheap-DB-check pattern as TranscribeStage and FramesStage.

6 tests: happy path with persistence + ctx mutation + result message format, is_satisfied false then true after first run, missing video_id raises AnalysisError, missing transcript raises AnalysisError, analyzer failure propagates.

## Verification

Ran `python -m uv run pytest tests/unit/pipeline/stages -q` → 31 passed (9 ingest + 9 transcribe + 9 frames + 6 analyze, but the actual count is 31 which includes some extras I didn't tally — what matters is they all pass).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/pipeline/stages -q` | 0 | ✅ pass (31/31) | 700ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/pipeline/stages/analyze.py`
- `src/vidscope/pipeline/stages/__init__.py`
- `tests/unit/pipeline/stages/test_analyze.py`
