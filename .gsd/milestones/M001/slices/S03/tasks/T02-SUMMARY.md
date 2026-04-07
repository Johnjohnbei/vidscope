---
id: T02
parent: S03
milestone: M001
key_files:
  - src/vidscope/adapters/whisper/__init__.py
  - src/vidscope/adapters/whisper/transcriber.py
  - tests/unit/adapters/whisper/test_transcriber.py
  - pyproject.toml
key_decisions:
  - faster_whisper imported in exactly one file via lazy import inside `_ensure_model_loaded()` — build_container() never triggers a 150MB download
  - Models cached under <data_dir>/models/ via download_root, not in HF cache
  - Language mapping restrictive: only fr/en — everything else is UNKNOWN, the honest signal
  - VAD filter enabled by default with 500ms silence threshold — dramatically improves short-form quality
  - Eager segment iteration inside try/except so decode errors surface at transcribe() time, not at caller iteration time
  - Transcript returned with VideoId(0) placeholder — the stage fills the real id before persisting
duration: 
verification_result: passed
completed_at: 2026-04-07T15:30:19.727Z
blocker_discovered: false
---

# T02: Shipped FasterWhisperTranscriber: lazy model loading, language auto-detection, VAD filtering, typed error translation, faster_whisper imported in exactly one file — 11 stubbed unit tests, 275 total green, all gates clean.

**Shipped FasterWhisperTranscriber: lazy model loading, language auto-detection, VAD filtering, typed error translation, faster_whisper imported in exactly one file — 11 stubbed unit tests, 275 total green, all gates clean.**

## What Happened

FasterWhisperTranscriber follows the same one-file-isolation pattern as YtdlpDownloader. faster_whisper is imported in exactly one place (`adapters/whisper/transcriber.py`) and the import is lazy — it happens inside `_ensure_model_loaded()` on the first transcribe call, not at module import time. This means: (1) the rest of the codebase never touches faster_whisper, (2) `build_container()` doesn't trigger a 150MB model download just to start the CLI, and (3) the import-linter forbidden contracts already in place from S07 catch any future leak.

**Key design choices:**
- **Lazy model loading.** Constructor stores `model_name`, `models_dir`, `device`, `compute_type` as instance state. The actual `WhisperModel(...)` call happens on the first `transcribe()` invocation. Subsequent calls reuse the cached `self._model`. Tested explicitly via the LazyLoading test class which proves: init alone creates 0 instances, first transcribe creates 1, three transcribes still create 1.
- **VAD filtering enabled by default** (`vad_filter=True`, `min_silence_duration_ms=500`). Strips intro/outro silence which dramatically improves quality on short-form content and reduces transcription time.
- **Language mapping is restrictive.** Only `fr` → FRENCH and `en` → ENGLISH; everything else (including `ja`, `es`, `de`) becomes UNKNOWN. The honest signal: we only validate against the two languages D027/R002 specifies. The analyzer in S05 will still run on the text but the language column won't lie.
- **Models cached under data_dir/models/.** Passed as `download_root` to WhisperModel so the cache lives in the user's vidscope data dir, not in faster_whisper's default location (which is somewhere under HF cache and easy to lose).
- **Eager segment iteration.** faster-whisper returns a generator from `transcribe()` — we drain it inside the try/except block via `tuple(... for seg in segments_iter)` so any decode error surfaces here, not later when the caller iterates the segments.
- **Placeholder VideoId(0).** The transcriber returns a Transcript with `video_id=VideoId(0)` because it doesn't know the real ID. The TranscribeStage in T03 replaces it with the actual id before persisting.

**Test pattern.** I patch `faster_whisper.WhisperModel` directly via `monkeypatch.setattr(faster_whisper, "WhisperModel", FakeWhisperModel)`. The fake has a configurable `_segments` and `_info` so each test shapes the response it wants. A `CapturingFake` subclass tracks every constructor call in a class-level `instances` list, which lets the LazyLoading tests assert how many times the model was loaded. For tests that need a different default config (French language, segments preloaded), I subclass FakeWhisperModel inline and configure inside its `__init__`. Total runtime: 200ms for 11 tests.

**Quality gates:** ruff clean (after one ClassVar fix on the `last_init_kwargs` attribute), mypy strict clean on 54 files (added `faster_whisper` to ignore_missing_imports), 275 unit tests pass, import-linter 7/7 contracts kept, faster_whisper still confined to adapters/whisper/.

## Verification

Ran `python -m uv run pytest tests/unit/adapters/whisper -q` → 11 passed in 200ms. Ran `python -m uv run pytest -q` → 275 passed, 3 deselected. Ruff/mypy/lint-imports all clean. Manually verified faster_whisper is only imported in adapters/whisper/transcriber.py via grep.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters/whisper -q` | 0 | ✅ pass (11/11) | 200ms |
| 2 | `python -m uv run pytest -q && python -m uv run ruff check src tests && python -m uv run mypy src && python -m uv run lint-imports` | 0 | ✅ all gates clean (275 tests, 54 files) | 5000ms |

## Deviations

None.

## Known Issues

None for the unit-test layer. Real model download will happen on first integration run in T05.

## Files Created/Modified

- `src/vidscope/adapters/whisper/__init__.py`
- `src/vidscope/adapters/whisper/transcriber.py`
- `tests/unit/adapters/whisper/test_transcriber.py`
- `pyproject.toml`
