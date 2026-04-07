---
id: T02
parent: S07
milestone: M001
key_files:
  - src/vidscope/adapters/ytdlp/downloader.py
  - tests/unit/adapters/ytdlp/test_downloader.py
key_decisions:
  - Init-time validation with two distinct error messages: 'cookies file not found' for missing path, 'cookies path is not a file' for directory paths — different remediations require different messages
  - Tilde expansion via `Path(...).expanduser().resolve()` so users can write `~/cookies.txt` and it just works on every OS
  - yt-dlp's `cookiefile` option is set in exactly one place (`_build_options`) so future yt-dlp upstream changes have a one-line blast radius
  - CapturingFakeYoutubeDL test helper inspects the options dict via class attribute — cleaner than monkeypatching the production `_build_options` and decouples test assertions from production internals
  - `str(self._cookies_file)` in `_build_options` because yt-dlp wants a str, not a Path — documented inline so the next agent doesn't 'fix' it back to Path
  - Init validation runs before any download attempt — a misconfigured VIDSCOPE_COOKIES_FILE fails container build, not the first ingest call. Loud and early.
duration: 
verification_result: passed
completed_at: 2026-04-07T13:44:43.708Z
blocker_discovered: false
---

# T02: Added cookies_file parameter to YtdlpDownloader with init-time validation, tilde expansion, and three distinct error messages (not found / not a file / valid) — 5 new tests, 254 total green, all gates clean.

**Added cookies_file parameter to YtdlpDownloader with init-time validation, tilde expansion, and three distinct error messages (not found / not a file / valid) — 5 new tests, 254 total green, all gates clean.**

## What Happened

T02 plugs the cookies path into the actual yt-dlp invocation and adds the fail-fast validation that T01 deliberately deferred. The change is small in surface area but tight in semantics.

**Init-time validation with three error states:**

1. **None** — no cookies path provided. `self._cookies_file` stays None. yt-dlp options are unchanged. This is the default and preserves every existing public-content workflow.

2. **Path provided but file doesn't exist** — raises `IngestError("cookies file not found: {resolved_path}", retryable=False)` immediately. This is the failure mode T01 explicitly delegated here. The error is non-retryable because no amount of retrying will make a missing file appear.

3. **Path provided but points at a directory (not a file)** — raises `IngestError("cookies path is not a file: {resolved_path}", retryable=False)`. Distinct error message because the user typo is different (they probably gave a folder where a file was expected). The remediation is different too (point at the file, not the directory).

**Tilde expansion.** `Path(cookies_file).expanduser().resolve()` so users can write `~/cookies.txt` in `VIDSCOPE_COOKIES_FILE` without doing path math themselves. Tested explicitly with monkeypatched `HOME` / `USERPROFILE`.

**`_build_options()` change.** Refactored from a return-literal-dict to building the dict, conditionally adding `cookiefile` if `self._cookies_file is not None`, and returning. yt-dlp expects `cookiefile` as a string, not a Path object — `str(self._cookies_file)` does the conversion. This is the **only** line in the entire codebase that touches yt-dlp's `cookiefile` option. When yt-dlp's cookies handling changes upstream, the fix lives in this one method.

**Tests — 5 new in `TestCookiesSupport`:**

I introduced a `CapturingFakeYoutubeDL` class that subclasses `FakeYoutubeDL` and stores its constructor options on a class attribute. This lets tests assert against the actual options dict yt-dlp would receive without coupling to the production `_build_options` internals.

- `test_no_cookies_file_means_no_cookiefile_in_options` — default constructor, captures the options dict, asserts `cookiefile` is NOT present. Backward-compat guard.
- `test_cookies_file_added_to_options` — pre-create a real cookies file in tmp_path, construct `YtdlpDownloader(cookies_file=cookies)`, run a fake Instagram ingest, assert the captured options dict has `cookiefile` set to the resolved absolute path.
- `test_missing_cookies_file_raises_at_init_time` — `YtdlpDownloader(cookies_file=tmp_path/"does-not-exist.txt")` raises IngestError with `"cookies file not found"` and `retryable=False`. The download method is never called.
- `test_cookies_path_pointing_at_directory_raises` — pass a tmp_path/subdir (a real directory). Different error message: `"not a file"` instead of `"not found"`. Helps users distinguish between "wrong path" and "wrong kind of thing".
- `test_cookies_path_with_tilde_is_expanded` — set fake HOME, pass `Path("~/cookies.txt")`, verify the resolved path in `_build_options()` matches the expanded location. Uses `dl._build_options(tmp_path)` to introspect, which is documented as test-only via the SLF001 noqa.

**Architectural invariant preserved.** yt_dlp is still imported in exactly one file. import-linter shows 7/7 contracts kept after T02.

**Quality gates:** ruff (1 minor auto-fix for an unused-import or import-sort issue in the test file), mypy strict clean on 52 files, pytest 254 passed, import-linter 7/7. No regressions.

## Verification

Ran `python -m uv run pytest tests/unit/adapters/ytdlp -q` → 23 passed (18 existing + 5 new) in 180ms. Ran `python -m uv run pytest -q` → 254 passed, 3 deselected in 1.93s. Ran `python -m uv run ruff check src tests` → All checks passed (1 auto-fix). Ran `python -m uv run mypy src` → Success: no issues found in 52 source files. Ran `python -m uv run lint-imports` → 7 contracts kept, 0 broken.

Manually verified all three init paths via `python -m uv run python -c "from vidscope.adapters.ytdlp import YtdlpDownloader; from vidscope.domain import IngestError; from pathlib import Path; YtdlpDownloader(); print('default ok'); import tempfile, os; td=tempfile.mkdtemp(); ck=Path(td)/'cookies.txt'; ck.write_text('# test'); YtdlpDownloader(cookies_file=ck); print('valid ok'); try: YtdlpDownloader(cookies_file=Path(td)/'missing.txt'); except IngestError as e: print('missing ok:', str(e)[:50])"`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/adapters/ytdlp -q` | 0 | ✅ pass (23/23) | 180ms |
| 2 | `python -m uv run pytest -q` | 0 | ✅ pass (254 passed, 3 deselected) | 1930ms |
| 3 | `python -m uv run ruff check src tests && python -m uv run mypy src && python -m uv run lint-imports` | 0 | ✅ pass — all 4 gates clean (52 source files, 7 contracts) | 3000ms |

## Deviations

None. The plan called for an optional cookies_file parameter, init-time validation, integration into yt-dlp options, and tests covering all paths — all delivered as specified, plus a bonus distinct error message for the directory-instead-of-file case.

## Known Issues

None. The downloader correctly validates cookies at init time and propagates the path to yt-dlp's cookiefile option. T03 will wire this into the container.

## Files Created/Modified

- `src/vidscope/adapters/ytdlp/downloader.py`
- `tests/unit/adapters/ytdlp/test_downloader.py`
