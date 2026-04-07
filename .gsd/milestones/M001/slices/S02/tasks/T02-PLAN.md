---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T02: Platform URL detection helper

Add src/vidscope/domain/platform_detection.py with a pure-Python function `detect_platform(url: str) -> Platform` that inspects the URL host and path to return the matching Platform enum value, or raises IngestError('unsupported platform URL: ...') for anything else. Supports: youtube.com, youtu.be, m.youtube.com, music.youtube.com -> YOUTUBE; tiktok.com, vm.tiktok.com, m.tiktok.com -> TIKTOK; instagram.com, www.instagram.com -> INSTAGRAM. Also validates the URL is a proper http(s):// URL (via urllib.parse, no third-party deps) and raises IngestError on malformed input. Unit tests cover every supported host + a handful of unsupported ones (vimeo, dailymotion, file://) + malformed URLs (empty, not-a-url, javascript:). Runs in milliseconds, zero I/O.

## Inputs

- ``src/vidscope/domain/values.py` — Platform enum`
- ``src/vidscope/domain/errors.py` — IngestError`

## Expected Output

- ``src/vidscope/domain/platform_detection.py` — detect_platform function with urllib.parse-based host matching`
- ``src/vidscope/domain/__init__.py` — re-exports detect_platform`
- ``tests/unit/domain/test_platform_detection.py` — parametrized tests covering every supported host + rejection cases`

## Verification

python -m uv run pytest tests/unit/domain/test_platform_detection.py -q && python -m uv run python -c "from vidscope.domain import detect_platform, Platform; assert detect_platform('https://www.youtube.com/watch?v=abc') is Platform.YOUTUBE; assert detect_platform('https://www.tiktok.com/@user/video/123') is Platform.TIKTOK; print('ok')"
