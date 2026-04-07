---
id: T01
parent: S02
milestone: M005
key_files:
  - src/vidscope/ports/pipeline.py
  - src/vidscope/ports/__init__.py
  - src/vidscope/domain/errors.py
  - src/vidscope/domain/__init__.py
  - src/vidscope/adapters/ytdlp/downloader.py
  - src/vidscope/application/cookies.py
  - src/vidscope/cli/commands/cookies.py
  - tests/unit/ports/test_protocols.py
  - tests/unit/application/test_cookies.py
  - tests/unit/cli/test_cookies.py
  - tests/unit/adapters/ytdlp/test_downloader.py
key_decisions:
  - CookieAuthError subclasses IngestError so existing pipeline error handling continues to work
  - Downloader.probe never raises — every failure encoded in ProbeResult.status
  - Renamed Test* prefixed classes to avoid pytest collection warnings
  - Default probe URL is a stable Instagram public Reel — the platform priority per D027 — with --url override available
  - 10-element cookie auth marker tuple covers Instagram, YouTube, TikTok auth phrasings
  - _translate_probe_error and _translate_download_error share the same _is_cookie_auth_error helper — single source of truth for what counts as a cookie failure
  - Interpretation message is context-aware: cookies_configured × status → specific actionable advice
duration: 
verification_result: passed
completed_at: 2026-04-07T19:00:15.696Z
blocker_discovered: false
---

# T01: Shipped vidscope cookies test (probe) + CookieAuthError typed domain error + Downloader.probe port method + ytdlp adapter detection of cookie auth failures. 9 contracts kept, 618 unit tests, all 4 gates clean.

**Shipped vidscope cookies test (probe) + CookieAuthError typed domain error + Downloader.probe port method + ytdlp adapter detection of cookie auth failures. 9 contracts kept, 618 unit tests, all 4 gates clean.**

## What Happened

**Combined S02's two planned tasks into one delivery** because the shape was clear: extending the Downloader port + the adapter + adding the use case + adding the CLI command + writing tests is a single coherent unit.

**Port extension** (`src/vidscope/ports/pipeline.py`):
- Added `ProbeResult` frozen dataclass with `status`, `url`, `detail`, `title`
- Added `ProbeStatus` StrEnum: `OK`, `AUTH_REQUIRED`, `NOT_FOUND`, `NETWORK_ERROR`, `UNSUPPORTED`, `ERROR`
- Added `Downloader.probe(url) -> ProbeResult` Protocol method documented as "never raises — every failure is encoded in the returned ProbeResult's status field"
- Re-exported `ProbeResult` + `ProbeStatus` from `vidscope.ports.__init__`
- Updated `tests/unit/ports/test_protocols.py` to assert `Downloader` has the `probe` attribute

**Domain error** (`src/vidscope/domain/errors.py`):
- Added `CookieAuthError(IngestError)` with `default_retryable = False` and an extra `url` attribute
- Re-exported from `vidscope.domain.__init__`
- Subclassing `IngestError` means existing pipeline error handling continues to work — the runner records it, the typed dispatch stays clean, and the CLI's `handle_domain_errors` context manager catches it

**ytdlp adapter implementation** (`src/vidscope/adapters/ytdlp/downloader.py`):
- New `_COOKIE_AUTH_MARKERS` tuple with 10 case-insensitive substrings: `login required`, `cookies needed`, `use --cookies`, `rate-limit reached`, `this content isn't available`, `this video is private`, `sign in to confirm`, `requires login`, `restricted video`, `age-restricted`
- New `_is_cookie_auth_error()` helper
- New `_translate_probe_error()` helper that maps yt-dlp exceptions to ProbeStatus values (auth → AUTH_REQUIRED, unsupported → UNSUPPORTED, video unavailable → NOT_FOUND, network words → NETWORK_ERROR, else → ERROR)
- Updated `_translate_download_error` and `_translate_extractor_error` to detect auth markers and raise `CookieAuthError` (with the actionable message `"cookies missing or expired. Run vidscope cookies test <url> to verify your cookies."`) instead of generic IngestError
- New `YtdlpDownloader.probe(url)` method: builds an extract_info call with `download=False` + `skip_download=True`, catches DownloadError/ExtractorError/anything, returns the appropriate ProbeResult. Never raises.

