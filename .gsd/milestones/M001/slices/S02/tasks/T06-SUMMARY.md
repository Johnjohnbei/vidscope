---
id: T06
parent: S02
milestone: M001
key_files:
  - tests/integration/__init__.py
  - tests/integration/conftest.py
  - tests/integration/test_ingest_live.py
  - pyproject.toml
  - src/vidscope/ports/repositories.py
  - src/vidscope/adapters/sqlite/pipeline_run_repository.py
  - src/vidscope/pipeline/runner.py
key_decisions:
  - Target content profile locked to short-form vertical (YouTube Shorts, Instagram Reels, TikTok) via D026 — the primary smoke test is now a real 19s Short, not a 10-minute long-form
  - MAX_EXPECTED_DURATION_SECONDS = 180 guard in the integration test so a URL drifting back to long-form fails loudly instead of silently normalizing
  - `pyproject.toml` default addopts include `-m 'not integration'` so `pytest` stays fast by default — integration tests run only on explicit opt-in
  - PipelineRunRepository.update_status gained an optional `video_id` kwarg so the runner can backfill the foreign key after the stage populates the context — fixed a real bug that unit tests could not detect by construction
  - _assert_successful_ingest raises typed IngestError (not AssertionError) so platform-specific tests can catch the typed error and xfail fragile platforms cleanly
  - Instagram xfails aggressively — any IngestError (retryable OR non-retryable) is treated as a known-fragile-platform xfail until R025 / M005 ship cookie support
  - Target URLs live in module-level constants with documented refresh policy — when a URL 404s, the fix is one edit to one line, no test logic changes
duration: 
verification_result: passed
completed_at: 2026-04-07T12:13:13.929Z
blocker_discovered: false
---

# T06: Live-network integration tests on three platforms: YouTube Short ✅, TikTok video ✅, Instagram Reel ⚠️ xfailed with clear "Instagram requires login" message — surfaced a real runner bug on pipeline_runs.video_id update and fixed it along the way.

**Live-network integration tests on three platforms: YouTube Short ✅, TikTok video ✅, Instagram Reel ⚠️ xfailed with clear "Instagram requires login" message — surfaced a real runner bug on pipeline_runs.video_id update and fixed it along the way.**

## What Happened

T06 is the reality check. Everything before this task was covered by stubbed tests running in 2 seconds. T06 hits the real network with the real yt-dlp against the real platforms, and the outcome tells us what the socle actually delivers today.

**The real-world result, one platform at a time:**

**✅ YouTube Short (19 seconds, @YouTube channel).** Full pipeline pass in 1.46s: yt-dlp downloads the media file, LocalMediaStorage atomically stores it at `videos/youtube/34WNvQ1sIw4/media.mp4`, VideoRepository upserts the row with title/author/duration/view_count, PipelineRunRepository records the OK run. Every assertion green.

