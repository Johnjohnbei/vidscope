---
estimated_steps: 1
estimated_files: 14
skills_used: []
---

# T07: Pipeline + application contracts: PipelineRunner + IngestVideoUseCase + GetStatusUseCase

Create src/vidscope/pipeline/ with stage.py (re-exports from ports + helper base classes) and runner.py (PipelineRunner: takes a list of stages + a UnitOfWork factory + a Clock; iterates stages in order; checks is_satisfied(ctx) to skip already-done stages for resume-from-failure; wraps each stage's execute() in a transaction that also writes the matching pipeline_runs row — started_at + status=RUNNING before execute, finished_at + status=OK/FAILED/SKIPPED after; on typed DomainError persists the error and aborts subsequent stages; on unexpected Exception wraps in StageCrashError with traceback). Add tests/unit/pipeline/test_runner.py with fake Stages (DummyOkStage, DummyFailingStage, DummySatisfiedStage) and an in-memory PipelineRunRepository stub proving: (a) happy path writes one pipeline_runs row per stage with status=OK, (b) failing stage aborts and writes status=FAILED, (c) satisfied stage is skipped and writes status=SKIPPED. Create src/vidscope/application/ with ingest_video.py (IngestVideoUseCase takes a Container subset, execute(url: str) builds a PipelineContext, opens a UnitOfWork, registers a placeholder pipeline_runs row with phase=INGEST status=PENDING source_url=url, returns an IngestResult — no actual stages invoked yet, S02-S05 will plug the real pipeline in), get_status.py (GetStatusUseCase returning the last N pipeline_runs as a typed DTO), list_videos.py / show_video.py / search_library.py skeletons that query through their respective ports and return empty DTOs on a fresh DB. Add tests/unit/application/test_ingest_video.py and test_get_status.py.

## Inputs

- ``src/vidscope/ports/pipeline.py``
- ``src/vidscope/ports/unit_of_work.py``
- ``src/vidscope/ports/repositories.py``
- ``src/vidscope/domain/values.py``
- ``src/vidscope/domain/errors.py``
- ``src/vidscope/infrastructure/container.py``

## Expected Output

- ``src/vidscope/pipeline/runner.py` — PipelineRunner with resume-from-failure + transactional pipeline_runs writes`
- ``src/vidscope/pipeline/stage.py` — re-exports + helper base classes`
- ``src/vidscope/application/ingest_video.py` — IngestVideoUseCase (S01 skeleton writing a PENDING row)`
- ``src/vidscope/application/get_status.py` — GetStatusUseCase`
- ``src/vidscope/application/list_videos.py` — ListVideosUseCase skeleton`
- ``src/vidscope/application/show_video.py` — ShowVideoUseCase skeleton`
- ``src/vidscope/application/search_library.py` — SearchLibraryUseCase skeleton`
- ``tests/unit/pipeline/test_runner.py` — happy/failing/satisfied path coverage`
- ``tests/unit/application/test_ingest_video.py` — PENDING row is written`
- ``tests/unit/application/test_get_status.py` — empty + populated DB shapes`

## Verification

python -m uv run pytest tests/unit/pipeline tests/unit/application -q && python -m uv run python -c "from vidscope.infrastructure.container import build_container; from vidscope.application.ingest_video import IngestVideoUseCase; c = build_container(); uc = IngestVideoUseCase(c); r = uc.execute('https://example.com/fake'); print('ingest use case ok:', r)"
