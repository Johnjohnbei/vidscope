---
id: S01
parent: M001
milestone: M001
provides:
  - Full hexagonal-architecture socle with every layer tested in isolation
  - SQLite data layer with 5 repositories + FTS5 SearchIndex + UnitOfWork, all bound to the UnitOfWork Protocol
  - LocalMediaStorage adapter with atomic writes and path-traversal protection
  - PipelineRunner with resume-from-failure, transactional stage-run coupling, and typed-error dispatch
  - Five application use cases that consume only ports + pipeline
  - Typer CLI package with six working commands and disciplined exit codes
  - Composition-root Container wiring every adapter via build_container()
  - Four quality gates (ruff, mypy strict, pytest, import-linter) enforced in the test suite
  - Reproducible bash verification script (scripts/verify-s01.sh) covering install + gates + CLI smoke + DB round-trip
requires:
  []
affects:
  - S02 (ingest) — inherits the Container, UnitOfWorkFactory, Stage Protocol, MediaStorage port, and PipelineRunner. S02 writes IngestStage implementing Stage, registers it in build_container, plugs it into IngestVideoUseCase. No new architectural work.
  - S03 (transcribe) — inherits the same with the Transcriber port. TranscribeStage implements Stage.
  - S04 (frames) — same shape with FrameExtractor port + FfmpegFrameExtractor adapter.
  - S05 (analyze) — Analyzer port already exists; adds HeuristicAnalyzer adapter + AnalyzeStage.
  - S06 (search + wiring) — SearchIndex port already exists and is tested; S06 wires IndexStage and exercises the full end-to-end add→search flow with a live URL per platform.
key_files:
  - src/vidscope/__init__.py
  - src/vidscope/config.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/domain/entities.py
  - src/vidscope/domain/values.py
  - src/vidscope/domain/errors.py
  - src/vidscope/ports/__init__.py
  - src/vidscope/ports/clock.py
  - src/vidscope/ports/storage.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/ports/unit_of_work.py
  - src/vidscope/ports/pipeline.py
  - src/vidscope/adapters/__init__.py
  - src/vidscope/adapters/sqlite/schema.py
  - src/vidscope/adapters/sqlite/video_repository.py
  - src/vidscope/adapters/sqlite/transcript_repository.py
  - src/vidscope/adapters/sqlite/frame_repository.py
  - src/vidscope/adapters/sqlite/analysis_repository.py
  - src/vidscope/adapters/sqlite/pipeline_run_repository.py
  - src/vidscope/adapters/sqlite/search_index.py
  - src/vidscope/adapters/sqlite/unit_of_work.py
  - src/vidscope/adapters/fs/local_media_storage.py
  - src/vidscope/infrastructure/config.py
  - src/vidscope/infrastructure/sqlite_engine.py
  - src/vidscope/infrastructure/startup.py
  - src/vidscope/infrastructure/container.py
  - src/vidscope/pipeline/runner.py
  - src/vidscope/application/ingest_video.py
  - src/vidscope/application/get_status.py
  - src/vidscope/application/list_videos.py
  - src/vidscope/application/show_video.py
  - src/vidscope/application/search_library.py
  - src/vidscope/cli/app.py
  - src/vidscope/cli/_support.py
  - src/vidscope/cli/commands/add.py
  - src/vidscope/cli/commands/doctor.py
  - src/vidscope/cli/commands/status.py
  - src/vidscope/cli/commands/list.py
  - src/vidscope/cli/commands/show.py
  - src/vidscope/cli/commands/search.py
  - pyproject.toml
  - uv.lock
  - .importlinter
  - scripts/verify-s01.sh
  - tests/architecture/test_layering.py
