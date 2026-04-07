---
id: T03
parent: S03
milestone: M001
key_files:
  - src/vidscope/pipeline/stages/transcribe.py
  - src/vidscope/pipeline/stages/__init__.py
  - tests/unit/pipeline/stages/test_transcribe.py
key_decisions:
  - TranscribeStage.is_satisfied is a cheap DB query — unlike IngestStage which has no cheap check (D025), transcripts CAN be checked for existence in O(1)
  - Transcript returned by Transcriber port has VideoId(0) placeholder — the stage replaces it with the real id before persisting, decoupling the adapter from the persistence id
  - Missing video_id or media_key in ctx raises TranscriptionError — the upstream stage failed silently and the runner should record this as a stage failure
duration: 
verification_result: passed
completed_at: 2026-04-07T15:32:31.815Z
blocker_discovered: false
---

# T03: Shipped TranscribeStage: orchestrates Transcriber + MediaStorage + TranscriptRepository, is_satisfied checks DB cheaply for resume-from-failure, propagates typed errors — 9 stage tests, 284 total green.

**Shipped TranscribeStage: orchestrates Transcriber + MediaStorage + TranscriptRepository, is_satisfied checks DB cheaply for resume-from-failure, propagates typed errors — 9 stage tests, 284 total green.**

## What Happened

TranscribeStage is the second concrete stage and the first one with a real `is_satisfied` implementation. Unlike `IngestStage` (D025: always returns False because the only way to know if the video is already ingested is to do the ingest), `TranscribeStage.is_satisfied()` is one cheap DB query: `uow.transcripts.get_for_video(ctx.video_id) is not None`. This means re-running `vidscope add <url>` after a successful first run will skip transcription entirely (the runner writes a SKIPPED pipeline_runs row) — exactly the resume-from-failure behavior R007 requires.

Execute flow: validate ctx.video_id and ctx.media_key (raise TranscriptionError if missing — that means the ingest stage didn't run or failed silently), resolve the media key through MediaStorage, verify the file exists on disk, call transcriber.transcribe(media_path), build a Transcript with the real video_id replacing the transcriber's VideoId(0) placeholder, persist via uow.transcripts.add, mutate ctx.transcript_id and ctx.language. Returns a StageResult with the message `"transcribed {language}: {N} segments, {M} chars"`.

Tests use a real SqliteUnitOfWork + real LocalMediaStorage + a fake `FakeTranscriber` dataclass that returns a configurable Transcript or raises a configurable error. Coverage: happy path with French content (FRENCH language, 2 segments, persisted with ctx mutated), is_satisfied false on no transcript, is_satisfied true after first run, is_satisfied false when video_id missing, missing video_id raises, missing media_key raises, missing media file on disk raises, transcriber failure propagates, stage name matches enum.

Quality gates clean after T03.

## Verification

Ran `python -m uv run pytest tests/unit/pipeline/stages -q` → 18 passed (9 ingest + 9 transcribe). Full suite 284 passed. Ruff/mypy/lint-imports all clean (one ruff RUF043 fix for raw-string match pattern, one auto-fix for import sorting).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/pipeline/stages -q` | 0 | ✅ pass (18/18) | 440ms |
| 2 | `python -m uv run pytest -q && python -m uv run ruff check src tests && python -m uv run mypy src` | 0 | ✅ all gates clean (284 tests, 55 files) | 5000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/pipeline/stages/transcribe.py`
- `src/vidscope/pipeline/stages/__init__.py`
- `tests/unit/pipeline/stages/test_transcribe.py`
