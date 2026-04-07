---
id: T03
parent: S02
milestone: M001
key_files:
  - src/vidscope/pipeline/stages/__init__.py
  - src/vidscope/pipeline/stages/ingest.py
  - tests/unit/pipeline/stages/test_ingest.py
key_decisions:
  - IngestStage knows about three ports and nothing else — no yt-dlp import, no SQLAlchemy import, no filesystem access except via MediaStorage
  - Tempdir sandboxing via `tempfile.TemporaryDirectory` so downloaded files never leak outside the cache_dir even on stage crash
  - Platform sanity check between detect_platform() and outcome.platform — surface yt-dlp/our-parser disagreements loudly instead of silently trusting yt-dlp
  - Stable media key layout `videos/{platform}/{platform_id}/media{ext}` so `vidscope show` can later display the source platform just by reading the key — no extra column needed
  - is_satisfied always returns False in S02 (D025) — DB-level upsert handles idempotence, S06 will add probe-before-download when real-world re-run cost justifies it
  - Tests use REAL SqliteUnitOfWork + REAL LocalMediaStorage + fake Downloader — catches any adapter-layer regression that a pure-mock test would miss
  - _build_media_key() is a module-level helper for reusability by future slices (frames in S04, transcripts in S03)
duration: 
verification_result: passed
completed_at: 2026-04-07T11:57:40.083Z
blocker_discovered: false
---

# T03: Shipped IngestStage: orchestrates Downloader + MediaStorage + VideoRepository through ports only, with tempdir sandboxing, platform mismatch detection, and DB-level idempotence via upsert — 9 stage tests, 238 total green.

**Shipped IngestStage: orchestrates Downloader + MediaStorage + VideoRepository through ports only, with tempdir sandboxing, platform mismatch detection, and DB-level idempotence via upsert — 9 stage tests, 238 total green.**

## What Happened

T03 lands the first concrete pipeline stage. It's pure orchestration — 170 lines of code that knows about three ports (Downloader, MediaStorage, VideoRepository via UnitOfWork), the PipelineContext, and nothing else. No yt-dlp import, no SQLAlchemy import, no pathlib except for the cache_dir type annotation.

**src/vidscope/pipeline/stages/ingest.py** — `IngestStage` class implementing the `Stage` Protocol. `__init__` takes three kwargs: `downloader`, `media_storage`, `cache_dir`. The class attribute `name: str = StageName.INGEST.value` makes it discoverable by the PipelineRunner when mapping stages to pipeline_runs phases.

**execute(ctx, uow) — six steps in sequence:**

1. **Platform detection first.** Call `detect_platform(ctx.source_url)` which raises `IngestError` before any download happens. This saves us from hitting yt-dlp with vimeo URLs or javascript: payloads. The detected platform is captured for the sanity check in step 3.

2. **Tempdir sandboxing.** `tempfile.TemporaryDirectory(prefix="vidscope-ingest-", dir=self._cache_dir)` creates an ephemeral subdir under the cache. Downloaded files land there. The context manager cleans it up automatically on exit (success or failure) — nothing leaks if the stage crashes. Verified by a dedicated test that captures the path and asserts it doesn't exist after execute returns.

3. **Download.** `downloader.download(ctx.source_url, tmp)` — this is where yt-dlp actually runs (in production) or the fake returns a preset outcome (in tests). The outcome carries platform, platform_id, media_path, title, author, duration, upload_date, view_count.

4. **Platform sanity check.** `outcome.platform is not detected_platform` → `IngestError("platform mismatch")`. If yt-dlp's extractor and our URL parser disagree on what platform a URL belongs to, that's a bug somewhere and we surface it loudly instead of silently trusting yt-dlp. Tested with a fake downloader that reports TikTok for a YouTube URL.

5. **MediaStorage copy.** Compute the stable key `videos/{platform}/{platform_id}/media{ext}` via `_build_media_key()`, then `media_storage.store(key, source_path)`. The key shape is explicitly documented: `videos/youtube/dQw4w9WgXcQ/media.mp4`. Using the platform as a folder prefix means `vidscope show <id>` can later display "it came from YouTube" just by reading the key, no extra column needed. Before calling store, we verify the source file exists on disk — yt-dlp CAN lie in its info_dict (covered by tests in T01 too) so we double-check.

6. **Upsert the videos row.** Build the `Video` entity with every field from the outcome plus the `media_key` from step 5, call `uow.videos.upsert_by_platform_id(video)`. This is where DB-level idempotence kicks in — re-running on the same URL updates the existing row instead of raising on the UNIQUE constraint.

