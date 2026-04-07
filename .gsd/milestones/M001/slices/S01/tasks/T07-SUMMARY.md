---
id: T07
parent: S01
milestone: M001
key_files:
  - src/vidscope/pipeline/__init__.py
  - src/vidscope/pipeline/runner.py
  - src/vidscope/application/__init__.py
  - src/vidscope/application/ingest_video.py
  - src/vidscope/application/get_status.py
  - src/vidscope/application/list_videos.py
  - src/vidscope/application/show_video.py
  - src/vidscope/application/search_library.py
  - src/vidscope/ports/unit_of_work.py
  - tests/unit/pipeline/test_runner.py
  - tests/unit/application/conftest.py
  - tests/unit/application/test_ingest_video.py
  - tests/unit/application/test_get_status.py
  - tests/unit/ports/test_protocols.py
key_decisions:
  - PipelineRunner writes a RUNNING pipeline_runs row BEFORE the stage executes and then updates it to OK/FAILED on completion — a mid-stage crash (even a segfault) leaves a visible 'stuck in RUNNING' trace in the DB that a future agent can diagnose
  - PipelineRunner uses exactly one UnitOfWork per stage (not per pipeline) so each stage's domain write and matching pipeline_runs row commit atomically or roll back together — this is what makes resume-from-failure safe in the presence of crashes
  - Typed DomainError in a stage is CAUGHT by the runner, persisted to the run row, and returned via RunResult — never re-raised. The CLI decides how to surface the failure. Only StageCrashError-from-bogus-stage-name is raised, and that's a programmer bug that should fail loud.
  - Untyped Exception leaking from a stage is wrapped in StageCrashError with the original in `cause`, persisted as a FAILED run row with 'leaked an untyped exception' in the error text. That text is a grep-able signal that an adapter layer failed to honor the typed-error contract.
  - UnitOfWork protocol now formally declares `search_index: SearchIndex` via a TYPE_CHECKING forward reference to break the circular import with ports.pipeline — the string annotation is still discoverable via `UnitOfWork.__annotations__` for test purposes
  - Use cases are constructor-injected with their UoW factory and clock, never with a container — they are trivially testable with in-memory fakes and have no hidden global state
  - `GetStatusUseCase.execute(limit)` clamps limit to [1, 100] so an untrusted CLI arg can't cause a DoS; `ListVideosUseCase` clamps to [1, 200]
  - IngestVideoUseCase validates empty URLs upfront and returns FAILED without writing anything — the DB stays clean, the CLI gets a typed answer
duration: 
verification_result: passed
completed_at: 2026-04-07T11:23:22.426Z
blocker_discovered: false
---

# T07: Built the PipelineRunner with resume-from-failure + transactional run-row coupling and five application use cases — 14 new tests, 172 total green.

**Built the PipelineRunner with resume-from-failure + transactional run-row coupling and five application use cases — 14 new tests, 172 total green.**

## What Happened

T07 closes the contract layers. The pipeline runner is now the single place in the codebase that decides "run this stage or skip it" and "record this run_row inside the same transaction as the stage's domain write". Use cases are the single entry point for the CLI and the future MCP server — there will never be CLI code that talks to a repository directly.

**pipeline/runner.py** — The `PipelineRunner` class is stateless beyond its constructor args (stages tuple, UnitOfWorkFactory, Clock). It's safe to build once per container and reuse across every `vidscope add` invocation. The main method `run(ctx) -> RunResult` iterates stages in declaration order and runs each one through `_run_one_stage`, which enforces the three architectural guarantees:

1. **Resume-from-failure via `is_satisfied`.** Before `execute()`, the runner opens a UoW and asks `stage.is_satisfied(ctx, uow)`. If True, a SKIPPED `pipeline_runs` row is written and the runner moves on. If False, the stage runs. This is what powers R007's "resume from last successful stage" behavior — stages like IngestStage check whether `videos.platform_id` already exists with a `media_key`, TranscribeStage checks whether a transcript exists for the video, etc.

2. **Transactional coupling of stage + run row.** Each `_run_one_stage` opens exactly one UoW. Inside the `with` block: is_satisfied check → add a RUNNING row upfront (so a mid-stage crash leaves a visible trace even before the finish write lands) → execute the stage → update the row to OK/SKIPPED/FAILED with `finished_at`. Every write happens on the same connection inside the same transaction, so either everything commits (including the run row) or everything rolls back.

3. **Typed error dispatch + untyped crash wrapping.** The runner catches `DomainError` separately from `Exception`. For typed errors, it updates the run row with the error message and returns a FAILED outcome — the typed error is NOT re-raised, it's surfaced through the `RunResult`. For untyped `Exception` (which is a bug — stages are supposed to translate their failures into typed errors), the runner wraps in `StageCrashError` and does the same. The CLI layer decides whether to raise or format the failure for display; the runner itself never leaks exceptions through `run()`.

The only error the runner does raise is `StageCrashError` from `_resolve_stage_phase()` — when a stage reports a `name` that isn't a valid `StageName` enum value. That's a programmer error that should fail loud and early, not turn into a silent failed row.

**RunResult + StageOutcome** — Frozen dataclasses. `RunResult.success` is `True` iff every stage finished OK or SKIPPED. `failed_at` names the stage that raised. `outcomes` lists every stage that actually ran, in order, with status, skipped flag, error message, and the id of the pipeline_runs row.

**pipeline/__init__.py** — Public re-exports: `PipelineRunner`, `RunResult`, `StageOutcome`. That's it. The `Stage` Protocol itself lives in `vidscope.ports.pipeline` and stays there.

