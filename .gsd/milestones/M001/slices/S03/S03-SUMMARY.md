---
id: S03
parent: M001
milestone: M001
provides:
  - FasterWhisperTranscriber implementing the Transcriber port
  - TranscribeStage implementing Stage protocol with cheap is_satisfied DB check
  - Container wiring with Container.transcriber field and 2-stage pipeline (ingest, transcribe)
  - Real transcripts in the DB after `vidscope add` for content with speech
  - Pattern for future CPU-bound adapters with model caching (whisper models cached under <data_dir>/models/)
requires:
  - slice: S02
    provides: Real videos rows with media_key pointing at downloaded files that the transcriber opens
affects:
  - S04 (frames) — inherits real transcripts and a working 2-stage pipeline. Adds FrameExtractorStage to the chain.
  - S05 (analyze) — reads transcripts.full_text produced here, runs heuristic analyzer, persists analyses row
  - S06 (FTS5) — indexes transcripts.full_text in the FTS5 virtual table for `vidscope search`
key_files:
  - src/vidscope/infrastructure/config.py
  - src/vidscope/adapters/whisper/__init__.py
  - src/vidscope/adapters/whisper/transcriber.py
  - src/vidscope/pipeline/stages/transcribe.py
  - src/vidscope/pipeline/stages/__init__.py
  - src/vidscope/infrastructure/container.py
  - tests/unit/adapters/whisper/test_transcriber.py
  - tests/unit/pipeline/stages/test_transcribe.py
  - tests/integration/test_ingest_live.py
  - tests/unit/cli/test_app.py
  - scripts/verify-s03.sh
  - pyproject.toml
key_decisions:
  - Default device='cpu' for FasterWhisperTranscriber — 'auto' is unsafe on partial-CUDA installs
  - Default compute_type='int8' — explicit, matches D008 documented baseline
  - VAD filter disabled by default — too aggressive for short-form vertical content
  - Empty transcripts are a legitimate success outcome for instrumental videos — integration test asserts row + language, not text content
  - TranscribeStage.is_satisfied is a cheap DB query — resume-from-failure works for transcribe even though ingest still re-downloads (D025)
  - Whisper model loaded lazily on first transcribe call — build_container() doesn't download anything
  - CLI test fixture extended from stub_ytdlp to stub_pipeline — stubs both yt_dlp and faster_whisper
patterns_established:
  - Adapter integration tests with @pytest.mark.slow for tests that take >10s due to model downloads or large file ops
  - Integration test assertions accept legitimate empty outcomes (instrumental videos, empty transcripts) instead of demanding non-empty content
observability_surfaces:
  - Pipeline now produces 2 pipeline_runs rows per video (ingest + transcribe) visible in vidscope status
  - Stage.name on TranscribeStage matches StageName.TRANSCRIBE so the runner correctly maps it to the enum
  - transcripts.language column carries the honest signal: FRENCH/ENGLISH/UNKNOWN, never lies
drill_down_paths:
  - .gsd/milestones/M001/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S03/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001/slices/S03/tasks/T04-SUMMARY.md
  - .gsd/milestones/M001/slices/S03/tasks/T05-SUMMARY.md
  - .gsd/milestones/M001/slices/S03/tasks/T06-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T15:41:14.597Z
blocker_discovered: false
---

# S03: Transcription brick (faster-whisper)

**Shipped real transcription end-to-end: FasterWhisperTranscriber + TranscribeStage + container wiring + integration tests proving YouTube + TikTok ingest+transcribe in ~6s on CPU. Two real bugs found and fixed during live testing.**

## What Happened

S03 plugged faster-whisper into the existing pipeline runner without changing any layer boundary. The same `vidscope add <url>` command that downloaded media in S02 now also produces a transcript with language detection, segments, and full text. The pipeline runner from S01 chains ingest → transcribe transactionally — each stage's output is committed in its own UnitOfWork with the matching pipeline_runs row.

