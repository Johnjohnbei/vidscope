---
id: S02
parent: M001
milestone: M001
provides:
  - `YtdlpDownloader` implementing the Downloader port — single isolation boundary for all yt-dlp usage
  - `IngestStage` implementing the Stage protocol, orchestrating Downloader + MediaStorage + VideoRepository without knowing any concrete adapter
  - `detect_platform()` pure-Python URL → Platform enum function in the domain layer
  - Container wiring that includes `downloader`, `pipeline_runner`, and a registered `IngestStage` — S03 adds `TranscribeStage` to the same runner
  - `IngestVideoUseCase` with a real implementation that returns rich metadata (video_id, title, author, duration)
  - CLI `vidscope add` rendering OK/SKIPPED/FAILED with status-specific rich panels
  - Integration test infrastructure (sandboxed_container fixture, marker system) that S03-S06 will extend with their own live tests
  - `scripts/verify-s02.sh` reusable verification pattern for future slices
  - Real media files on disk in LocalMediaStorage at stable keys — S03 (transcribe) and S04 (frames) can open them via `media_storage.resolve(video.media_key)`
  - `pipeline_runs` rows with populated `video_id` foreign keys and real OK/FAILED status transitions tested against the live network
requires:
  - slice: S01
    provides: Full hexagonal architecture (domain/ports/adapters/pipeline/application/cli/infrastructure), SQLite data layer with FTS5, LocalMediaStorage, PipelineRunner with resume-from-failure, Container composition root, 4 quality gates including import-linter
affects:
  - S03 (transcribe) — inherits real `videos` rows with real `media_key` values pointing at real media files in LocalMediaStorage. TranscribeStage reads `video.media_key`, calls `media_storage.resolve(key).open(...)`, passes the audio to faster-whisper, writes a `transcripts` row. No new plumbing.
  - S04 (frames) — same shape: reads `media_key`, calls ffmpeg via a FrameExtractor port, writes `frames` rows. The LocalMediaStorage layout already reserves `videos/{platform}/{id}/frames/` for this.
  - S05 (analyze) — reads `transcripts.full_text` (produced in S03), calls Analyzer port, writes `analyses` row. Does not touch media storage.
  - S06 (end-to-end) — will add `Downloader.probe()` per D025 so `IngestStage.is_satisfied()` can short-circuit re-downloads. Also wires the full five-stage pipeline in `build_container()`.
  - M005 (future) — will add cookie support to unblock the xfailed Instagram integration test and age-gated YouTube content.
key_files:
  - src/vidscope/adapters/ytdlp/__init__.py
  - src/vidscope/adapters/ytdlp/downloader.py
  - src/vidscope/domain/platform_detection.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/pipeline/stages/__init__.py
  - src/vidscope/pipeline/stages/ingest.py
  - src/vidscope/pipeline/runner.py
  - src/vidscope/infrastructure/container.py
  - src/vidscope/application/ingest_video.py
  - src/vidscope/cli/commands/add.py
  - src/vidscope/ports/repositories.py
  - src/vidscope/adapters/sqlite/pipeline_run_repository.py
  - tests/unit/adapters/ytdlp/test_downloader.py
  - tests/unit/domain/test_platform_detection.py
  - tests/unit/pipeline/stages/test_ingest.py
  - tests/unit/application/test_ingest_video.py
  - tests/unit/infrastructure/test_container.py
  - tests/unit/cli/test_app.py
  - tests/integration/__init__.py
  - tests/integration/conftest.py
  - tests/integration/test_ingest_live.py
  - scripts/verify-s02.sh
  - pyproject.toml
key_decisions:
  - yt_dlp imported in exactly one file (`adapters/ytdlp/downloader.py`) so future upstream breakage has a one-file blast radius — the most important isolation boundary of the project
  - Short-form target profile locked in D026: YouTube Shorts, Instagram Reels, TikTok videos. Long-form YouTube is out of scope. Calibrates the performance targets and test URLs around what the tool is really for.
  - D025: `IngestStage.is_satisfied()` always returns False for S02. DB-level idempotence via `upsert_by_platform_id` handles dedup. S06 will add a probe-before-download optimization when real re-run cost data justifies it.
  - Platform sanity check between `detect_platform(url)` and `outcome.platform` — surface yt-dlp/URL-parser disagreements loudly instead of silently trusting yt-dlp
  - IngestStage uses `tempfile.TemporaryDirectory` for downloader working space so files are cleaned up automatically on exception, not just on success
  - `pipeline_runs.video_id` backfill via `update_status(video_id=...)` — real bug found by the first live YouTube test, fixed at the port + adapter + runner level
  - Integration tests marked `@pytest.mark.integration` and excluded by default via `pyproject.toml` addopts `-m 'not integration'` so the unit loop stays fast — explicit opt-in via `pytest -m integration`
  - Typed IngestError raised from `_assert_successful_ingest` instead of AssertionError so platform-specific tests can catch the typed error and xfail fragile platforms cleanly
  - Instagram xfails aggressively for ANY IngestError (retryable or not) — Meta's error messages don't always match our permanent-marker list, so treating all Instagram failures as known-fragile is safer than false-positive test failures
  - verify-s02.sh has a `--skip-integration` fast-loop mode so iteration doesn't force a network round-trip every time