**Application use case** (`src/vidscope/application/cookies.py`):
- Added `CookiesProbeResult` (renamed from TestCookiesResult to avoid pytest collection warning) and `CookiesProbeUseCase` (renamed from TestCookiesUseCase same reason)
- Constructor takes `downloader: Downloader` + `cookies_configured: bool`
- `execute(url)` calls `downloader.probe(url or _DEFAULT_PROBE_URL)` and produces a human-readable interpretation based on the status × cookies_configured combination
- Default URL is a stable Instagram public Reel; the user can override with `--url`
- Interpretation distinguishes "cookies work" vs "no cookies needed" on OK, and "expired" vs "install" on AUTH_REQUIRED — context-aware so the user knows exactly what action to take

**CLI command** (`src/vidscope/cli/commands/cookies.py`):
- New `vidscope cookies test [--url URL]` subcommand
- Builds the use case via the container, passes `cookies_configured = (config.cookies_file is not None)`
- Prints URL + status + detail + interpretation with rich color coding (green for OK, yellow for AUTH_REQUIRED/NOT_FOUND/NETWORK_ERROR, red for UNSUPPORTED/ERROR)
- Exits with code 1 (user error) when status != OK so scripts can detect failures

**Tests** (54 new):
- `tests/unit/application/test_cookies.py`: `TestCookiesProbe` class with 8 tests covering OK with/without cookies, AUTH_REQUIRED with/without cookies, NOT_FOUND, NETWORK_ERROR, UNSUPPORTED, default URL fallback
- `tests/unit/cli/test_cookies.py`: `TestCookiesProbe` class with 3 tests covering OK exit code, AUTH_REQUIRED exit code 1, default URL is Instagram. Stubs `YtdlpDownloader.probe` directly.
- `tests/unit/adapters/ytdlp/test_downloader.py`: `TestCookieAuthDetection` class (3 tests for the auth marker detection in download paths) + `TestProbe` class (6 tests for the probe method covering OK with title, empty URL, AUTH_REQUIRED, UNSUPPORTED, NOT_FOUND, unexpected exception)

**Pytest collection warning surfaced and fixed**: original use case names `TestCookiesUseCase` and `TestCookiesResult` triggered pytest's collection of any class starting with `Test`. Renamed to `CookiesProbeUseCase` and `CookiesProbeResult` — better names anyway because the action is "probe" not "test".

**Quality gates after S02**:
- ✅ pytest: **618 passed**, 5 deselected, in 14.96s (was 598 before S02, +20)
- ✅ mypy strict: **84 source files** OK
- ✅ ruff: clean (6 ruff B/F errors auto-fixed, 1 PLR0911 noqa for the 8-state interpretation method)
- ✅ lint-imports: **9 contracts kept**, 0 broken

## Verification

All 4 quality gates clean: pytest 618 passed in 14.96s, mypy 84 source files OK, ruff clean (after auto-fix + 1 noqa), lint-imports 9 contracts kept.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest -q` | 0 | ✅ 618 passed | 14960ms |
| 2 | `python -m uv run mypy src` | 0 | ✅ 84 source files OK | 2100ms |
| 3 | `python -m uv run lint-imports` | 0 | ✅ 9 contracts kept | 2100ms |
| 4 | `python -m uv run ruff check .` | 0 | ✅ all checks passed | 800ms |

## Deviations

**Renamed `TestCookiesUseCase` → `CookiesProbeUseCase` and `TestCookiesResult` → `CookiesProbeResult`** because pytest tried to collect them as test classes (any class starting with `Test`). The new names are more accurate anyway — the action is "probe", not "test". Also delivered S02 in one task instead of the planned T01+T02 split because the shape was clear and the work was tightly coupled.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/ports/pipeline.py`
- `src/vidscope/ports/__init__.py`
- `src/vidscope/domain/errors.py`
- `src/vidscope/domain/__init__.py`
- `src/vidscope/adapters/ytdlp/downloader.py`
- `src/vidscope/application/cookies.py`
- `src/vidscope/cli/commands/cookies.py`
- `tests/unit/ports/test_protocols.py`
- `tests/unit/application/test_cookies.py`
- `tests/unit/cli/test_cookies.py`
- `tests/unit/adapters/ytdlp/test_downloader.py`
