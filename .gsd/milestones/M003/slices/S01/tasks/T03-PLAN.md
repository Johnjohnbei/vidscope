---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: YtdlpDownloader.list_channel_videos implementation

Add a `list_channel_videos(url, limit=10)` method to YtdlpDownloader that wraps yt_dlp with extract_flat=True + playlist_items='1-{limit}'. Returns a list of ChannelEntry tuples (platform_id, url). Catches yt-dlp exceptions and translates to IngestError. Tests stub yt_dlp.YoutubeDL and verify the options dict + the return shape.

## Inputs

- ``src/vidscope/adapters/ytdlp/downloader.py``

## Expected Output

- `list_channel_videos method + tests`

## Verification

python -m uv run pytest tests/unit/adapters/ytdlp -q