7. **Mutate the context.** `ctx.video_id = persisted.id`, `ctx.platform = persisted.platform`, `ctx.platform_id = persisted.platform_id`, `ctx.media_key = persisted.media_key`. Downstream stages (transcribe in S03, frames in S04) read these fields to know what they're operating on.

Returns `StageResult(message=f"ingested {platform}/{platform_id} — {title}")` — the CLI will render this via rich.

**is_satisfied(ctx, uow) — returns False always (for now).** Documented decision D025 recorded explicitly. True is_satisfied-based short-circuit requires a `probe()` method on the Downloader port to get the platform_id without downloading, which is a bigger change than S02 warrants. DB-level idempotence via upsert_by_platform_id already ensures "no duplicate rows". Re-running is suboptimal (re-downloads the media) but safe. S06 will revisit.

**_build_media_key() helper** — pure function that composes the storage key from platform + platform_id + source file extension. Pulled out as a module-level helper so tests (and future slices that build keys for frames, transcripts, etc.) can reuse the same convention.

**Tests — 9 in tests/unit/pipeline/stages/test_ingest.py:**

- `FakeDownloader` dataclass that records every call and either raises or delegates to an `outcome_factory` callable. The factory pattern lets each test shape the `IngestOutcome` it wants without subclassing.
- `_youtube_outcome_factory(platform_id)` returns a factory that writes a real byte string to the destination dir and returns a matching outcome — tests the real file I/O path end-to-end.

Coverage:
- `TestHappyPath` (3): round-trip with full metadata verification (video row, context, stored file bytes, downloader call count), re-execute upserts without duplication (DB count stays at 1, downloader called twice per D025), is_satisfied returns False.
- `TestErrorPaths` (4): invalid URL raises before calling downloader (call count = 0), downloader IngestError propagates with retryable flag preserved, platform mismatch between URL and downloader surfaces as a non-retryable IngestError, missing media file on disk raises "file does not exist".
- `TestStageIdentity` (2): `name` attribute matches StageName.INGEST.value, tempdir is cleaned up after execute (captured via a capturing factory).

The tests use a **real** `SqliteUnitOfWork` against a **real** SQLite file under tmp_path, plus a **real** `LocalMediaStorage`. Only the Downloader is faked. That means if any of the adapter-level invariants break (e.g., upsert changes behavior), these tests catch it.

**Gate fixes:** 1 ruff auto-fix (unused import cleanup), nothing mypy-related, no import-linter regressions. 238/238 unit tests in 1.45s, 52 source files mypy strict clean, 7 architectural contracts kept.

## Verification

Ran `python -m uv run pytest tests/unit/pipeline/stages -q` → 9 passed in 300ms. Ran `python -m uv run pytest tests/unit -q` → 238 passed in 1.45s. Ran `python -m uv run ruff check src tests` → All checks passed (after 1 auto-fix). Ran `python -m uv run mypy src` → Success: no issues found in 52 source files. Ran `python -m uv run lint-imports` → 7 contracts kept, 0 broken. Manually verified the stage conforms to the Stage Protocol: `python -m uv run python -c "from vidscope.pipeline.stages import IngestStage; from vidscope.ports import Stage; print('ok')"`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/pipeline/stages -q` | 0 | ✅ pass (9/9) | 300ms |
| 2 | `python -m uv run pytest tests/unit -q` | 0 | ✅ pass (238/238 full unit suite) | 1450ms |
| 3 | `python -m uv run ruff check src tests && python -m uv run mypy src && python -m uv run lint-imports` | 0 | ✅ pass — all 4 gates clean (52 files, 7 contracts) | 2500ms |

## Deviations

Recorded decision D025 mid-task: IngestStage.is_satisfied() always returns False for S02. True is_satisfied-based short-circuit would require adding a `probe()` method to the Downloader port to extract platform_id without downloading. That's a bigger change than T03 should own. DB-level idempotence via `upsert_by_platform_id` already prevents duplicate rows, which is the important invariant. The decision is revisable and explicitly earmarked for S06 review.

## Known Issues

Re-running `vidscope add <url>` on an already-ingested video re-downloads the media file (the downloader is called twice across two separate runs). This is documented as a trade-off via D025. It is not plan-invalidating — the DB row is not duplicated, and for the single-user local-tool use case the wasted bandwidth on re-run is acceptable for S02. S06 will add probe-before-download.

## Files Created/Modified

- `src/vidscope/pipeline/stages/__init__.py`
- `src/vidscope/pipeline/stages/ingest.py`
- `tests/unit/pipeline/stages/test_ingest.py`