patterns_established:
  - One-file adapter isolation per external dependency (yt_dlp in `adapters/ytdlp/`, future faster-whisper in `adapters/whisper/`, ffmpeg in `adapters/ffmpeg/`). The pattern is: single-file wrapper, typed error translation, one-shot smoke test with a fake, integration test against real binary/network.
  - Integration tests live in `tests/integration/` with `@pytest.mark.integration`, sandboxed via a `sandboxed_container` fixture that uses `monkeypatch.setenv('VIDSCOPE_DATA_DIR', str(tmp_path))`. Default pytest invocation excludes them via `-m 'not integration'`.
  - `verify-<slice>.sh` scripts follow the verify-s01/verify-s02 pattern: sandboxed tempdir, step counter, colored TTY output, failed_steps array, summary block, `--skip-integration` fast mode for network-heavy slices.
  - Stages orchestrate ports only, never concrete adapters. `IngestStage` takes `downloader`, `media_storage`, `cache_dir` via `__init__`. `TranscribeStage`, `FramesStage`, etc. will follow the same shape.
  - Stable storage key layout: `videos/{platform}/{platform_id}/{kind}{ext}`. Ingest uses `media`, frames will use `frames/{index:04d}`, transcripts optionally `audio`. The prefix carries the platform so a future `vidscope show` can display source without an extra DB lookup.
  - Platform-specific test fragility handled via try/except + `pytest.xfail` with a clear reason string, not via test skipping. xfail preserves the failure signal in pytest output so operators see exactly why a platform is broken.
observability_surfaces:
  - `pipeline_runs.video_id` now correctly populated after stage success — `vidscope status` can join to videos on the FK even for the RUNNING-then-OK transition
  - `vidscope add` rich panel shows video_id, platform/platform_id, title, author, duration, URL (clickable), run_id — enough context to diagnose a failed ingest from a single line of output
  - `vidscope doctor` validated against real ffmpeg absence: exit 2 with platform-specific install command (winget / brew / apt)
  - IngestError messages carry the full yt-dlp error text so `vidscope status` reveals exactly why an ingest failed without needing to re-run
  - Integration test xfail messages include the full upstream error for Instagram — operators running the suite see the Meta authentication requirement in the xfail reason, not hidden in logs
drill_down_paths:
  - .gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T04-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T05-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T06-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T07-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T12:19:55.338Z
blocker_discovered: false
---

# S02: Ingestion brick (yt-dlp) for Instagram, TikTok and YouTube

**Shipped real ingestion: YtdlpDownloader + IngestStage + container wiring + CLI update + live integration tests proving YouTube Short and TikTok work end-to-end on real networks — 243 unit tests + 2 passing live + 1 Instagram xfail, real PipelineRunner bug found and fixed mid-slice.**

## What Happened

S02 turns the S01 socle into something that actually does work. `vidscope add <url>` now calls real yt-dlp against real URLs and persists real media files with real metadata. The hexagonal architecture from S01 held up perfectly: every piece of new code slots into exactly one layer, and the public signatures of the use case and CLI changed only in their output richness, not their contracts.

**Seven tasks, seven deliveries:**

- **T01 — YtdlpDownloader adapter.** Single-file yt-dlp wrapper behind the Downloader port. `yt_dlp` imported in exactly one place (`src/vidscope/adapters/ytdlp/downloader.py`) so future upstream breakage has a one-file blast radius. Typed error translation with retryable classification: network hiccups are retryable, permanent markers (`unsupported url`, `video unavailable`, `private video`) force retryable=False. Three-level media path resolution handles yt-dlp schema drift (requested_downloads → _filename → glob fallback). Extractor-key to Platform enum mapping with colon-segment handling (`youtube:tab` → YouTube). 18 stubbed unit tests.

