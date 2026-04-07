---
id: T04
parent: S01
milestone: M001
key_files:
  - src/vidscope/ports/__init__.py
  - src/vidscope/ports/clock.py
  - src/vidscope/ports/storage.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/unit_of_work.py
  - src/vidscope/ports/pipeline.py
  - tests/unit/ports/test_protocols.py
key_decisions:
  - UnitOfWork exposes the five repositories as class-level annotations so adapters know exactly what to wire, and the same transactional connection backs all of them — this is how atomic cross-aggregate writes work
  - Use cases and stages hold `UnitOfWorkFactory` (a callable) not a `UnitOfWork` instance — every logical operation opens its own transaction and closes it
  - `PipelineRunRepository.latest_by_phase()` is the query that powers `Stage.is_satisfied()` for resume-from-failure — the single method that makes R007 achievable without special casing
  - Storage keys are slash-separated strings, not `pathlib.Path`, so adapters can be local filesystem or object store without changing any caller
  - `MediaStorage.resolve()` returns a `Path` for filesystem adapters but object stores should raise — callers needing byte access call `open()` instead. Two explicit contracts rather than one fudged one.
  - Per-stage service Protocols (`Downloader`, `Transcriber`, etc.) are separate from the generic `Stage` Protocol — stages orchestrate services, services don't know about persistence. This keeps each layer's dependencies minimal.
  - Stage class annotation `name: str` is checked via `get_type_hints(Stage)` not `hasattr()` because Protocol annotations without defaults don't appear as attributes — documented in the test so the next agent doesn't fall into the same trap
duration: 
verification_result: passed
completed_at: 2026-04-07T11:03:37.520Z
blocker_discovered: false
---

# T04: Defined the ports layer: 14 runtime-checkable Protocols plus 4 DTO dataclasses spanning persistence, storage, pipeline stages, and time — no implementations, imports only vidscope.domain.

**Defined the ports layer: 14 runtime-checkable Protocols plus 4 DTO dataclasses spanning persistence, storage, pipeline stages, and time — no implementations, imports only vidscope.domain.**

## What Happened

The ports layer is the application's contract with the outside world. Every fragile external dependency — yt-dlp, faster-whisper, ffmpeg, SQLite, filesystem, LLM providers — sits behind one of these Protocols. When any of them breaks, we replace an adapter, not the pipeline.

Six modules, one Protocol per responsibility:

**clock.py** — `Clock` with a single `now() -> datetime` method. Tiny but important: every place in the codebase that needs the current time will go through this. Tests inject a `FixedClock`, production uses a system clock. Without this, pipeline-run timestamp assertions become flaky.

**storage.py** — `MediaStorage` with `store / resolve / exists / delete / open`. Keys are slash-separated strings (`videos/{id}/media.mp4`, `videos/{id}/frames/0000.jpg`). The domain never touches `pathlib.Path` for media — it passes keys. Adapters resolve them. This is what lets us swap local filesystem for S3/MinIO in a future milestone with zero pipeline changes. The `resolve()` method explicitly returns a `Path` for filesystem-backed adapters; object stores raise `StorageError` and callers use `open()` instead.

**repositories.py** — Five Protocols, one per aggregate: `VideoRepository`, `TranscriptRepository`, `FrameRepository`, `AnalysisRepository`, `PipelineRunRepository`. Key decisions:
- Every method takes and returns **domain entities**, not dicts or SQL rows. Adapters translate.
- Read methods return `None` on miss, never raise. "Not found" is a normal outcome.
- No unbounded queries — every list method has a required `limit` arg.
- `VideoRepository.upsert_by_platform_id()` guarantees idempotent ingest: re-running `vidscope add <url>` on a previously ingested video updates the row instead of raising on the unique constraint. This is the single most important method for R007 (partial-success recovery).
- `PipelineRunRepository.latest_by_phase(video_id, phase)` is the query that powers `Stage.is_satisfied()` — the mechanism that implements resume-from-failure.

**unit_of_work.py** — `UnitOfWork` + `UnitOfWorkFactory`. Transactional boundary. Stages and use cases don't hold a `UnitOfWork` directly — they hold a factory (`Callable[[], UnitOfWork]`) and open a fresh one per logical operation. The repositories are exposed as class-level attributes on the Protocol (`videos: VideoRepository`, `pipeline_runs: PipelineRunRepository`, etc.) so an adapter binds them to its own transactional connection. This is what gives us the "no half-written rows" guarantee — stage execution and its matching pipeline_runs row commit atomically or rollback together.

