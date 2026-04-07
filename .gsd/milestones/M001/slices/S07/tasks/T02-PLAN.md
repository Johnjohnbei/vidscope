---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T02: YtdlpDownloader: optional cookies_file parameter with init-time validation

Update src/vidscope/adapters/ytdlp/downloader.py: __init__ accepts a new optional `cookies_file: Path | None = None` keyword argument. When provided AND the file exists, store it as self._cookies_file. When provided BUT the file does NOT exist, raise IngestError('cookies file not found: {path}', retryable=False) at init time — fail fast, not at the first download. _build_options() adds `cookiefile=str(self._cookies_file)` to the yt-dlp options dict when cookies are configured. Tests in tests/unit/adapters/ytdlp/test_downloader.py: 4 new tests covering (1) no cookies (default), (2) cookies path provided + file exists → cookiefile in options, (3) cookies path provided + file missing → IngestError at init, (4) cookiefile flag actually appears in the FakeYoutubeDL options dict via stub assertion.

## Inputs

- ``src/vidscope/adapters/ytdlp/downloader.py` — existing class`
- ``src/vidscope/domain/errors.py` — IngestError`

## Expected Output

- ``src/vidscope/adapters/ytdlp/downloader.py` — cookies_file parameter, init-time validation, _build_options uses it`
- ``tests/unit/adapters/ytdlp/test_downloader.py` — 4 new tests covering the cookies paths`

## Verification

python -m uv run pytest tests/unit/adapters/ytdlp -q