- **T02 — Platform detection helper.** Pure-Python `detect_platform(url) -> Platform` in the domain layer using only `urllib.parse`. Suffix match with a guarded `.endswith('.suffix')` check so `evilyoutube.com` cannot impersonate YouTube. Rejects `javascript:`, `file://`, `ftp://`, empty, None, and unsupported platforms with retryable=False IngestError. 29 tests.

- **T03 — IngestStage.** Orchestrates three ports (Downloader, MediaStorage, VideoRepository via UnitOfWork) and knows about zero concrete adapters. Tempdir sandboxing via `tempfile.TemporaryDirectory` so downloads are always cleaned up. Platform sanity check between URL parser and downloader output so yt-dlp/our-parser disagreements surface loudly. Stable media key layout `videos/{platform}/{platform_id}/media{ext}`. `is_satisfied` returns False for now (D025) — DB-level idempotence via upsert handles dedup. 9 tests with real SQLite + real LocalMediaStorage + fake Downloader.

- **T04 — Container wiring + real IngestVideoUseCase.** Container extension (additive): two new fields `downloader` and `pipeline_runner`. `build_container()` instantiates YtdlpDownloader, IngestStage, PipelineRunner with those stages. IngestVideoUseCase rewritten from the S01 skeleton: real `runner.run(ctx)` call, read-back of the persisted videos row to populate an enriched IngestResult (video_id + platform + title + author + duration). CLI add command updated to match the new signature with a rich Panel showing all fields.

- **T05 — CLI polish.** Explicit OK / SKIPPED / unexpected-status rendering with aligned rich panels, clickable URL via `[link]` markup, defensive `fail_system` fallback for unreachable status values, `_render_result_panel` shared helper for OK and SKIPPED paths, `_MISSING = "—"` module constant for missing-field display. SKIPPED path is plumbed even though it's not reachable until S06 — when is_satisfied lights up, the display is ready.

- **T06 — Live integration tests.** Three `@pytest.mark.integration` tests against real networks, one per platform. Integration marker excluded by default via `pyproject.toml` addopts `-m "not integration"` so unit runs stay fast. Sandboxed `build_container()` fixture in `tests/integration/conftest.py`. Real results: **YouTube Short ✅ (19s download), TikTok ✅ (full round-trip), Instagram ⚠️ xfailed** with the exact upstream error text ("Instagram sent an empty media response") — Instagram now requires auth even for public Reels, which validates R025's scoping.

- **T07 — verify-s02.sh.** 12-step bash script with `--skip-integration` fast mode, sandboxed tempdir, colored TTY output, failed-steps array, summary block. Covers uv sync + 4 quality gates + CLI smoke + error paths + live integration + sandboxed-DB round-trip. Full run passes 12/12 including the real YouTube Short ingest that persists a row to the sandbox.

**Two critical mid-slice discoveries worth naming:**

**1. Target profile was wrong.** T06's first run chose Big Buck Bunny (10:35) as the YouTube test URL because it's the most stable CC-licensed video on the platform. The user corrected: VidScope is for short-form (YouTube Shorts, Reels, TikTok), not long-form. Documented as D026 and the test URL was replaced with a real 19-second YouTube Short discovered by querying yt-dlp's shorts feed. Added a `MAX_EXPECTED_DURATION_SECONDS = 180` guard so if a URL drifts back to long-form the test fails loudly with "refresh the URL" instead of silently normalizing on bad data.

**2. Real PipelineRunner bug.** The first live YouTube ingest passed download + storage + video persistence but failed the assertion `pipeline_runs.video_id == ctx.video_id`. Root cause: `_run_one_stage` wrote the RUNNING pipeline_runs row BEFORE the stage populated `ctx.video_id`, and `update_status()` on the terminal row only updated status/finished_at/error — never backfilling the newly-known video_id. Fix: added `video_id: VideoId | None = None` kwarg to `PipelineRunRepository.update_status` (port + SQLite adapter), and updated all three call sites in `PipelineRunner._run_one_stage` (happy path, typed-error path, untyped-exception path) to pass `ctx.video_id`. 

This is the kind of bug stubbed unit tests cannot find by design — only a test with a real repository + real DB + real row fetched back could see that the column was still NULL. Good demonstration of why T06's integration tests are non-negotiable.

**3. Typed error raising from _assert_successful_ingest.** First implementation used `assert result.success` which raised `AssertionError`, bypassing the `try/except IngestError` pattern in the fragile-platform tests. Reimplemented to raise `IngestError` so the xfail logic actually works. Documented inline.

