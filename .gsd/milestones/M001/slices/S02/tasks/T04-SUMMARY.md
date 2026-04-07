---
id: T04
parent: S02
milestone: M001
key_files:
  - src/vidscope/infrastructure/container.py
  - src/vidscope/application/ingest_video.py
  - src/vidscope/cli/commands/add.py
  - tests/unit/application/test_ingest_video.py
  - tests/unit/cli/test_app.py
  - tests/unit/infrastructure/test_container.py
key_decisions:
  - Container growth pattern held: two new fields (downloader, pipeline_runner) added additively. No existing field signatures changed. No existing use case constructors changed beyond IngestVideoUseCase itself (which was always planned to be rewritten in S02).
  - IngestVideoUseCase re-reads the videos row after the runner completes — one extra query per successful add, but the result DTO carries rich metadata the CLI can render without the CLI or the caller having to peek into the DB themselves
  - `_render_success` helper keeps the add command's happy path formatting in one place instead of embedding format strings in the main function body
  - stub_ytdlp pytest fixture centralizes the yt_dlp.YoutubeDL monkeypatch used by every CLI test that calls `add`. No test has to know how yt_dlp's info_dict is shaped.
  - Defensive None-ness handling on `failed_outcome.error`: mypy caught the implicit Optional-to-str conversion and the fix keeps the error message type strictly `str` in the result dataclass
  - CLI test exercising `https://vimeo.com/12345` proves the full real pipeline path (Typer → container → use case → runner → stage → detect_platform → IngestError) works without any stubbing — the error handler path is covered end-to-end
duration: 
verification_result: passed
completed_at: 2026-04-07T12:03:20.321Z
blocker_discovered: false
---

# T04: Wired the full pipeline through the Container and rewrote IngestVideoUseCase from S01 skeleton to real runner-backed implementation — 240 tests green, 4 gates clean, CLI unsupported-URL path exercised end-to-end without network.

**Wired the full pipeline through the Container and rewrote IngestVideoUseCase from S01 skeleton to real runner-backed implementation — 240 tests green, 4 gates clean, CLI unsupported-URL path exercised end-to-end without network.**

## What Happened

T04 is the task where every piece from T01-T03 gets plugged together and the use case stops being a skeleton.

**Container extension — two new fields.** `downloader: Downloader` and `pipeline_runner: PipelineRunner` added to the frozen dataclass. `build_container()` now instantiates `YtdlpDownloader()`, constructs an `IngestStage(downloader, media_storage, cache_dir)`, builds a `PipelineRunner(stages=[ingest_stage], unit_of_work_factory=_uow_factory, clock=clock)`, and passes everything into the Container. The docstring's "growth model" section is updated to reflect that S02 fills two more slots that were previously marked "later tasks".

Every new import in `container.py` is legitimate per the layering rules: `vidscope.adapters.ytdlp`, `vidscope.pipeline`, `vidscope.pipeline.stages`, and `vidscope.ports.pipeline.Downloader` are all inward from infrastructure. Import-linter confirmed all 7 contracts still kept after the wiring.

**IngestVideoUseCase — full rewrite.** Signature changed from `(unit_of_work_factory, clock)` to `(unit_of_work_factory, pipeline_runner)`. The old skeleton wrote a PENDING pipeline_runs row directly from the use case; the new implementation delegates to the runner, which owns pipeline_runs persistence end-to-end via its transactional write path.

`execute(url)` flow:
1. Strip whitespace. Empty → `IngestResult(FAILED, "url is empty")` without calling the runner.
2. Build a `PipelineContext(source_url=cleaned_url)` and call `runner.run(ctx)`.
3. Extract the first stage outcome's `run_id` for correlation with `vidscope status`.
4. If `run_result.success` is False, find the first outcome with a non-None error, coalesce to a string (defensive because `StageOutcome.error` is `str | None`), and return `IngestResult(FAILED, message, url, run_id)`.
5. On success, re-read the video row via `uow.videos.get(ctx.video_id)` to populate the enriched result fields (title, author, duration) the CLI will display. Done in a separate short-lived UoW — the runner already closed its own transaction by this point.
6. Return `IngestResult(OK, message, url, run_id, video_id, platform, platform_id, title, author, duration)`.

The `IngestResult` dataclass gained six new optional fields: `video_id`, `platform`, `platform_id`, `title`, `author`, `duration`. All default to None so tests and the CLI can handle both the rich success case and the sparse failure case uniformly.

**CLI add command — partial update to match the new signature.** T05 is the proper CLI polish task, but I updated `add.py` here so the full test suite would compile. The command now:
- Uses `IngestVideoUseCase(unit_of_work_factory=container.unit_of_work, pipeline_runner=container.pipeline_runner)`
- On FAILED: `fail_user(result.message)` → exit 1 with the domain error string
- On success: calls a new `_render_success(result)` helper that prints a rich Panel with video_id, platform/platform_id, title, author, duration, url, and run_id — seven fields, one per line, dashes for None values

**CLI tests — two updated, one new, one added fixture.**

