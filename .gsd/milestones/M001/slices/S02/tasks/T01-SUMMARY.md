---
id: T01
parent: S02
milestone: M001
key_files:
  - src/vidscope/adapters/ytdlp/__init__.py
  - src/vidscope/adapters/ytdlp/downloader.py
  - tests/unit/adapters/ytdlp/test_downloader.py
key_decisions:
  - yt-dlp is imported in exactly one file — any future breakage has a blast radius of `src/vidscope/adapters/ytdlp/downloader.py` plus its tests, nothing else
  - Retryable classification driven by error content: transient failures (network, rate limit) default retryable=True, permanent markers (`unsupported url`, `video unavailable`, `private video`) force retryable=False. Pipeline runner uses this for the retry decision.
  - Format spec `best[ext=mp4]/best` prefers mp4 then falls back to anything — mp4 is what faster-whisper and ffmpeg both handle natively on every platform
  - Three-level media path resolution (requested_downloads → _filename → directory glob) handles yt-dlp's schema drift across versions without hardcoding a single path key
  - Extractor key normalization splits on `:` so `youtube:tab`, `youtube:clip`, etc. all map to Platform.YOUTUBE without enumerating every variant
  - Unexpected exceptions (non-DownloadError, non-ExtractorError) are caught in a dedicated branch and wrapped as non-retryable IngestError with `unexpected yt-dlp failure` prefix — crashes are visible, not silent
  - `ignoreerrors=False` in yt-dlp options so yt-dlp raises on failures instead of returning partial data — we want the exceptions
duration: 
verification_result: passed
completed_at: 2026-04-07T11:51:41.315Z
blocker_discovered: false
---

# T01: Shipped YtdlpDownloader: single-file yt-dlp wrapper behind the Downloader port with typed error translation, extractor-to-platform mapping, multi-path media file resolution, 18 unit tests with stubbed yt-dlp — 200 total green.

**Shipped YtdlpDownloader: single-file yt-dlp wrapper behind the Downloader port with typed error translation, extractor-to-platform mapping, multi-path media file resolution, 18 unit tests with stubbed yt-dlp — 200 total green.**

## What Happened

T01 closes the most critical isolation boundary of the whole project. yt-dlp is the single external dependency most likely to break at unpredictable moments (platform API rotations, Instagram CDN changes, yt-dlp extractor bugs). Every one of those failures will now land in exactly one file — `src/vidscope/adapters/ytdlp/downloader.py` — with a typed error translation that lets the pipeline runner decide whether to retry.

**src/vidscope/adapters/ytdlp/downloader.py** — `YtdlpDownloader` class implementing the `Downloader` Protocol. Four design decisions worth naming:

1. **Single-line yt-dlp import.** `import yt_dlp` and `from yt_dlp.utils import DownloadError, ExtractorError` happen at the top of this file and nowhere else in the codebase. import-linter's existing forbidden contracts on `domain`, `ports`, `pipeline`, and `application` already prevent any leak — but even without them, this is the only place yt-dlp's name appears in any `.py` under `src/vidscope/`.

2. **Typed error translation with retryable classification.** `DownloadError` and `ExtractorError` both get translated to `IngestError`. The `retryable` flag is set based on error content: network-looking errors default to retryable=True; errors matching permanent markers (`"unsupported url"`, `"video unavailable"`, `"private video"`, `"members-only"`, etc.) get retryable=False. This feeds directly into `PipelineRunner`'s retry logic in future slices. Any unexpected non-yt-dlp exception is caught in a separate `except Exception` branch and wrapped as a non-retryable IngestError — crashes are never silently swallowed.

3. **Format selection.** `'best[ext=mp4]/best'` prefers mp4 where available and falls back to best-quality anything. mp4 is the sweet spot for S03 (faster-whisper opens it natively) and S04 (ffmpeg handles it on every platform without container gymnastics). The `format_spec` is an `__init__` parameter so tests or future code can override without subclassing.

4. **Three-level media path resolution.** yt-dlp's info_dict schema has shifted across versions. I check three locations in priority order: (a) `info['requested_downloads'][0]['filepath']` (yt-dlp 2024+), (b) `info['_filename']` (older builds), (c) glob the destination dir for `{platform_id}.*` and pick a non-intermediate file (skipping `.part`, `.json`, `.tmp`). If all three fail, raise `IngestError("no media file was found")` — never return a path that doesn't exist on disk. Every path is covered by a test.