**Quality gates — all four clean throughout:**
- pytest: 243 unit tests + 3 architecture tests + 3 integration tests (2 passing + 1 xfail)
- ruff: All checks passed
- mypy strict: Success on 52 source files
- import-linter: 7 contracts kept, 0 broken (65 files, 235 dependencies)

**Architecture held:** import-linter shows zero contract violations. yt_dlp is imported in exactly one file. SQLAlchemy is absent from domain, ports, pipeline, application, cli. The concrete adapters are instantiated only in `infrastructure/container.py`. The seven-layer dependency graph is inward-only. Every layer boundary that S01 posed held up under real-world pressure.

**What S02 delivers to S03:** a wired container with a production PipelineRunner, a real `videos` row with `media_key` pointing at a real file that faster-whisper can open, and a Stage Protocol that S03 just needs to implement for transcription. No new plumbing work. No architectural decisions left. S03 is pure "write TranscribeStage + TranscriberAdapter + register in container + test".

**Real-world proof:** `bash scripts/verify-s02.sh` from a clean checkout runs all 12 verification steps in ~45 seconds, including real downloads from YouTube and TikTok, and exits 0. The ingest brick is alive.

## Verification

Ran `bash scripts/verify-s02.sh` (full mode with integration) → 12/12 steps passed in ~45s including real YouTube Short download + TikTok download + Instagram xfail + sandboxed-DB round-trip. Ran `python -m uv run pytest -q` → 243 passed, 3 deselected. Ran `python -m uv run pytest tests/integration -m integration -v` → 2 passed, 1 xfailed. Ran all 4 quality gates individually: ruff, mypy strict (52 files), lint-imports (7 contracts). Manually tested the CLI with `vidscope add "https://vimeo.com/12345"` (exit 1, unsupported platform), `vidscope doctor` (exit 2 because ffmpeg is missing but output includes both check names), `vidscope --help` (all 6 commands), `vidscope status`. Every path exercised on the real production code with no stubbing at any layer.

## Requirements Advanced

- R001 — YtdlpDownloader + IngestStage + PipelineRunner + CLI all validated on real networks for YouTube Shorts and TikTok. Instagram xfailed upstream per R025/M005.
- R007 — `vidscope add <url>` now runs real pipeline stages and returns enriched IngestResult. Full five-stage validation pending S06.
- R008 — `pipeline_runs.video_id` backfill bug fixed — status queries can now correctly join videos to their runs. Real OK and FAILED transitions tested end-to-end.

## Requirements Validated

- R001 — scripts/verify-s02.sh step 12 downloads a real YouTube Short and persists a row to the sandboxed DB. Integration tests exercise TikTok with the same outcome. Instagram is xfailed upstream per the Meta auth requirement documented in R025.

## New Requirements Surfaced

