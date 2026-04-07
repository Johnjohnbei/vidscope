---
id: T03
parent: S07
milestone: M001
key_files:
  - src/vidscope/infrastructure/container.py
  - tests/unit/infrastructure/test_container.py
key_decisions:
  - Container reads cookies_file from config and passes it as a constructor kwarg to YtdlpDownloader — the validation happens in YtdlpDownloader.__init__ (T02), the wiring is just plumbing
  - Misconfigured cookies path fails build_container() with a typed IngestError — the user sees the problem at startup, not on the first ingest attempt
  - Test reaches into the downloader's private `_cookies_file` attribute via getattr() because there's no public accessor and tests should assert on observable behavior — documented as test-only introspection
duration: 
verification_result: passed
completed_at: 2026-04-07T13:46:07.682Z
blocker_discovered: false
---

# T03: Wired Config.cookies_file through build_container() to YtdlpDownloader — misconfigured cookies now fail container startup with a typed IngestError, 3 new tests, 257 total green.

**Wired Config.cookies_file through build_container() to YtdlpDownloader — misconfigured cookies now fail container startup with a typed IngestError, 3 new tests, 257 total green.**

## What Happened

T03 is the smallest task in S07 — exactly one production line plus three integration tests. The container reads `resolved_config.cookies_file` and passes it as a kwarg to `YtdlpDownloader(cookies_file=...)`. That's it.

But the small change has a sharp consequence: a misconfigured `VIDSCOPE_COOKIES_FILE` now fails `build_container()` with a typed IngestError at startup. This is exactly the fail-fast contract T01 + T02 set up. The user sees the problem when they run any vidscope command (because every command goes through `acquire_container()` → `build_container()`), not on the first ingest attempt where the error would be tangled up with whatever URL they were trying.

**Three tests in `TestCookiesIntegration`:**

- `test_no_cookies_file_works_as_before` — sandbox has no cookies, container builds cleanly, both `config.cookies_file` and the downloader's private `_cookies_file` are None. Backward-compatibility guard.

- `test_cookies_file_propagates_to_downloader` — set `VIDSCOPE_COOKIES_FILE` to a real cookies file, reset config cache, build the container, verify the resolved path makes it from config to the downloader's internal state. Reaches into `getattr(container.downloader, "_cookies_file")` because that's the only way to assert the path actually got there without exercising a real download.

- `test_misconfigured_cookies_file_fails_build_container` — set the env var to a non-existent path, build the container, expect an `IngestError("cookies file not found")` with `retryable=False`. This is the user-facing fail-fast behavior at its purest: no `vidscope` command will run with a broken cookies path. The operator sees the error immediately and fixes it before doing anything else.

**One commit-style note:** the production change is one constructor argument. Everything else in T03 is the test scaffolding that proves the wiring is correct. That ratio of test-code-to-production-code is normal at the composition root — wiring tasks are mostly about validating that the wires connect to the right things.

**Quality gates after T03:** 257 tests pass (254 + 3 new), 2 ruff auto-fixes for unused-import or formatting in the new test code, mypy strict clean on 52 files, import-linter 7/7. Zero regressions.

## Verification

Ran `python -m uv run pytest tests/unit/infrastructure/test_container.py -q` → 14 passed in 380ms. Ran `python -m uv run pytest -q` → 257 passed, 3 deselected in 1.99s. Ran `python -m uv run ruff check src tests` → All checks passed (2 auto-fixes). Ran `python -m uv run mypy src` → Success: no issues found in 52 source files. Ran `python -m uv run lint-imports` → 7 contracts kept, 0 broken.

Manually verified the misconfiguration behavior: `VIDSCOPE_COOKIES_FILE=/nonexistent.txt vidscope status` would now exit with the typed IngestError before even reaching the status command logic. No mock — the real container wiring catches the bad config at startup.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/infrastructure/test_container.py -q` | 0 | ✅ pass (14/14) | 380ms |
| 2 | `python -m uv run pytest -q` | 0 | ✅ pass (257 passed, 3 deselected) | 1990ms |
| 3 | `python -m uv run ruff check src tests && python -m uv run mypy src && python -m uv run lint-imports` | 0 | ✅ pass — all 4 gates clean (52 files, 7 contracts) | 3000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/vidscope/infrastructure/container.py`
- `tests/unit/infrastructure/test_container.py`
