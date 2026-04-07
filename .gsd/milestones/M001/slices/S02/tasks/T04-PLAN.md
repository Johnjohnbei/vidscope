---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T04: Container wiring + real IngestVideoUseCase

Extend Container dataclass with two new fields: `downloader: Downloader` and `pipeline_runner: PipelineRunner`. build_container() instantiates YtdlpDownloader (with the cache_dir from config as its working directory), builds a list of stages `[IngestStage(downloader, media_storage)]`, constructs a PipelineRunner with those stages + unit_of_work factory + clock, and populates the new Container fields. Update IngestVideoUseCase: constructor signature changes from (unit_of_work_factory, clock) to (container) or (unit_of_work_factory, pipeline_runner) — pick the latter to keep the use case testable without a full container. execute(url) rewrites from the S01 skeleton to: (1) strip the URL, (2) create a PipelineContext with source_url, (3) call pipeline_runner.run(ctx), (4) translate RunResult into IngestResult with status = OK / FAILED / SKIPPED, a message, and video_id populated from ctx.video_id if available. Update the S01 IngestResult dataclass to carry video_id, title, author (all optional) so the CLI can display richer output. Unit tests: fake PipelineRunner + real UoW, assert happy path produces OK result, assert failing stage produces FAILED result with the error text, assert is_satisfied path produces SKIPPED result.

## Inputs

- ``src/vidscope/adapters/ytdlp/downloader.py` — YtdlpDownloader from T01`
- ``src/vidscope/pipeline/stages/ingest.py` — IngestStage from T03`
- ``src/vidscope/pipeline/runner.py` — PipelineRunner`
- ``src/vidscope/ports/pipeline.py` — Downloader protocol`

## Expected Output

- ``src/vidscope/infrastructure/container.py` — extended Container + build_container wiring YtdlpDownloader + IngestStage + PipelineRunner`
- ``src/vidscope/application/ingest_video.py` — real IngestVideoUseCase + enriched IngestResult`
- ``tests/unit/application/test_ingest_video.py` — updated to test the real use case with a fake PipelineRunner`
- ``tests/unit/infrastructure/test_container.py` — updated to assert the new Container fields`

## Verification

python -m uv run pytest tests/unit/application tests/unit/infrastructure -q