key_decisions:
  - Adopt strict hexagonal architecture with import-linter enforcement from day one (D019–D023) — the single most consequential decision, replanned mid-slice after T02
  - Seven layers: domain → ports → adapters → pipeline → application → cli + infrastructure as composition root. Inward-only import rule enforced mechanically.
  - Media references are opaque string keys not pathlib.Path — domain stays storage-agnostic forever, MediaStorage port can be swapped to S3/MinIO without touching any use case or stage
  - PipelineRunner writes a RUNNING pipeline_runs row BEFORE stage execution and UPDATEs it to OK/FAILED/SKIPPED after — mid-stage crashes leave a visible trace, not a silent gap
  - upsert_by_platform_id uses native SQLite ON CONFLICT DO UPDATE so `vidscope add <url>` is idempotent at the DB level with `created_at` preserved across reruns
  - SqliteUnitOfWork types its repository attributes with the Protocol types (not concrete classes) so it's a structural subtype of UnitOfWork with zero casts in the container — mypy happy, invariants explicit
  - Use cases are constructor-injected with a UnitOfWorkFactory and a Clock, never with the full container — trivially testable with in-memory fakes, no hidden global state
  - CLI is a package with one file per command + shared _support module + top-level app registration. Each command has a three-import budget: use case, acquire_container, console. Scales to M002's MCP server via the same pattern.
  - import-linter is run as a subprocess by a pytest architecture test, so any layering regression fails the main test suite — no human discipline needed
  - verify-s01.sh sandboxes under mktemp and uses `python -m uv run` everywhere for cross-platform portability (Windows git-bash, macOS, Linux)
patterns_established:
  - One file per CLI command + shared _support module (`cli/commands/<name>.py` + `cli/_support.py`)
  - One file per domain aggregate's repository adapter + shared helpers for row↔entity translation (`_video_to_row` / `_row_to_video` idiom)
  - `_ensure_utc_for_read` / `_ensure_utc_for_write` symmetric helpers for every adapter that touches timestamp columns — guards against SQLite's naive-datetime quirks
  - frozen=True, slots=True dataclasses for every domain entity and DTO — immutability + memory efficiency without boilerplate
  - `with handle_domain_errors():` context manager wrapping every CLI command body — typed errors become user messages with exit 1 automatically
  - `@runtime_checkable Protocol` for every port so adapter conformance can be asserted with `isinstance(...)` in tests
  - Use the `VIDSCOPE_DATA_DIR` env override everywhere in tests via a tmp_path + monkeypatch fixture — sandboxes the filesystem without mocking
  - `set +e; output=$(cmd); exit=$?; set -e` bash idiom for capturing exit codes inside scripts with `set -e`
  - TYPE_CHECKING guarded imports + string forward refs to break circular imports between port modules without sacrificing type annotations
observability_surfaces:
  - `pipeline_runs` table is the single source of truth for pipeline state — every stage writes exactly one row, `vidscope status` reads it directly with no log parsing
  - Per-stage RUNNING row written upfront by PipelineRunner so crashes leave a visible trace
  - `vidscope doctor` runs startup checks (ffmpeg + yt-dlp) with platform-specific remediation in the output — actionable at 3am
  - CLI exit codes disciplined (0/1/2) so shell scripts can branch on outcome
  - Color-coded RunStatus in `vidscope status` table (green/red/yellow/cyan/blue) for at-a-glance scanning
  - `StageCrashError` row in pipeline_runs is an explicit signal that an adapter leaked an untyped exception — bug marker, not runtime condition
drill_down_paths:
  - .gsd/milestones/M001/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T04-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T05-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T06-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T07-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T08-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T09-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T10-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T11:42:21.877Z
blocker_discovered: false
---

# S01: Project socle, data layer and CLI skeleton

**Delivered a strict hexagonal-architecture socle for VidScope: 48 source files across 7 layers, 185 tests, 7 import-linter contracts enforced, and a working CLI that already writes to the real DB — S02 can now plug in yt-dlp without changing a single public signature.**

## What Happened

S01 was replanned mid-execution (after T02) to pose a strict hexagonal layered architecture instead of the original flat layout. That replan was the single most consequential decision of the slice: every subsequent task slotted cleanly into its layer, and the architecture is now enforced mechanically via import-linter so it can't rot.

**What shipped — ten tasks, ten commits-worth of code:**

- **T01** — uv toolchain installed, Python 3.13 pinned, runtime + dev deps declared with compatible-release specifiers, `uv.lock` committed. Key realization: uv was already installed via pip `--user` but not on PATH. Went with `python -m uv` everywhere for portability.

- **T02** — `src/vidscope/` package with a frozen Config dataclass that resolves data/cache/db paths via platformdirs, honors a `VIDSCOPE_DATA_DIR` env override, and creates every directory eagerly. Memoized + explicit reset hook for tests.

