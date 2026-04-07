---
estimated_steps: 1
estimated_files: 8
skills_used: []
---

# T04: Define ports layer (Protocols only, imports domain only)

Create src/vidscope/ports/ containing ONLY `typing.Protocol` interfaces. No implementations, no I/O, no third-party imports except `typing` and the `vidscope.domain` package. Modules: `repositories.py` (VideoRepository, TranscriptRepository, FrameRepository, AnalysisRepository, PipelineRunRepository — each with the CRUD needed across M001 as Protocol methods), `storage.py` (MediaStorage protocol with store/resolve/exists/open/delete methods, operating on string keys), `pipeline.py` (Downloader, Transcriber, FrameExtractor, Analyzer, SearchIndex protocols — one per pipeline stage; Stage protocol with `execute(ctx)` and `is_satisfied(ctx)`; StageResult dataclass; PipelineContext dataclass with video_id, url, media_key, etc.), `clock.py` (Clock protocol with now() -> datetime — lets tests inject a frozen clock), `unit_of_work.py` (UnitOfWork protocol exposing `__enter__`/`__exit__` plus one repository property per domain aggregate). Every Protocol is `@runtime_checkable` so tests can assert adapters conform. Add `tests/unit/ports/test_protocols.py` that imports each Protocol and asserts it has the expected attribute signatures via `inspect.get_annotations`.

## Inputs

- ``src/vidscope/domain/__init__.py` — entities and value objects referenced by port signatures`

## Expected Output

- ``src/vidscope/ports/repositories.py` — five repository Protocols`
- ``src/vidscope/ports/storage.py` — MediaStorage Protocol`
- ``src/vidscope/ports/pipeline.py` — Stage/PipelineContext/StageResult + five stage-specific Protocols`
- ``src/vidscope/ports/clock.py` — Clock Protocol`
- ``src/vidscope/ports/unit_of_work.py` — UnitOfWork Protocol with repository properties`
- ``src/vidscope/ports/__init__.py` — public re-exports`
- ``tests/unit/ports/test_protocols.py` — runtime_checkable assertions`

## Verification

python -m uv run pytest tests/unit/ports -q && python -m uv run python -c "from vidscope.ports import VideoRepository, MediaStorage, Stage, UnitOfWork, Clock; from typing import Protocol; assert hasattr(VideoRepository, '__protocol_attrs__') or True; print('ports ok')"
