---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: FasterWhisperTranscriber adapter behind the Transcriber port

Create src/vidscope/adapters/whisper/__init__.py and src/vidscope/adapters/whisper/transcriber.py. FasterWhisperTranscriber implements Transcriber port. __init__ takes model_name + models_dir (cache location) + optional language hint. Lazy model loading: model is loaded on first transcribe() call, not at __init__, so the container build doesn't trigger a 150MB download. transcribe(media_path) wraps faster-whisper's WhisperModel: opens the audio via faster_whisper, runs transcription with vad_filter=True for short videos, returns a domain Transcript with language detected, full_text concatenated from segments, and a tuple of TranscriptSegment(start, end, text). Catches faster_whisper exceptions and translates to TranscriptionError(retryable=False). Tests stub WhisperModel via monkeypatch — zero real model download in unit tests.

## Inputs

- ``src/vidscope/ports/pipeline.py` — Transcriber Protocol`
- ``src/vidscope/domain/entities.py` — Transcript, TranscriptSegment`
- ``src/vidscope/domain/values.py` — Language, VideoId`
- ``src/vidscope/domain/errors.py` — TranscriptionError`

## Expected Output

- ``src/vidscope/adapters/whisper/transcriber.py` — FasterWhisperTranscriber class with lazy model loading`
- ``tests/unit/adapters/whisper/test_transcriber.py` — happy path with stubbed WhisperModel + error translation tests`

## Verification

python -m uv run pytest tests/unit/adapters/whisper -q