- **T03** — Pure-Python domain layer: six frozen entities (Video, Transcript, TranscriptSegment, Frame, Analysis, PipelineRun), three string enums + two NewType aliases, a typed error hierarchy rooted in DomainError with eight subclasses. Zero third-party imports, 60 tests in 80ms. **Design win:** media references stored as opaque string keys (not Path) so the domain is storage-agnostic forever.

- **T04** — Ports layer: 14 runtime-checkable Protocols (VideoRepository/TranscriptRepository/FrameRepository/AnalysisRepository/PipelineRunRepository, MediaStorage, Stage/Downloader/Transcriber/FrameExtractor/Analyzer/SearchIndex, UnitOfWork, Clock) + 4 DTO dataclasses (PipelineContext, StageResult, IngestOutcome, SearchResult). 17 structural tests. **Design win:** `UnitOfWork` exposes all repositories + SearchIndex as typed attributes so adapters know exactly what to implement and so transactions span every aggregate.

- **T05** — Infrastructure layer: relocated config.py (with a compatibility shim at the old location), added `build_engine` with PRAGMA foreign_keys=ON + journal_mode=WAL, startup checks for ffmpeg (five distinct failure modes, each with platform-aware remediation) and yt-dlp, and the composition-root Container. 26 tests.

- **T06** — SQLite adapters: full schema with FTS5 virtual table (unicode61 + remove_diacritics for French), five repositories, SqliteUnitOfWork with atomic commit/rollback semantics, SearchIndexSQLite with re-indexing safety, LocalMediaStorage with path-traversal protection + atomic writes via `.tmp` sidecar + `os.replace`. 52 tests. **Design win:** `upsert_by_platform_id` uses native SQLite `INSERT ... ON CONFLICT(platform_id) DO UPDATE` so re-running `vidscope add <url>` is idempotent at the DB level, preserving `created_at` on update.

- **T07** — Pipeline runner + five application use cases. `PipelineRunner` guarantees resume-from-failure (via `is_satisfied` check), transactional coupling (stage execution + pipeline_runs row commit atomically or rollback together), typed-error dispatch, and untyped-exception wrapping in `StageCrashError`. Writes a RUNNING row upfront so mid-stage crashes leave a visible trace. Five use cases: IngestVideoUseCase (skeleton writing PENDING row), GetStatusUseCase, ListVideosUseCase, ShowVideoUseCase, SearchLibraryUseCase. 14 tests. **Blocker encountered and solved:** circular import between `ports.unit_of_work` (needed SearchIndex) and `ports.pipeline` (needed UnitOfWork). Solved with TYPE_CHECKING guarded import + string forward ref.

- **T08** — CLI as a package: `app.py` + six command files + shared `_support.py` helpers. Every command is a thin wrapper around a use case. Typed error handler (`handle_domain_errors` context manager) turns DomainError into exit 1. Doctor command with rich table + remediation printout. Rich tables color-coded per RunStatus. 10 CliRunner tests. **Pattern win:** the CLI is the single layer (with infrastructure) allowed to call `build_container` — every command has exactly three imports: its use case, `acquire_container`, and `console`.

- **T09** — Quality gates: ruff + mypy strict + import-linter with seven architectural contracts. Fixed 75 ruff auto-fixable issues, migrated enums to `StrEnum`, added a forward-ref fix for the UnitOfWork Protocol's `search_index` attribute, and retyped SqliteUnitOfWork repository attributes with the Protocol types so `SqliteUnitOfWork` is a structural subtype of `UnitOfWork` without any cast in the container. Created `tests/architecture/test_layering.py` that runs `lint-imports` as a subprocess and parses the output. All four gates clean on the full tree.

- **T10** — `scripts/verify-s01.sh`: a 13-step bash script that exercises every success criterion end-to-end under a sandboxed tempdir. Uses `python -m uv run` for portability across git-bash/macOS/Linux. Captures exit codes correctly (fixed a `$(cmd || true)` bash gotcha mid-run). Tolerates ffmpeg missing (correctly reports exit 2) but requires both check names in the doctor output. Re-runnable infinitely without touching the user's real data dir.

