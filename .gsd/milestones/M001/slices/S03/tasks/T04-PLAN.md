---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T04: Container wiring: instantiate Transcriber + TranscribeStage

Update src/vidscope/infrastructure/container.py to instantiate FasterWhisperTranscriber(model_name=config.whisper_model, models_dir=config.models_dir), construct TranscribeStage with the transcriber + media_storage, and append both stages to the PipelineRunner stages list. Order matters: IngestStage first, then TranscribeStage. Add transcriber: Transcriber field on Container so tests and the future doctor command can introspect it. Tests in test_container.py: assert container.pipeline_runner.stage_names == ('ingest', 'transcribe'), assert container.transcriber is not None.

## Inputs

- ``src/vidscope/adapters/whisper/transcriber.py``
- ``src/vidscope/pipeline/stages/transcribe.py``

## Expected Output

- ``src/vidscope/infrastructure/container.py` — transcriber field + stage registration`
- ``tests/unit/infrastructure/test_container.py` — 2 new assertions`

## Verification

python -m uv run pytest tests/unit/infrastructure -q
