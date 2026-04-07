---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T05: Integration tests: real transcription against downloaded media

Extend tests/integration/test_ingest_live.py with assertions on the transcript produced by each platform test. After the ingest assertion block, query uow.transcripts.get_for_video(ctx.video_id) and assert: transcript exists, transcript.full_text is non-empty, transcript.language is one of (FRENCH, ENGLISH, UNKNOWN), at least one segment exists. Note: this will trigger the real faster-whisper model download on first run — the test is slow (~30s for the model download + ~5s per video). Mark with @pytest.mark.slow as well as @pytest.mark.integration so users can skip via -m 'integration and not slow' if they want fast iteration. Update verify-s02 / verify-s07 if needed.

## Inputs

- ``tests/integration/test_ingest_live.py``
- ``src/vidscope/adapters/whisper/transcriber.py``

## Expected Output

- ``tests/integration/test_ingest_live.py` — transcript assertions added to the helper`
- ``pyproject.toml` — 'slow' marker registered`

## Verification

python -m uv run pytest tests/integration -m 'integration and not slow' -v
