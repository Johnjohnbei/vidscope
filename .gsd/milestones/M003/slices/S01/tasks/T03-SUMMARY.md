---
id: T03
parent: S01
milestone: M003
key_files:
  - src/vidscope/adapters/ytdlp/downloader.py
  - tests/unit/adapters/ytdlp/test_downloader.py
key_decisions:
  - Separate options dict for list vs download — download path stays unchanged, listing path uses extract_flat + skip_download + playlist_items
  - Cookies are honored on the listing path too — some channels may require auth even for public listing
  - Skip entries without an id silently — some extractors return null entries for hidden/private content within a public channel feed
  - Fallback URL construction `https://www.youtube.com/watch?v={id}` for entries that lack webpage_url — covers TikTok and Instagram extractors which behave differently from YouTube
duration: 
verification_result: passed
completed_at: 2026-04-07T17:49:01.483Z
blocker_discovered: false
---

# T03: Implemented YtdlpDownloader.list_channel_videos using yt-dlp's extract_flat=True. 7 new tests, 398 total green, 4 quality gates clean, YtdlpDownloader now conforms to the extended Downloader Protocol.

**Implemented YtdlpDownloader.list_channel_videos using yt-dlp's extract_flat=True. 7 new tests, 398 total green, 4 quality gates clean, YtdlpDownloader now conforms to the extended Downloader Protocol.**

## What Happened

Added the `list_channel_videos(url, limit=10)` method to YtdlpDownloader. The implementation uses yt-dlp's `extract_flat=True` mode which returns a flat list of entries with just IDs and URLs — no metadata fetch, no download. This is the cheap-listing path the watchlist refresh loop will use.

**Implementation details:**
- Builds a separate options dict (different from `_build_options` which is for downloads): `extract_flat=True`, `playlist_items=f"1-{limit}"`, `skip_download=True`, plus the same `quiet`/`no_warnings`/`noprogress` flags as the download path
- Honors the cookies file if configured (same `cookiefile` option as the download path)
- Catches DownloadError, ExtractorError, and the unexpected-Exception fallback — same translation pattern as `download()`
- Returns a list of `ChannelEntry` (the new DTO from the ports layer) with `platform_id` and `url` populated
- Falls back to `f"https://www.youtube.com/watch?v={raw_id}"` when the entry lacks `webpage_url` AND `url` (some flat extracts only return ids)
- Skips entries without an `id` field gracefully

**7 new tests** in `TestListChannelVideos`:
- `_ListCapturingFake` helper class that records the options dict passed to `yt_dlp.YoutubeDL` so tests can assert the right flags
- Returns ChannelEntry list (3 entries → 3 ChannelEntry, ids preserved, URLs preserved)
- Passes `extract_flat=True` and `playlist_items='1-N'` correctly
- limit caps the returned entries (10 entries, limit=5 → 5 returned)
- Empty URL raises IngestError("empty")
- None info raises IngestError("no metadata")
- DownloadError is translated via the existing `_translate_download_error` helper
- Skips entries without an id (mixed list of valid + invalid → only valid returned)

**Quality gate status after T03:**
- 398 unit tests pass
- mypy strict: clean on 72 source files (the protocol mismatch from T02 is gone now that YtdlpDownloader implements `list_channel_videos`)
- ruff: 12 auto-fixes for unused imports and minor formatting in the test additions
- lint-imports: 8 contracts kept

S01 is now complete: domain entities + ports + SQLite repositories + adapter listing method. S02 will use these to build the WatchRefreshUseCase + CLI.

## Verification

Ran `python -m uv run pytest tests/unit/adapters/ytdlp -q` → 30 passed (23 existing + 7 new). Ran full suite → 398 passed, 5 deselected. All 4 quality gates clean after 12 ruff auto-fixes. mypy strict no longer flags YtdlpDownloader because it now exposes list_channel_videos.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters/ytdlp -q` | 0 | ✅ 30/30 ytdlp tests green (7 new for list_channel_videos) | 190ms |
| 2 | `python -m uv run pytest -q && ruff + mypy + lint-imports` | 0 | ✅ 398/398 unit tests, all 4 quality gates clean | 5000ms |

## Deviations

None.

## Known Issues

Real network validation of `list_channel_videos` happens in S03 via the live integration test (the @YouTube channel listing already validated that the approach works in <0.6s).

## Files Created/Modified

- `src/vidscope/adapters/ytdlp/downloader.py`
- `tests/unit/adapters/ytdlp/test_downloader.py`
