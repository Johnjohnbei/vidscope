---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: FramesStage implementing the Stage protocol

Create src/vidscope/pipeline/stages/frames.py. FramesStage with name=StageName.FRAMES.value. __init__ takes FrameExtractor + MediaStorage. is_satisfied returns True if uow.frames.list_for_video(ctx.video_id) is non-empty. execute: (1) requires ctx.video_id and ctx.media_key, (2) resolves media_path via media_storage, (3) creates a temp dir under cache, (4) calls extractor.extract_frames(media_path, tmp_dir), (5) for each Frame returned, copies the image into MediaStorage at videos/{platform}/{platform_id}/frames/{index:04d}.jpg and builds a new Frame with the storage key, (6) calls uow.frames.add_many(frames), (7) mutates ctx.frame_ids. Tests use a fake FrameExtractor + real LocalMediaStorage + real SqliteUnitOfWork.

## Inputs

- ``src/vidscope/ports/pipeline.py``
- ``src/vidscope/ports/storage.py``
- ``src/vidscope/ports/repositories.py``
- ``src/vidscope/domain/entities.py``

## Expected Output

- ``src/vidscope/pipeline/stages/frames.py` — FramesStage class`
- ``src/vidscope/pipeline/stages/__init__.py` — re-export FramesStage`
- ``tests/unit/pipeline/stages/test_frames.py``

## Verification

python -m uv run pytest tests/unit/pipeline/stages -q