**Extractor to Platform mapping.** `_EXTRACTOR_TO_PLATFORM` is a frozen dict mapping yt-dlp's extractor_key strings to our `Platform` enum. Covers `youtube`, `youtubetab`, `youtubeclip`, `youtubeshorts`, `tiktok`, `instagram`, `instagramstory`. Extractor keys often include colons (`youtube:tab`) — I split on `:` and try the base segment too so we don't have to list every variant. Unknown extractors raise `IngestError("unsupported yt-dlp extractor")` with the full supported list in the message so operators see what would need adding.

**yt-dlp options.** Passed via `_build_options()` as a dict: `format`, `outtmpl=destination_dir/%(id)s.%(ext)s`, `quiet=True`, `no_warnings=True`, `noprogress=True`, `writeinfojson=False`, `writesubtitles=False`, `writeautomaticsub=False`, `skip_download=False`, `ignoreerrors=False`. The output template puts the file under the destination dir with the platform id as its stem, which makes the glob fallback deterministic. `ignoreerrors=False` is critical — we want yt-dlp to raise, not silently return empty dicts.

**Safety nets on the top layer:** `download(url, destination_dir)` validates the URL is non-empty upfront (immediate `IngestError` before touching yt-dlp), creates `destination_dir` if missing, opens yt-dlp inside a context manager so it's always cleaned up, handles the `info is None` case (yt-dlp returns None on some malformed URLs without raising), and delegates to `_info_to_outcome()` which does the final schema validation and field translation.

**Tests — 18 in `tests/unit/adapters/ytdlp/test_downloader.py`:**

- `FakeYoutubeDL` class that impersonates `yt_dlp.YoutubeDL`: implements `__enter__/__exit__/extract_info`, optionally raises on extract, optionally touches a fake media file on disk. Tests swap the module-level `yt_dlp.YoutubeDL` symbol with a factory that returns a `FakeYoutubeDL` instance.

- `TestHappyPath` (6): YouTube happy path with full metadata round-trip (platform, platform_id, url, media_path, title, author, duration, upload_date, view_count all verified), TikTok + Instagram extractor mapping, extractor with colon (`youtube:tab`) correctly split to `youtube`, legacy `_filename` field path, directory glob fallback when neither `requested_downloads` nor `_filename` is present.

- `TestErrorTranslation` (6): `DownloadError("network hiccup")` → retryable IngestError, `DownloadError("Unsupported URL")` → non-retryable, `DownloadError("video unavailable")` → non-retryable, `ExtractorError("extractor broke")` → non-retryable by default, `ExtractorError("Service is temporarily unavailable")` → retryable (transient marker), unexpected `RuntimeError` → non-retryable with "unexpected yt-dlp failure" in the message.

- `TestValidation` (6): empty URL → IngestError, whitespace URL → IngestError, missing `id` in info → IngestError mentioning "no 'id' field", unknown extractor → IngestError with supported list, `info is None` → IngestError, missing media file on disk → IngestError with "no media file was found".

Every test runs with zero network. Total runtime: 160ms for the full 18 tests.

**Full suite check:** 200/200 unit tests pass in 1.40s (from 185 → 200 with the new 18 ytdlp tests plus the 3 existing architecture tests counted). import-linter still shows 7/7 contracts kept — the yt_dlp import is confined to the adapter package, nowhere else.

## Verification

Ran `python -m uv run pytest tests/unit/adapters/ytdlp -q` → 18 passed in 160ms. Ran `python -m uv run pytest tests/unit -q` → 200 passed in 1.40s. Ran `python -m uv run lint-imports` → 7 contracts kept, 0 broken. Manually verified import containment via `grep -rn "yt_dlp" src/vidscope/` — only matches are in `src/vidscope/adapters/ytdlp/downloader.py` and `src/vidscope/infrastructure/startup.py` (the existing doctor check from S01). No other source file references yt-dlp.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters/ytdlp -q` | 0 | ✅ pass (18/18) | 160ms |
| 2 | `python -m uv run pytest tests/unit -q` | 0 | ✅ pass (200/200 full unit suite) | 1400ms |
| 3 | `python -m uv run lint-imports` | 0 | ✅ pass — 7 contracts kept, yt_dlp still confined to adapters/ytdlp/ | 1300ms |

## Deviations

None from the plan. The adapter package shape and test coverage match what T01 specified.

## Known Issues

None. The downloader is covered by stubbed tests. Real-network validation lives in T06's integration tests and will exercise the adapter against actual public URLs.

## Files Created/Modified

- `src/vidscope/adapters/ytdlp/__init__.py`
- `src/vidscope/adapters/ytdlp/downloader.py`
- `tests/unit/adapters/ytdlp/test_downloader.py`