**The architecture in one sentence:** domain imports nothing, ports imports domain only, adapters import domain + ports + their specific third-party deps, pipeline and application import domain + ports + pipeline (application only), cli imports application + domain, infrastructure is the composition root and is allowed to reach any layer to wire it. import-linter enforces every rule via a pytest test in the main suite — any regression fails the build.

**Numbers that matter:**
- 48 source files under `src/vidscope/`
- 29 test files under `tests/`
- 185 tests total, 1.67s full suite runtime
- 7 import-linter contracts, 0 broken
- 0 ruff warnings, 0 mypy errors in strict mode on 47 files
- 13/13 verify-s01.sh steps green on a sandboxed run
- 5 architectural decisions recorded (D019–D023)

**What the next slice inherits:** a fully wired container that returns a MediaStorage, a UnitOfWorkFactory, a Clock, and a SQLAlchemy engine. Five repositories that accept and return domain entities through typed Protocols. A PipelineRunner that already handles resume-from-failure, transactional runs, and error dispatch — S02 just needs to write an IngestStage that implements the Stage protocol, register it in the container, and plug it into IngestVideoUseCase. No new plumbing. No architectural decisions left to make. No fragile globals to work around.

**What the user sees today:** `vidscope --help` lists six commands, `vidscope status` reads from the real DB and prints a color-coded table of pipeline runs, `vidscope add <url>` writes a PENDING row and reports back, `vidscope doctor` detects missing ffmpeg with platform-specific install instructions, `vidscope search` and `vidscope list` and `vidscope show` all handle empty state gracefully. Exit codes are disciplined: 0 = success, 1 = user error, 2 = system error.

The socle is ready for S02.

## Verification

Ran `bash scripts/verify-s01.sh` — 13/13 steps green, S01 verification PASSED. Ran `python -m uv run pytest -q` — 185 passed in 1.67s. Ran `python -m uv run ruff check src tests` — All checks passed. Ran `python -m uv run mypy src` — Success, no issues in 47 files. Ran `python -m uv run lint-imports` — Contracts: 7 kept, 0 broken, 65 files / 235 deps analyzed. Manually tested every CLI command: `vidscope --help`, `--version`, `status` (empty and populated), `doctor` (exit 2 with ffmpeg missing, remediation shown), `add` (happy path + empty URL → exit 1), `list` (empty), `search "hello"` (no hits), `show 999` (exit 1 "no video with id"). Every exit code is correct, every output is rich-formatted.

## Requirements Advanced

- R005 — SQLite + FTS5 data layer implemented with 5 repositories returning domain entities. Schema is idempotently created by the container on first use. Foreign-key cascades enforced via PRAGMA.
- R008 — pipeline_runs table + GetStatusUseCase + `vidscope status` command expose pipeline state as a grep-able surface. PipelineRunner writes a RUNNING row before each stage and updates to terminal status atomically.
- R009 — Package installs via `uv sync` on Windows from a fresh clone. Startup checks detect missing ffmpeg/yt-dlp with platform-specific remediation. Cross-platform Path handling via platformdirs + relative string keys in MediaStorage.
- R010 — Analyzer port is defined as a runtime-checkable Protocol with `provider_name` and `analyze(transcript)` members. A second provider (the real heuristic one) will ship in S05; the port is already consumed through dependency injection.

## Requirements Validated

None.

## New Requirements Surfaced

- A media_storage abstraction surfaced as a first-class port instead of scattered pathlib.Path usage — future S3/MinIO backend is now a one-adapter swap

## Requirements Invalidated or Re-scoped

None.

## Deviations

Mid-slice replan (gsd_replan_slice after T02) changed the entire architecture from a flat module layout to a strict hexagonal one with seven layers and import-linter enforcement. T01 and T02 were preserved intact. T03-T07 (original) became T03-T10 (new) with tighter layer-aligned tasks. Documented in decisions D019-D023 and knowledge.md. The replan was the right call: the original flat layout would have forced a painful refactor in M002 when the MCP server lands, and re-landing the hexagonal structure from the start cost ~30% extra code but zero subsequent refactor debt.

