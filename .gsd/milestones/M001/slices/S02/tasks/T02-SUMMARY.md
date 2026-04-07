---
id: T02
parent: S02
milestone: M001
key_files:
  - src/vidscope/domain/platform_detection.py
  - src/vidscope/domain/__init__.py
  - tests/unit/domain/test_platform_detection.py
  - pyproject.toml
key_decisions:
  - Platform detection lives in `vidscope.domain`, not in the yt-dlp adapter — multiple callers (ingest stage, CLI, future search) need it and none should have to know about yt-dlp's extractor vocabulary
  - Stdlib-only implementation (`urllib.parse`) so the domain layer's zero-third-party-deps invariant stays intact (verified by import-linter)
  - Suffix match with a guarded `endswith('.suffix')` check so `evilyoutube.com` cannot impersonate YouTube — tested explicitly
  - Scheme validation explicitly rejects `javascript:`, `file://`, `ftp://` upfront so a future CLI that takes URL input from untrusted sources won't call yt-dlp with a poisonous URL
  - Error messages list the supported platforms so operators see what's allowed without reading docs
  - All detection errors are `retryable=False` because URL issues never self-heal — encoded in the error, not left to the runner to guess
duration: 
verification_result: passed
completed_at: 2026-04-07T11:54:07.202Z
blocker_discovered: false
---

# T02: Shipped detect_platform() in the domain layer: URL → Platform enum with stdlib-only parsing, suffix matching, and typed error rejection — 29 tests, 229 total green, all gates clean.

**Shipped detect_platform() in the domain layer: URL → Platform enum with stdlib-only parsing, suffix matching, and typed error rejection — 29 tests, 229 total green, all gates clean.**

## What Happened

Short but important task. Platform detection lives in the domain layer (not in the yt-dlp adapter) because it's a business concept that multiple callers need: the ingest stage consults it before handing a URL to the downloader, the CLI uses it for display formatting, and the search index will use it later to filter results by platform. Putting it in an adapter would have leaked yt-dlp's extractor-name vocabulary into the business logic.

**src/vidscope/domain/platform_detection.py** — One function, `detect_platform(url: str) -> Platform`. Zero third-party imports, only `urllib.parse` from the stdlib. Three safety layers before the suffix match:
1. Null / empty / whitespace rejection with `IngestError("url is empty")`
2. `urlparse()` wrapped in try/except so truly malformed input becomes a typed error instead of a crash
3. Scheme validation: only `http` and `https` are accepted. `javascript:`, `file://`, `ftp://`, and bare words all get rejected with a clear message naming the offending scheme.

The suffix match uses a tuple of `(host_suffix, Platform)` pairs and checks `host == suffix or host.endswith(f".{suffix}")`. That second check is critical: it matches `www.youtube.com`, `m.youtube.com`, `music.youtube.com` without enumerating every subdomain, AND it rejects `evilyoutube.com` (which only looks like a suffix but isn't a subdomain). I tested that lookalike case explicitly — it's the kind of attack that someone could try if the URL parser is ever exposed to untrusted input.

Error messages include the list of supported platforms so operators see what they need to name correctly. Every error is `retryable=False` because URL issues never self-heal — the pipeline runner shouldn't retry a malformed URL on the next pass.

**Updated `src/vidscope/domain/__init__.py`** to re-export `detect_platform` alongside the other domain helpers, grouped under a new `# helpers` section in `__all__`. The `# noqa: RUF022` comment preserves the concern-based grouping over strict alphabetical sort.

**Tests — 29 in `tests/unit/domain/test_platform_detection.py`:**

- `TestYouTube` (8): parametrized over 7 URL shapes (`youtube.com`, `youtu.be`, `m.youtube.com`, `music.youtube.com`, `youtube.com/shorts/`, http not just https) plus a case-insensitive host test (`WWW.YouTube.com`).
- `TestTikTok` (4): parametrized over `www.tiktok.com`, `tiktok.com`, `m.tiktok.com`, `vm.tiktok.com`.
- `TestInstagram` (3): parametrized over reel URLs, post URLs (`/p/`), and story URLs (`/stories/`).
- `TestRejections` (12): empty, whitespace, None (typed ignore), javascript:, file://, ftp://, bare word, vimeo.com (unsupported), dailymotion.com (unsupported), subdomain of unsupported (`video.example.com`), error message lists supported platforms, lookalike host (`evilyoutube.com`) rejected.
- `TestErrorProperties` (2): all errors are `retryable=False` and carry `stage=StageName.INGEST`.

**Gate fixes done in-task:**
- Ruff flagged an unsorted import block in the new ytdlp test file → auto-fix applied.
- mypy complained about missing stubs for `yt_dlp.utils` → added to the `ignore_missing_imports` override in pyproject.toml (previously only `yt_dlp` itself was listed).

**Full suite after T02:** 229/229 unit tests pass in 1.36s. Ruff clean, mypy strict clean on 50 source files (up from 47 with the new T01/T02 files), import-linter 7/7.

## Verification

Ran `python -m uv run pytest tests/unit/domain/test_platform_detection.py -q` → 29 passed in 70ms. Ran `python -m uv run pytest tests/unit -q` → 229 passed in 1.36s. Ran `python -m uv run ruff check src tests` → All checks passed. Ran `python -m uv run mypy src` → Success: no issues found in 50 source files. Ran `python -m uv run lint-imports` → Contracts: 7 kept, 0 broken. Manually verified the domain package imports via `python -m uv run python -c "from vidscope.domain import detect_platform, Platform, IngestError; assert detect_platform('https://www.youtube.com/watch?v=x') is Platform.YOUTUBE; print('ok')"` → ok.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/domain/test_platform_detection.py -q` | 0 | ✅ pass (29/29) | 70ms |
| 2 | `python -m uv run pytest tests/unit -q` | 0 | ✅ pass (229/229) | 1360ms |
| 3 | `python -m uv run ruff check src tests && python -m uv run mypy src && python -m uv run lint-imports` | 0 | ✅ pass — all 4 gates clean (50 source files, 7 contracts) | 2000ms |

## Deviations

None.

## Known Issues

None. The function is pure Python, fully tested, and integrates cleanly with the existing domain layer.

## Files Created/Modified

- `src/vidscope/domain/platform_detection.py`
- `src/vidscope/domain/__init__.py`
- `tests/unit/domain/test_platform_detection.py`
- `pyproject.toml`