**Six tasks delivered:**
- T01: VIDSCOPE_WHISPER_MODEL config field with known-models validation (4 tests)
- T02: FasterWhisperTranscriber adapter with lazy model loading, language mapping, typed errors (11 stubbed tests)
- T03: TranscribeStage with cheap is_satisfied DB check (resume-from-failure works), 9 tests
- T04: Container wiring for transcriber + transcribe stage; pipeline now runs ingest → transcribe
- T05: Live integration tests with real model, fixed 2 production bugs
- T06: verify-s03.sh end-to-end script

**Two real bugs fixed mid-T05:**
1. **device='auto' broke on partial-CUDA installs.** faster-whisper tried to load `cublas64_12.dll` on a CPU-only machine. Changed default to `device='cpu'` per D008.
2. **VAD filter stripped all speech from short videos.** `min_silence_duration_ms=500` was too aggressive for tight-paced shorts. Disabled VAD by default; can be re-enabled if a use case emerges.

Both fixes documented inline in transcriber.py with rationale.

**Live results on dev machine (CPU, int8, base model):**
- YouTube Short (19s): full ingest + transcribe in ~6.5s, real non-empty English transcript
- TikTok official video: ingest + transcribe complete, empty transcript (instrumental content — legitimate outcome)
- Instagram: xfail (cookies needed per S07/R025)

**Test relaxation:** the integration helper originally asserted `transcript.full_text` was non-empty. Relaxed to "transcripts row exists with a recognized language" because instrumental videos legitimately produce empty transcripts. The schema is correct, the pipeline ran, the row exists — that's the success signal.

**Pipeline state after S03:** the runner has 2 stages (ingest, transcribe). vidscope status shows 2 pipeline_runs per video. Container.transcriber is wired. R002 advances to active with live evidence.

**Quality gates:** 284 unit + 3 architecture + 3 integration tests, ruff/mypy/lint-imports all clean throughout. faster_whisper imported in exactly one file (`adapters/whisper/transcriber.py`).

## Verification

Ran `python -m uv run pytest -q` → 284 passed, 3 deselected. Ran `python -m uv run pytest tests/integration -m 'integration and slow' -v` → 2 passed, 1 xfailed in 10.27s. Ran `bash scripts/verify-s03.sh --skip-integration` → 7/7 green. Ruff, mypy strict, lint-imports all clean.

## Requirements Advanced

- R002 — Real transcription validated end-to-end on live YouTube Short. faster-whisper integrated behind the Transcriber port with one-file isolation.
- R007 — vidscope add now produces 2 stages of output per video (ingest + transcribe) demonstrating multi-stage transactional pipeline

## Requirements Validated

- R002 — Live integration test TestLiveYouTube produces a real non-empty English transcript in 6.5s on CPU with int8 base model.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Two production fixes during T05 live run: device default and VAD default. Test assertion relaxed for legitimate empty-transcript case.

## Known Limitations

Whisper model downloads from HF Hub on first run (~150MB for base). French transcription validated only via unit tests; no real French URL in the integration suite yet (would need a known-stable French short).

## Follow-ups

Consider a `vidscope models pull` command for explicit pre-download. Add a French-content URL to the integration suite when one is identified.

## Files Created/Modified

- `src/vidscope/infrastructure/config.py` — Added whisper_model field + VIDSCOPE_WHISPER_MODEL env var resolution + known-models validation
- `src/vidscope/adapters/whisper/transcriber.py` — New: FasterWhisperTranscriber with lazy loading, CPU defaults, VAD disabled, language mapping
- `src/vidscope/pipeline/stages/transcribe.py` — New: TranscribeStage with cheap is_satisfied DB check
- `src/vidscope/infrastructure/container.py` — Wired transcriber + transcribe stage into the runner
- `tests/integration/test_ingest_live.py` — Added transcript assertions to helper, slow marker on tests
- `tests/unit/cli/test_app.py` — Extended stub_pipeline fixture to also stub faster_whisper.WhisperModel
- `pyproject.toml` — Added 'slow' marker, faster_whisper to mypy ignore_missing_imports
- `scripts/verify-s03.sh` — New verification script with whisper model warning