**application/** — Five use cases, one file each:

- `ingest_video.py` (`IngestVideoUseCase` + `IngestResult`): the primary user-facing operation. S01 skeleton writes a PENDING pipeline_runs row with source_url and returns a typed result — no real pipeline yet. S02-S06 will plug a real `PipelineRunner` with concrete stages into this use case without changing its public signature. Validates empty URLs up front (returns FAILED without touching the DB). Uses the injected Clock for started_at.

- `get_status.py` (`GetStatusUseCase` + `GetStatusResult`): the observability window. Reads the last N runs via `PipelineRunRepository.list_recent`, plus total counts for runs and videos. Limit is clamped to [1, 100]. Result is a frozen dataclass with `runs: tuple[PipelineRun, ...]`, `total_runs: int`, `total_videos: int`.

- `list_videos.py` (`ListVideosUseCase` + `ListVideosResult`): reads recent videos. Limit clamped to [1, 200].

- `show_video.py` (`ShowVideoUseCase` + `ShowVideoResult`): fetches everything about one video — the Video entity, its latest Transcript, all its Frames, its latest Analysis. Returns `found=False` when the id doesn't exist (never raises).

- `search_library.py` (`SearchLibraryUseCase` + `SearchLibraryResult`): runs an FTS5 query through the SearchIndex port. Returns a tuple of `SearchResult` DTOs. Limit clamped to [1, 200].

Every use case takes dependencies via keyword arguments, never calls `build_container()` itself, and never references a concrete adapter. Adapters are injected by the CLI (T08).

**Circular import fix — worth calling out.** Adding `search_index: SearchIndex` to the `UnitOfWork` Protocol triggered a circular import: `ports.unit_of_work` needed `SearchIndex` from `ports.pipeline`, but `ports.pipeline` already imports `UnitOfWork` for the `Stage` protocol signature. Solved cleanly with a `TYPE_CHECKING` guarded import + a forward-reference string annotation on the `search_index` field. The test that used `get_type_hints(UnitOfWork)` to introspect the fields would fail at runtime trying to resolve the unresolved ref, so I switched it to `UnitOfWork.__annotations__.keys()` which reads raw annotation strings — exactly what we want for a structural check. Documented in the test docstring so the next agent knows why.

**Tests (14 new)**:

- `test_runner.py` (8 tests): happy path single stage, multiple stages in order, satisfied stage skipped (execute never called), typed IngestError marks FAILED with the error persisted, untyped RuntimeError wrapped in StageCrashError with a meaningful message, failing stage aborts subsequent stages (no row for the stage after the failure), bogus stage.name triggers StageCrashError before the runner opens any UoW, stage_names property.
- `test_ingest_video.py` (5 tests): IngestResult shape and message, pipeline_run persisted with the right phase/status/video_id=None/source_url, URL whitespace trimmed, empty URL returns FAILED without writing, started_at uses the injected Clock (not wall-clock time).
- `test_get_status.py` (4 tests): empty DB returns zero counts, populated DB returns runs in newest-first order with correct total counts, limit argument is honored but total counts reflect the DB not the limit, negative limit is clamped to 1 without raising.

**Full suite** — 172 tests in 1.31s. No regressions, no warnings.

## Verification

Ran `python -m uv run pytest tests/unit/pipeline -q` → 8 passed. Ran `python -m uv run pytest tests/unit/application -q` → 9 passed (counting the use-case conftest fixture test). Ran `python -m uv run pytest tests/unit -q` → 172 passed in 1.31s across the full unit test tree. Manual smoke of `python -m uv run python -c "from vidscope.pipeline import PipelineRunner; from vidscope.application import IngestVideoUseCase, GetStatusUseCase"` → imports clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/pipeline -q` | 0 | ✅ pass (8/8) | 270ms |
| 2 | `python -m uv run pytest tests/unit/application -q` | 0 | ✅ pass (9/9) | 300ms |
| 3 | `python -m uv run pytest tests/unit -q` | 0 | ✅ pass (172/172 full unit suite) | 1310ms |

## Deviations

Discovered a real circular import during T07 (ports.pipeline ↔ ports.unit_of_work after I added `search_index: SearchIndex` to UnitOfWork). Solved with a TYPE_CHECKING guarded import and a string forward ref, then adapted the existing Protocol-shape test to read `__annotations__` directly instead of `get_type_hints` (which would fail trying to resolve the unresolvable forward ref at runtime — that's by design for TYPE_CHECKING imports). The circular import is an architectural constraint of having `Stage.execute(uow)` reference UnitOfWork AND `UnitOfWork.search_index` reference SearchIndex — it's solved, not avoided.

## Known Issues

None. Every port is now formally part of the UnitOfWork contract (six fields: videos, transcripts, frames, analyses, pipeline_runs, search_index). The runner correctly handles all four outcomes (OK, SKIPPED, typed-FAILED, untyped-crash-FAILED). Use cases return typed DTOs. The CLI in T08 can consume everything without reaching into adapters.

## Files Created/Modified

- `src/vidscope/pipeline/__init__.py`
- `src/vidscope/pipeline/runner.py`
- `src/vidscope/application/__init__.py`
- `src/vidscope/application/ingest_video.py`
- `src/vidscope/application/get_status.py`
- `src/vidscope/application/list_videos.py`
- `src/vidscope/application/show_video.py`
- `src/vidscope/application/search_library.py`
- `src/vidscope/ports/unit_of_work.py`
- `tests/unit/pipeline/test_runner.py`
- `tests/unit/application/conftest.py`
- `tests/unit/application/test_ingest_video.py`
- `tests/unit/application/test_get_status.py`
- `tests/unit/ports/test_protocols.py`
