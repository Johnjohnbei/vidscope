---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: YtdlpDownloader adapter: wrap yt_dlp.YoutubeDL behind the Downloader port

Create src/vidscope/adapters/ytdlp/ with downloader.py implementing the Downloader Protocol from ports.pipeline. Uses `yt_dlp.YoutubeDL` with format='best[ext=mp4]/best' + outtmpl targeting a provided destination_dir. On success, returns an IngestOutcome with platform (detected from extractor), platform_id (from info_dict['id']), url (canonical), media_path (absolute path to the downloaded file), title, author (uploader), duration, upload_date (YYYYMMDD), view_count. On failure: catch `yt_dlp.utils.DownloadError`, `yt_dlp.utils.ExtractorError`, and generic Exception, translate each to IngestError with the original exception in `cause` and retryable=True for transient failures, retryable=False for 'unsupported URL' and 'video unavailable' errors. Module-level _platform_from_extractor() helper maps yt-dlp extractor names (youtube, tiktok, instagram) to the Platform enum. Unit tests monkeypatch yt_dlp.YoutubeDL with a fake class that returns a fake info_dict — zero real network calls in the unit tests.

## Inputs

- ``src/vidscope/ports/pipeline.py` — Downloader Protocol + IngestOutcome DTO`
- ``src/vidscope/domain/values.py` — Platform enum`
- ``src/vidscope/domain/errors.py` — IngestError`

## Expected Output

- ``src/vidscope/adapters/ytdlp/__init__.py` — package init with public re-export of YtdlpDownloader`
- ``src/vidscope/adapters/ytdlp/downloader.py` — YtdlpDownloader class + _platform_from_extractor helper + _info_to_outcome translator`
- ``tests/unit/adapters/ytdlp/test_downloader.py` — happy path (fake yt_dlp returning valid info), DownloadError translation, ExtractorError translation, missing info_dict fields, platform detection for youtube/tiktok/instagram`

## Verification

python -m uv run pytest tests/unit/adapters/ytdlp -q && python -m uv run python -c "from vidscope.adapters.ytdlp import YtdlpDownloader; from vidscope.ports import Downloader; assert issubclass(YtdlpDownloader, object); print('ok')"