Several small deviations documented in individual task summaries:
- T03: renamed `IndexError` subclass to `IndexingError` to avoid shadowing the builtin
- T06: schema column renamed from `media_path` to `media_key` to match the storage-key abstraction; SqliteUnitOfWork also exposes `search_index` as an extra attribute beyond the original 5-repository plan
- T07: solved a circular import between ports.pipeline and ports.unit_of_work via TYPE_CHECKING forward reference
- T10: original plan said "nuke the data_dir" — too dangerous, sandboxed under mktemp instead

None were plan-invalidating.

## Known Limitations

The media_storage port is present and the LocalMediaStorage adapter works, but nothing in the pipeline writes to it yet — S02 will be the first slice that actually stores a media file. Similarly the search_index is implemented and tested but returns zero hits in production because no transcripts are indexed yet — S06 wires the real indexing. The IngestVideoUseCase is a skeleton that writes a PENDING run row; S02 replaces this with a real PipelineRunner invocation wired to concrete stages. None of these are bugs — they're the deliberate seam between S01 (socle) and S02-S06 (stage implementations).

ffmpeg is not installed on the current dev machine. `vidscope doctor` correctly reports this. It becomes a hard dependency in S04 (frame extraction); for S01 through S03 the pipeline runs without ever touching ffmpeg.

Windows Store Python sandboxes `%LOCALAPPDATA%` under a package-local virtual path; documented in T08's narrative so the next agent looking for the DB doesn't get confused.

## Follow-ups

None that block S02. Two low-priority items for later slices:
1. Remove or formalize the `src/vidscope/config.py` compatibility shim once we're sure nothing imports the old path (S02 or S03 can revisit).
2. Consider adding a `--verbose` flag to the doctor command to print full subprocess stderr when a check fails unexpectedly.

## Files Created/Modified

- `pyproject.toml` — Declared runtime + dev deps with compatible-release specifiers. Added pytest/ruff/mypy/coverage config. Updated entry point to vidscope.cli.app:app. Added import-linter to dev deps.
- `.importlinter` — Seven architectural contracts: layered hexagonal architecture, adapter isolation (sqlite vs fs), domain/ports purity, pipeline/application adapter isolation.
- `scripts/verify-s01.sh` — 13-step end-to-end verification script, sandboxed under mktemp, tolerates ffmpeg-missing, prints pass/fail summary with exit codes.
- `src/vidscope/domain/*` — Pure-Python domain layer: 3 modules (values, errors, entities), 21 public exports, zero third-party deps.
- `src/vidscope/ports/*` — 6 port modules: repositories, storage, pipeline, unit_of_work, clock, re-exports. 14 runtime_checkable Protocols + 4 DTO dataclasses.
- `src/vidscope/adapters/sqlite/*` — 9 modules: schema + 5 repositories + search_index + unit_of_work + re-exports. SQLAlchemy Core only, FTS5 via raw DDL.
- `src/vidscope/adapters/fs/*` — LocalMediaStorage with path-traversal protection + atomic writes via .tmp sidecar.
- `src/vidscope/infrastructure/*` — Config relocation, sqlite_engine factory with FK+WAL pragmas, startup checks, composition-root Container.
- `src/vidscope/pipeline/runner.py` — PipelineRunner with resume-from-failure, transactional run-row coupling, typed error dispatch, StageCrashError wrapping.
- `src/vidscope/application/*` — 5 use cases: IngestVideoUseCase (skeleton), GetStatusUseCase, ListVideosUseCase, ShowVideoUseCase, SearchLibraryUseCase.
- `src/vidscope/cli/*` — CLI package: app.py + _support.py + 6 commands (add/show/list/search/status/doctor). Shared DomainError handler, rich-formatted output.
- `tests/**` — 185 tests across 7 sub-packages: domain (60) + ports (17) + infrastructure (29) + adapters (52) + pipeline (8) + application (6) + cli (10) + architecture (3).
- `.gsd/PROJECT.md` — Updated to reflect S01 completion.
- `.gsd/KNOWLEDGE.md` — Added the architecture rules section with layer definitions, forbidden moves, idempotence contract, and test layering rules.
- `.gsd/DECISIONS.md` — Added D019-D023 covering hexagonal architecture, package layout, stage contract, media storage abstraction, and import-linter enforcement.
