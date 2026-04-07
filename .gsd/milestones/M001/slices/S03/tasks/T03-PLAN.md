---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: TranscribeStage implementing the Stage protocol

Create src/vidscope/pipeline/stages/transcribe.py. TranscribeStage with name=StageName.TRANSCRIBE.value. __init__ takes Transcriber + MediaStorage. is_satisfied(ctx, uow) returns True if uow.transcripts.get_for_video(ctx.video_id) is not None — unlike ingest which always re-downloads (D025), transcripts CAN be checked cheaply via DB query without re-running anything. execute(ctx, uow): (1) requires ctx.video_id and ctx.media_key (raises TranscriptionError if missing), (2) resolves the media file via media_storage.resolve(ctx.media_key), (3) calls transcriber.transcribe(media_path), (4) builds a Transcript entity with the right video_id, (5) calls uow.transcripts.add(transcript), (6) mutates ctx.transcript_id and ctx.language. Tests use a fake Transcriber and real SqliteUnitOfWork against an in-memory schema.

## Inputs

- ``src/vidscope/ports/pipeline.py` — Stage + Transcriber protocols`
- ``src/vidscope/ports/storage.py` — MediaStorage`
- ``src/vidscope/ports/unit_of_work.py` — UnitOfWork`
- ``src/vidscope/domain/entities.py` — Transcript`
- ``src/vidscope/domain/errors.py` — TranscriptionError`

## Expected Output

- ``src/vidscope/pipeline/stages/transcribe.py` — TranscribeStage class`
- ``src/vidscope/pipeline/stages/__init__.py` — re-export TranscribeStage`
- ``tests/unit/pipeline/stages/test_transcribe.py` — happy path, is_satisfied=True path, missing media_key path, missing video_id path`

## Verification

python -m uv run pytest tests/unit/pipeline/stages -q