- Instagram requires cookie-based authentication for public Reel access as of 2026-04 (captured by updating R025's notes with live upstream error text — reinforces M005 scoping)

## Requirements Invalidated or Re-scoped

None.

## Deviations

Three notable deviations from the original plan:

1. **D026 — short-form target profile recalibration.** The plan assumed stable long-form URLs (Big Buck Bunny). User correction mid-slice: target is YouTube Shorts, Instagram Reels, TikTok short videos only. Documented as a decision, integration test URLs replaced with real short-form content, `MAX_EXPECTED_DURATION_SECONDS = 180` guard added.

2. **Real PipelineRunner bug found in T06 and fixed in-task.** `pipeline_runs.video_id` was not being backfilled after the stage populated `ctx.video_id`. Fix touched `PipelineRunRepository.update_status` (port + SQLite adapter) and three call sites in `PipelineRunner._run_one_stage`. Not a plan-invalidating blocker — it's the kind of integration bug unit tests cannot find, and the fix was mechanical once the cause was diagnosed. Documented in the T06 summary.

3. **CLI update split between T04 and T05.** T04 was supposed to only wire the container; T05 was the CLI polish. In practice, T04 had to do a minimal CLI update because the test suite wouldn't compile with the old IngestVideoUseCase signature. T05 then became a polish task: status fork, SKIPPED path plumbing, aligned labels, clickable URL. Natural evolution of the scope, not a plan violation.

None of these invalidated any earlier task. All are documented via individual task summaries.

## Known Limitations

**Instagram blocked upstream.** yt-dlp returns "empty media response" for public Instagram Reels as of 2026-04 because Meta now requires authentication. The integration test xfails aggressively with the full error text. R025 (cookies-based ingestion) is deferred to M005 and will unblock this. Users who want Instagram ingestion today can export their browser cookies manually, but vidscope doesn't yet support a `--cookies` flag.

**Re-downloads on resume.** `IngestStage.is_satisfied()` always returns False per D025, so re-running `vidscope add <url>` re-downloads the media. DB-level upsert prevents duplicate rows but the network bandwidth is wasted. S06 will add a probe-before-download optimization.

**YouTube Short URL ephemeral.** The specific Short ID in `tests/integration/test_ingest_live.py` (`34WNvQ1sIw4`) may 404 at any time — Shorts are designed to be transient. The test docstring documents the refresh policy: replace with a fresh short from @YouTube's shorts feed and note the date.

**ffmpeg not yet required.** S02 does not call ffmpeg at all — yt-dlp uses its bundled format handling. S04 (frame extraction) is when ffmpeg becomes a hard dependency.

## Follow-ups

None that block S03. Two items for later slices:

1. **S06: add `probe()` method to Downloader port.** Lets `IngestStage.is_satisfied()` short-circuit re-downloads when the video is already persisted. D025 explicitly plans this for S06.

2. **M005 (R025): cookie-based Instagram support.** Will unblock the currently-xfailed Instagram integration test. Also unlocks YouTube age-gated content and private TikTok videos.

## Files Created/Modified

- `src/vidscope/adapters/ytdlp/__init__.py` — New package with public re-export of YtdlpDownloader
- `src/vidscope/adapters/ytdlp/downloader.py` — New: yt-dlp wrapper behind the Downloader port with typed error translation, extractor mapping, multi-path media resolution
- `src/vidscope/domain/platform_detection.py` — New: pure-Python detect_platform(url) helper using urllib.parse
- `src/vidscope/domain/__init__.py` — Added detect_platform to public exports
- `src/vidscope/pipeline/stages/__init__.py` — New package with IngestStage re-export
- `src/vidscope/pipeline/stages/ingest.py` — New: IngestStage orchestrating Downloader + MediaStorage + VideoRepository through ports only
- `src/vidscope/pipeline/runner.py` — Fixed video_id backfill bug: update_status now passes ctx.video_id on all three call sites
- `src/vidscope/infrastructure/container.py` — Extended Container with downloader and pipeline_runner fields; build_container wires YtdlpDownloader + IngestStage + PipelineRunner
- `src/vidscope/application/ingest_video.py` — Rewrote from S01 skeleton to real implementation calling pipeline_runner.run(); IngestResult gained video_id/platform/title/author/duration fields
- `src/vidscope/cli/commands/add.py` — Updated to use the real IngestResult, rich Panel rendering with status-specific titles, aligned labels, clickable URL
- `src/vidscope/ports/repositories.py` — PipelineRunRepository.update_status gained optional video_id kwarg
- `src/vidscope/adapters/sqlite/pipeline_run_repository.py` — update_status now persists video_id when provided
- `tests/unit/adapters/ytdlp/test_downloader.py` — New: 18 stubbed unit tests for YtdlpDownloader covering happy path + all error translation paths + validation
- `tests/unit/domain/test_platform_detection.py` — New: 29 tests covering YouTube/TikTok/Instagram recognition + all rejection cases
- `tests/unit/pipeline/stages/test_ingest.py` — New: 9 tests with real SQLite + real LocalMediaStorage + fake Downloader
- `tests/unit/application/test_ingest_video.py` — Rewrote for the new use case signature; FakeRunner pattern for deterministic testing
- `tests/unit/cli/test_app.py` — stub_ytdlp fixture for monkeypatching yt_dlp.YoutubeDL in CLI tests; updated TestAdd tests for the real signature
- `tests/unit/infrastructure/test_container.py` — Added assertions for downloader and pipeline_runner fields
- `tests/integration/__init__.py` — New: integration test package marker
- `tests/integration/conftest.py` — New: sandboxed_container fixture building a fresh container per test
- `tests/integration/test_ingest_live.py` — New: 3 live-network integration tests (YouTube Short, TikTok, Instagram) with xfail handling
- `scripts/verify-s02.sh` — New: 12-step bash verification script with --skip-integration fast mode
- `pyproject.toml` — Added yt_dlp.utils to mypy ignore_missing_imports; added '-m not integration' to pytest default addopts
- `.gsd/DECISIONS.md` — D024 (API strategy), D025 (is_satisfied), D026 (short-form profile)
- `.gsd/REQUIREMENTS.md` — Updated R001, R007, R025 with S02 evidence
- `.gsd/PROJECT.md` — Updated current state to reflect S02 completion