The old tests assumed `vidscope add <url>` would write a PENDING row without touching the network. That's no longer true — it now actually calls `YtdlpDownloader.download()`. I added a `stub_ytdlp` fixture that monkeypatches `downloader_module.yt_dlp.YoutubeDL` with a `FakeYoutubeDL` class that writes a dummy file matching the `outtmpl` pattern and returns a valid info_dict. This lets the CLI tests exercise the FULL real path from Typer → use case → runner → stage → downloader, but without any network call.

- `test_after_add_shows_one_run` uses `stub_ytdlp`, invokes `vidscope add <url>`, then `vidscope status`, and asserts the resulting row has status `ok` (not `pending` anymore).
- `test_happy_path_ingests_with_stubbed_downloader` (renamed from `test_happy_path_registers_pending_run`) asserts "ingest OK" + "Fake CLI Video" + "Fake Author" appear in the CLI output.
- `test_unsupported_url_fails_with_user_error` is new: invokes `vidscope add https://vimeo.com/12345` (no stub needed because `detect_platform` rejects it before any downloader call), asserts exit 1 and "unsupported" in the output. This test exercises the real full path including the CLI error handler.
- `test_empty_url_fails_with_user_error` is unchanged — empty URL is rejected before the runner.

**IngestVideoUseCase tests — full rewrite.** Old tests assumed the S01 skeleton signature. New tests use a `FakeRunner` class that takes a `behavior(ctx) -> FakeRunResult` callable, so each test shapes the runner's return value independently. Coverage:

- `test_success_returns_ok_result_with_metadata`: fake runner populates ctx + returns success, use case re-reads the video and returns enriched result. Seeded video via `_seed_video(engine)` so the `uow.videos.get()` call finds a real row. Asserts every field on `IngestResult` is populated correctly.
- `test_trims_whitespace_from_url`: passes a URL with leading/trailing spaces, asserts the cleaned URL reaches the runner.
- `test_failing_runner_returns_failed_result_with_error_message`: runner returns `success=False` with a populated `outcomes[0].error`, use case surfaces the error text.
- `test_empty_url_returns_failed_without_calling_runner`: runner call count stays at 0.
- `test_none_url_returns_failed`: also count 0.
- `test_failing_runner_without_outcomes_still_returns_failed`: edge case where `run_result.outcomes` is empty, use case falls back to `"pipeline failed at stage 'ingest'"`.

**Container test addition.** `test_returns_a_container_with_every_field_populated` now also asserts `container.downloader is not None`, `container.pipeline_runner is not None`, `hasattr(container.pipeline_runner, "run")`, and `"ingest" in container.pipeline_runner.stage_names`. The last assertion proves the stage registration actually plugged `IngestStage` into the runner.

**Quality gates after T04:**
- `pytest` → 240/240 passed in 2.59s
- `ruff check` → All checks passed (2 auto-fixes for minor import cleanups in the new code)
- `mypy src` → Success, no issues in 52 source files (one error found and fixed mid-task: the `failed_outcome.error` coalescing had a None-ness issue mypy caught)
- `lint-imports` → 7/7 contracts kept, 0 broken

**Manual CLI smoke:** `vidscope --help` still lists all six commands. `vidscope add "https://vimeo.com/12345"` returns exit 1 with "unsupported platform URL" — the full real path from Typer through `acquire_container()` through `IngestVideoUseCase` through the runner into the stage's `detect_platform` call, all working end-to-end without touching the network.

## Verification

Ran `python -m uv run pytest tests/unit -q` → 240 passed in 2.59s. Ran `python -m uv run ruff check src tests` → All checks passed (after 2 auto-fixes). Ran `python -m uv run mypy src` → Success: no issues in 52 source files (fixed one str|None coalescing error mid-task). Ran `python -m uv run lint-imports` → 7 contracts kept, 0 broken. Ran `python -m uv run vidscope --help` → six commands listed. Ran `python -m uv run vidscope add "https://vimeo.com/12345"` → exit 1 with "unsupported platform URL" — confirms the full Typer→use case→runner→stage→detect_platform chain works end-to-end on the real container without any network call.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit -q` | 0 | ✅ pass (240/240) | 2590ms |
| 2 | `python -m uv run ruff check src tests && python -m uv run mypy src && python -m uv run lint-imports` | 0 | ✅ pass — all 4 gates clean, 52 files mypy-strict, 7 contracts kept | 3000ms |
| 3 | `python -m uv run vidscope add 'https://vimeo.com/12345'` | 1 | ✅ pass — real pipeline rejects unsupported URL with clean user-error message, no network call | 800ms |

## Deviations

Updated the CLI add command in T04 (not waiting for T05) because the test suite wouldn't even compile without the new IngestVideoUseCase signature being consumed. This moves some of T05's scope forward but leaves the polish (specific rich-table refinements, formatting choices) for T05 to own. T05 becomes a smaller, focused refinement task instead of a bulk rewrite.

## Known Issues

None. The downloader is still stubbed in every unit test — real-network validation comes in T06's integration tests, exactly as the S02 plan specifies.

## Files Created/Modified

- `src/vidscope/infrastructure/container.py`
- `src/vidscope/application/ingest_video.py`
- `src/vidscope/cli/commands/add.py`
- `tests/unit/application/test_ingest_video.py`
- `tests/unit/cli/test_app.py`
- `tests/unit/infrastructure/test_container.py`
