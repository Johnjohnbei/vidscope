---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: Container wiring: pass config.cookies_file to YtdlpDownloader

Update src/vidscope/infrastructure/container.py to read config.cookies_file and pass it to YtdlpDownloader(cookies_file=...). No new container fields needed — the cookies_file already lives in config, the downloader consumes it directly. This means a misconfigured cookies file fails build_container() at startup (loud and early). Tests in tests/unit/infrastructure/test_container.py: 2 new tests covering (1) build_container with no cookies works as before, (2) build_container with VIDSCOPE_COOKIES_FILE set to an existing tmp file builds successfully and the resulting downloader has the cookies path set.

## Inputs

- ``src/vidscope/infrastructure/container.py``
- ``src/vidscope/adapters/ytdlp/downloader.py` — updated by T02`

## Expected Output

- ``src/vidscope/infrastructure/container.py` — build_container passes cookies_file to YtdlpDownloader`
- ``tests/unit/infrastructure/test_container.py` — 2 new tests`

## Verification

python -m uv run pytest tests/unit/infrastructure/test_container.py -q