Initial choice was Big Buck Bunny (the Blender Foundation's CC-BY short film, `aqz-KE-bpKQ`) because it's historically the most stable CC-licensed video on YouTube. First live run showed this was wrong: Big Buck Bunny is 635 seconds (10:35) which is long-form content, not the short-form vertical videos VidScope is built for. **D026 recorded explicitly:** VidScope's target profile is YouTube Shorts (<60s), Instagram Reels (<90s), and TikTok videos. Long-form is out of scope. The test URL was replaced with a real YouTube Short (`34WNvQ1sIw4`, 19s, official @YouTube channel) discovered by querying yt-dlp's shorts feed. Added a `MAX_EXPECTED_DURATION_SECONDS = 180.0` guard in the test — if a URL drifts back to long-form, the test fails loudly with "refresh the URL" instead of silently normalizing on bad data.

**✅ TikTok video (official @tiktok account).** Passed cleanly on the first live run. yt-dlp's TikTok extractor is reliable for public videos as of 2026-04-07.

**⚠️ Instagram Reel (official @instagram account, C0nELpwLkpk).** XFAILED with a precise upstream error: `"Instagram sent an empty media response. Check if this post is accessible in your browser without being logged-in. If it is not, then use --cookies-from-browser or --cookies for the authentication."` Instagram now requires authentication even for public Reels. This validates R025's scoping — cookie-based ingestion is not a "nice to have" but a hard requirement that only becomes a blocker at M005. The xfail path surfaces the error with the exact remediation message so an operator running `pytest tests/integration -m integration` sees why Instagram is failing today. R025 was updated with the live error text as evidence.

**Real bug found and fixed during T06.** The first live YouTube run passed the download and storage steps but failed the assertion `pipeline_runs.video_id == ctx.video_id`. Root cause: `PipelineRunner._run_one_stage` wrote a RUNNING pipeline_runs row BEFORE the stage's execute() had a chance to populate `ctx.video_id`, and then `update_status()` on the terminal row only updated status/finished_at/error — never backfilling the video_id that the stage had just persisted. The row stayed with `video_id=NULL` even though the corresponding video existed.

The fix spans three files:
1. **`PipelineRunRepository.update_status`** port signature and SQLite implementation gained an optional `video_id: VideoId | None = None` parameter. When provided, it's included in the UPDATE statement. When None, the column is left alone.
2. **`PipelineRunner._run_one_stage`** now passes `ctx.video_id` on all three update_status call sites: the happy path (OK/SKIPPED), the typed-DomainError path (where a stage might have persisted a row before failing on a later step), and the untyped-exception path (same rationale). This means pipeline_runs rows are always linked to their matching video once that video exists, regardless of which path the runner took.
3. **Test coverage** — the 240 existing unit tests all kept passing because the fakes they use for pipeline_runs already accepted the new kwarg via `**kwargs`.

This is the kind of bug that stubbed tests cannot find by design. Stubbed PipelineRunRepository fakes accepted any keyword arguments and reported "yes I updated the row" without actually doing anything. Only a test with a real repository + a real DB + a real row fetched back out could see that the `video_id` column was still NULL. It's a good example of why T06's integration tests are non-negotiable — they catch the class of bugs that unit tests miss by construction.

**Integration test infrastructure:**

- **`tests/integration/conftest.py`** with a `sandboxed_container` fixture that uses `monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))`, `reset_config_cache()` before and after yield, and returns a fresh `build_container()`. Every integration test gets an isolated DB, storage, and cache dir. Sandboxing is critical because live ingestion writes real files — we never want the test runner to touch the user's real library.

- **`tests/integration/test_ingest_live.py`** with three test classes (one per platform), each marked `@pytest.mark.integration`. The shared `_assert_successful_ingest` helper raises a typed `IngestError` (not `AssertionError`) when the pipeline reports `success=False`, so individual platform tests can catch the typed error and decide whether to xfail (for known-fragile platforms) or propagate the failure (YouTube). This is important: the first implementation used `assert result.success` directly, which raised `AssertionError` that my try/except `IngestError` could never catch. Lesson documented in the test.

- **`pyproject.toml` addopts update** to include `"-m", "not integration"` so the default `pytest` invocation skips integration tests. The unit suite (`pytest tests/unit`, `pytest`) deselects 3 tests and runs 243. Running them explicitly requires `pytest tests/integration -m integration -v` — this override bypasses the default marker filter.

**Target URLs — policy for refreshing:**

Every URL is documented in the module docstring with a "last refreshed" date and a refresh policy. YouTube Shorts are ephemeral by design so the YouTube test URL may need refreshing more often than any other. TikTok and Instagram target the official platform-owner accounts (@tiktok, @instagram) because those are the most durable sources.

**Full result:**
- `pytest` (default): 243 passed, 3 deselected in 1.85s
- `pytest tests/integration -m integration -v`: 2 passed, 1 xfailed in 7.20s
- ruff, mypy strict (52 files), import-linter (7 contracts): all clean

**What S02 now proves end-to-end on real networks:**
- R001 is validated for YouTube and TikTok (2 of 3 target platforms)
- R001 is documented-as-blocked for Instagram (R025 defers this to M005)
- R005 (persistent DB) exercised with real rows across real transactions
- R007 (single-command end-to-end) works for public YouTube/TikTok
- R008 (pipeline_runs observability) exercised and fixed (the video_id backfill bug)
- R009 (cross-platform local install) still holds — the test ran on Windows without any platform-specific code

## Verification

Ran `python -m uv run pytest tests/integration -m integration -v` → 2 passed, 1 xfailed in 7.20s. YouTube Short downloaded and stored correctly, TikTok video same, Instagram xfailed with the exact upstream error text captured in the xfail message. Ran `python -m uv run pytest -q` → 243 passed, 3 deselected in 1.85s (integration tests correctly skipped by default via `-m "not integration"`). Ran `python -m uv run ruff check src tests` → All checks passed. Ran `python -m uv run mypy src` → Success, 52 files. Ran `python -m uv run lint-imports` → 7 contracts kept.

Manually verified the bug fix: the pipeline_runs.video_id column is now populated on OK runs by inspecting a fresh DB after a live YouTube ingest. The video_id matches the corresponding videos.id.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/integration -m integration -v` | 0 | ✅ 2 passed, 1 xfailed (YouTube Short + TikTok green, Instagram expected xfail) | 7200ms |
| 2 | `python -m uv run pytest -q` | 0 | ✅ pass (243 passed, 3 deselected — integration tests correctly skipped by default) | 1850ms |
| 3 | `python -m uv run ruff check src tests && python -m uv run mypy src && python -m uv run lint-imports` | 0 | ✅ pass — all 4 gates clean (52 files, 7 contracts) | 3000ms |

## Deviations

Three deviations worth naming:

1. **Target profile recalibration (D026).** The plan originally specified stable long-form content like Big Buck Bunny. The user corrected mid-task: VidScope's target is short-form vertical content (YouTube Shorts, Instagram Reels, TikTok). This was documented as D026 and the YouTube URL was replaced with a real Short.

2. **Real bug found and fixed in-task.** The PipelineRunner was not backfilling `pipeline_runs.video_id` after the stage populated `ctx.video_id`. The fix touched `PipelineRunRepository.update_status` (port + adapter) and three call sites in `PipelineRunner._run_one_stage`. This was not a T06 scope item — it's a direct consequence of writing the first test that actually exercised the full stack end-to-end. Documented in the narrative.

3. **`_assert_successful_ingest` now raises typed IngestError instead of AssertionError.** The first implementation used `assert result.success` which raised AssertionError, bypassing the try/except IngestError pattern in the platform-specific tests. Reimplemented to raise IngestError so the fragile-platform xfail logic actually works.

All three are improvements, none are plan-invalidating.

## Known Issues

Instagram Reel ingestion is blocked upstream: yt-dlp returns "empty media response" because Instagram requires authentication for public Reels as of 2026-04-07. This is NOT a vidscope bug — it's a real-world platform constraint that R025 (deferred to M005) addresses by adding cookie-based authentication. The integration test xfails with the full error message so operators see why. Instagram can still be ingested by users who manually export their cookies once M005 ships.

YouTube Shorts are ephemeral content — the specific Short URL in the test file may 404 at some point. The test docstring documents the refresh policy: replace the URL with a fresh Short from @YouTube's shorts feed and note the date. No code change needed.

## Files Created/Modified

- `tests/integration/__init__.py`
- `tests/integration/conftest.py`
- `tests/integration/test_ingest_live.py`
- `pyproject.toml`
- `src/vidscope/ports/repositories.py`
- `src/vidscope/adapters/sqlite/pipeline_run_repository.py`
- `src/vidscope/pipeline/runner.py`
