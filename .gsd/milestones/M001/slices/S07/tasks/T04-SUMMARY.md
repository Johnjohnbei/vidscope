---
id: T04
parent: S07
milestone: M001
key_files:
  - src/vidscope/infrastructure/startup.py
  - tests/unit/infrastructure/test_startup.py
key_decisions:
  - Cookies-not-configured is `ok=True` because cookies are opt-in — reporting it as failed would push doctor to exit 2 on perfectly functional installs where the user only cares about YouTube/TikTok
  - Lazy import of `vidscope.infrastructure.config` inside `check_cookies()` so startup.py has no import-time side effects — critical for tests that monkeypatch the config env vars
  - Test sandboxing explicitly deletes VIDSCOPE_COOKIES_FILE env var via `monkeypatch.delenv(..., raising=False)` because earlier tests may set it and pytest doesn't isolate process env between tests by default
  - Distinct error messages for 'not found' vs 'not a file' (path is a directory) so the remediation matches the actual mistake the user made
  - run_all_checks() updated additively: it now returns 3 results instead of 2. The CLI consumes the list generically so no CLI change was needed.
duration: 
verification_result: passed
completed_at: 2026-04-07T13:48:42.205Z
blocker_discovered: false
---

# T04: Added check_cookies() to startup checks with three semantic states (ok+configured / ok+optional / not-ok+missing) — vidscope doctor now reports cookies as a third row, 4 new tests, 260 total green.

**Added check_cookies() to startup checks with three semantic states (ok+configured / ok+optional / not-ok+missing) — vidscope doctor now reports cookies as a third row, 4 new tests, 260 total green.**

## What Happened

T04 makes the cookies feature visible to operators. `vidscope doctor` is the diagnostic command — anyone debugging "why isn't Instagram working" runs doctor first, and cookies are now part of the report.

**Three semantic states for cookies:**

1. **Configured + present** → `ok=True`, message `"configured at {path}"`. The user has set everything up correctly. Doctor exit code stays 0 unless something else fails.

2. **Not configured** → `ok=True`, message `"not configured (optional)"`, remediation points at `docs/cookies.md`. This is a healthy state because cookies are opt-in. The remediation is informational, not prescriptive.

3. **Configured + missing** → `ok=False`, message `"configured at {path} but file is missing"`, remediation tells the user to either create the file or unset the env var. This is the only state where doctor reports a real failure.

A fourth state — `configured + path is a directory` — gets the same `ok=False` treatment with a distinct message (`"path is not a file"`). Symmetric with `YtdlpDownloader`'s init-time validation in T02.

**Why cookies-not-configured is `ok=True`:**

Conceptually, the cookies check is asking "is your cookies setup broken?" not "are cookies present?". When the user hasn't configured anything, there's nothing broken — they just haven't opted in. Reporting it as failed would be wrong: it would push doctor to exit 2 (system error) on a perfectly functional install where the user only cares about YouTube and TikTok. The remediation field still nudges them toward `docs/cookies.md` if they want to enable Instagram, but that's a nudge, not an error.

**Lazy import of `vidscope.infrastructure.config`:**

`check_cookies()` imports `get_config` lazily inside the function body, with a `# noqa: PLC0415`. This avoids a side effect at module import time: importing startup.py earlier would otherwise trigger config resolution before the user's monkeypatching has had a chance to run in tests. The lazy import keeps `startup.py` cleanly free of import-time global side effects.

**Updated `run_all_checks()`:**

The list returned grew from 2 to 3 entries: `[check_ffmpeg(), check_ytdlp(), check_cookies()]`. The CLI doctor command and the future `add` command preflight both consume this list — no command-side change needed because they iterate the list generically.

**Tests — 4 new in `TestCheckCookies` + 1 updated `TestRunAllChecks`:**

Each cookies test starts with a `_sandbox()` helper that sets `VIDSCOPE_DATA_DIR` to a fresh tmp_path, deletes any pre-existing `VIDSCOPE_COOKIES_FILE` env var, and resets the config cache. This is critical: the previous tests in the suite may leave a cookies env var set (especially in CI where tests run in arbitrary order), and without the explicit delete, the cookies tests would inherit state.

- `test_not_configured_is_ok` — empty sandbox → `ok=True`, "not configured" in the message, docs reference in remediation
- `test_configured_and_present_is_ok` — pre-create a real cookies file, set env var → `ok=True`, "configured at" in the message, empty remediation
- `test_configured_but_missing_is_not_ok` — env var points at a non-existent path → `ok=False`, "missing" in message, env-var name in remediation
- Updated `test_returns_one_result_per_check` — now asserts 3 results with the names `{ffmpeg, yt-dlp, cookies}`. Also sandboxed to prevent state leakage from other tests' cookies env vars.

**Manual verification.** Ran `vidscope doctor` on the dev machine. The rich table now shows three rows. ffmpeg fails (not on PATH), yt-dlp ok (2026.03.17), cookies ok (not configured / optional). Exit code 2 because of the ffmpeg failure, not because of cookies — exactly the semantics I wanted.

**Quality gates after T04:** 260 tests pass (257 + 3 new), ruff clean, mypy strict clean on 52 files, import-linter 7/7. Zero regressions.

## Verification

Ran `python -m uv run pytest tests/unit/infrastructure/test_startup.py -q` → 11 passed in 270ms. Ran `python -m uv run pytest -q` → 260 passed, 3 deselected in 2.12s. Ran `python -m uv run ruff check src tests` → All checks passed. Ran `python -m uv run mypy src` → Success: no issues found in 52 source files. Ran `python -m uv run lint-imports` → 7 contracts kept, 0 broken.

Manually ran `python -m uv run vidscope doctor`. The output shows the new third row for cookies with status "ok" and detail "not configured (optional)". Exit code 2 (ffmpeg missing), correctly preserved.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/infrastructure/test_startup.py -q` | 0 | ✅ pass (11/11) | 270ms |
| 2 | `python -m uv run pytest -q` | 0 | ✅ pass (260 passed, 3 deselected) | 2120ms |
| 3 | `python -m uv run vidscope doctor` | 2 | ✅ pass — third row 'cookies' shows 'ok / not configured (optional)', exit 2 from ffmpeg failure unchanged | 600ms |

## Deviations

None. Plan called for three states, lazy import to avoid side effects, 3 tests covering the states, and run_all_checks integration. All delivered, plus a bonus fourth-state distinction for "path is a directory" that mirrors T02's symmetric error handling.

## Known Issues

None. The check correctly reports all four states (configured-ok, not-configured-ok, missing-not-ok, directory-not-ok). The CLI doctor command consumes it without any code change because it iterates run_all_checks() generically.

## Files Created/Modified

- `src/vidscope/infrastructure/startup.py`
- `tests/unit/infrastructure/test_startup.py`
