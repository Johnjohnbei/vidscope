---
estimated_steps: 1
estimated_files: 10
skills_used: []
---

# T03: Build pure-Python domain layer (entities, value objects, typed errors)

Create src/vidscope/domain/ with ZERO project-internal imports and ZERO third-party runtime dependencies (stdlib + typing only). This is the innermost layer — no SQLAlchemy, no Typer, no pathlib.Path in signatures (use str keys for storage references). Modules: `entities.py` (frozen dataclasses: Video, Transcript, TranscriptSegment, Frame, Analysis, PipelineRun), `values.py` (Platform enum: INSTAGRAM/TIKTOK/YOUTUBE; Language; StageName enum: INGEST/TRANSCRIBE/FRAMES/ANALYZE/INDEX; RunStatus enum: PENDING/RUNNING/OK/FAILED/SKIPPED; VideoId = int NewType; PlatformId = str NewType), `errors.py` (DomainError base + IngestError, TranscriptionError, FrameExtractionError, AnalysisError, IndexingError, StorageError, ConfigError, each with structured fields: stage, cause, retryable). All entities are `@dataclass(frozen=True, slots=True)`. Entities expose behavior (e.g. Video.is_ingested() checks media_key is not None, PipelineRun.duration() returns finished_at - started_at). No I/O methods. Add `tests/unit/domain/test_entities.py`, `test_values.py`, `test_errors.py` — targets sub-100ms total runtime. No fixtures needed: pure Python.

## Inputs

- ``.gsd/KNOWLEDGE.md` — layer rules and forbidden imports`

## Expected Output

- ``src/vidscope/domain/entities.py` — frozen dataclasses for Video, Transcript, TranscriptSegment, Frame, Analysis, PipelineRun`
- ``src/vidscope/domain/values.py` — Platform, Language, StageName, RunStatus enums + NewTypes`
- ``src/vidscope/domain/errors.py` — typed error hierarchy rooted in DomainError`
- ``src/vidscope/domain/__init__.py` — public re-exports`
- ``tests/unit/domain/test_entities.py` — round-trip and behavior assertions`
- ``tests/unit/domain/test_values.py` — enum coverage and NewType identity`
- ``tests/unit/domain/test_errors.py` — error fields, chaining, retryable flag`

## Verification

python -m uv run pytest tests/unit/domain -q && python -m uv run python -c "import vidscope.domain as d; assert d.Platform.INSTAGRAM; assert d.StageName.INGEST; assert issubclass(d.IngestError, d.DomainError); print('domain ok')"