**pipeline.py** — Two layers in one module:
1. The generic `Stage` Protocol + `PipelineContext` (mutable, threaded through all stages) + `StageResult` (returned by each stage). Stages have `name: str`, `is_satisfied(ctx, uow) -> bool` (for resume), and `execute(ctx, uow) -> StageResult`. The runner calls `is_satisfied` before `execute`; if True, skips and writes a SKIPPED pipeline_runs row.
2. Five per-stage service Protocols: `Downloader`, `Transcriber`, `FrameExtractor`, `Analyzer`, `SearchIndex`. These are what the concrete stages consume. A stage like `IngestStage` holds a `Downloader` and a `MediaStorage` and orchestrates them against a `UnitOfWork` — the `Downloader` Protocol itself doesn't know anything about persistence.

Also in this module: `IngestOutcome` (what a downloader returns before it's persisted) and `SearchResult` (what the search index returns). Both are `@dataclass(frozen=True, slots=True)`.

**__init__.py** — Public re-exports of every Protocol and DTO. 19 names in `__all__`. Import-linter will enforce in T09 that this is the only surface `application/`, `pipeline/`, and `cli/` are allowed to reach for.

**Tests** — `tests/unit/ports/test_protocols.py` with 17 assertions across four test classes:
1. `TestProtocolConformance` — every listed Protocol is a `typing.Protocol` and is `@runtime_checkable` (catches silent decorator regressions).
2. `TestPortSignatures` — every Protocol has its expected methods. `Stage.name` is a class annotation without a default, so it's checked via `get_type_hints(Stage)` rather than `hasattr()` — a subtle detail I caught on the first test run and fixed properly instead of adding a bogus default value.
3. `TestDataclassShapes` — the four DTOs carry their expected fields and defaults.
4. `TestLayerIsolation` — walks `vidscope.ports.*` and asserts every module-level attribute comes from either `vidscope.domain.*` or `vidscope.ports.*` (no adapter, pipeline, application, cli, or infrastructure import). An inexpensive early warning before import-linter enforces the same rule mechanically in T09.

Smoke-tested the public imports and confirmed manual grep of `src/vidscope/ports/*.py` shows only stdlib + `vidscope.domain` + intra-package imports.

## Verification

Ran `python -m uv run pytest tests/unit/ports -q` → 17 tests passed in 100ms. The first run surfaced one failure on `Stage.name` (class annotation not visible via `hasattr`) — fixed by using `get_type_hints(Stage)` instead, which is the right tool for introspecting Protocol annotations without runtime instances. Ran a smoke import of all 19 public names from `vidscope.ports` → `ports ok 19 exports`. Manual grep of imports under `src/vidscope/ports/` confirms only stdlib + `vidscope.domain` + intra-package imports — no reach into outer layers.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/ports -q` | 0 | ✅ pass (17/17) | 100ms |
| 2 | `python -m uv run python -c "from vidscope.ports import VideoRepository, MediaStorage, Stage, UnitOfWork, Clock, Downloader, Transcriber, FrameExtractor, Analyzer, SearchIndex; import vidscope.ports as p; print('ports ok', len(p.__all__), 'exports')"` | 0 | ✅ pass (19 exports) | 400ms |
| 3 | `grep import pattern in src/vidscope/ports/` | 0 | ✅ only stdlib + vidscope.domain + intra-package imports | 30ms |

## Deviations

None from the replanned T04. The first implementation of `test_stage_has_name_execute_and_is_satisfied` used `hasattr()` which doesn't see pure class annotations on Protocols — that was a bug in the test, fixed immediately to use `get_type_hints()` like the equivalent `UnitOfWork` check.

## Known Issues

None. Every planned Protocol and DTO exists, every test passes, the architectural invariant (no outer-layer imports) is satisfied manually and will be enforced mechanically in T09.

## Files Created/Modified

- `src/vidscope/ports/__init__.py`
- `src/vidscope/ports/clock.py`
- `src/vidscope/ports/storage.py`
- `src/vidscope/ports/repositories.py`
- `src/vidscope/ports/unit_of_work.py`
- `src/vidscope/ports/pipeline.py`
- `tests/unit/ports/test_protocols.py`
