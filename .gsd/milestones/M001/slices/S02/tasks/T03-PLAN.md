---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T03: IngestStage implementation: orchestrate Downloader + MediaStorage + VideoRepository

Create src/vidscope/pipeline/stages/__init__.py and src/vidscope/pipeline/stages/ingest.py. IngestStage implements the Stage protocol with name=StageName.INGEST.value. Constructor takes a Downloader and a MediaStorage (both injected). is_satisfied(ctx, uow): detects the platform from ctx.source_url via detect_platform, looks up uow.videos.get_by_platform_id(platform, platform_id) — but we don't know platform_id until after download, so is_satisfied actually uses the URL hash for a lighter check, OR — cleaner — it just returns False every time and lets the stage re-detect idempotence via upsert_by_platform_id on the database side. Default choice: return False and rely on upsert idempotence. execute(ctx, uow): (1) detect the platform from the URL, (2) call downloader.download(ctx.source_url, destination_dir) into a tempdir inside the container's cache_dir, (3) compute the storage key `videos/{platform_id}/media.{ext}`, (4) call media_storage.store(key, outcome.media_path), (5) build a Video entity with all metadata and media_key, (6) call uow.videos.upsert_by_platform_id(video), (7) mutate ctx.video_id, ctx.platform, ctx.platform_id, ctx.media_key to reflect what landed, (8) return StageResult(message=f'ingested {video.platform.value}/{video.platform_id}'). Any IngestError from the downloader propagates unchanged (the PipelineRunner catches and persists). Unit tests use fake Downloader, fake MediaStorage, and a real SqliteUnitOfWork against an in-memory schema — asserts that execute writes a real videos row, copies the media file into the storage, and populates the context correctly. Also tests a failing Downloader (raises IngestError) and asserts the stage re-raises it.

## Inputs

- ``src/vidscope/ports/pipeline.py` — Stage protocol + Downloader + IngestOutcome`
- ``src/vidscope/ports/storage.py` — MediaStorage`
- ``src/vidscope/ports/unit_of_work.py` — UnitOfWork`
- ``src/vidscope/domain/entities.py` — Video`
- ``src/vidscope/domain/platform_detection.py` — detect_platform`

## Expected Output

- ``src/vidscope/pipeline/stages/ingest.py` — IngestStage class implementing Stage protocol`
- ``src/vidscope/pipeline/stages/__init__.py` — public re-export`
- ``tests/unit/pipeline/stages/test_ingest.py` — happy path with fake Downloader + real SqliteUnitOfWork + real LocalMediaStorage under tmp_path, failing Downloader re-raises IngestError, context is populated correctly, videos row has every expected field`

## Verification

python -m uv run pytest tests/unit/pipeline/stages -q
