---
id: T05
parent: S07
milestone: M001
key_files:
  - tests/integration/test_ingest_live.py
key_decisions:
  - Class order in the source file matches platform priority (Instagram first, YouTube last) so pytest collection order matches user priority — the most important platform's status is the first thing operators see in the test output
  - `_cookies_file_available()` reads VIDSCOPE_COOKIES_FILE directly from os.environ instead of going through the config layer — simpler and avoids any caching subtlety at test-time
  - Three-layer xfail logic for Instagram with cookies: retryable → xfail (transient), login/cookies/auth in error text → xfail (stale cookies, with re-export remediation), anything else → real failure. Documents the distinction between 'upstream broke' and 'user did something wrong'
  - Instagram xfails BEFORE making any network call when cookies are absent — saves test runtime and gives a deterministic, fast 'cookies needed' signal
  - URL constants reordered to match priority order so the source file is visually consistent with the runtime behavior
  - Module docstring includes step-by-step cookies export instructions for Firefox and Chrome — anyone who reads the test knows exactly how to enable Instagram without leaving the file
duration: 
verification_result: passed
completed_at: 2026-04-07T13:51:05.721Z
blocker_discovered: false
---

# T05: Reordered integration tests Instagram→TikTok→YouTube per D027, made Instagram conditionally xfail-or-pass based on VIDSCOPE_COOKIES_FILE — operators now see priority platform status first and have a clear path from xfail to passing.

**Reordered integration tests Instagram→TikTok→YouTube per D027, made Instagram conditionally xfail-or-pass based on VIDSCOPE_COOKIES_FILE — operators now see priority platform status first and have a clear path from xfail to passing.**

## What Happened

T05 makes the integration test file honest about VidScope's actual priorities. The previous version had the platforms in alphabetical order (Instagram → TikTok → YouTube by chance) but with three issues that mattered:

1. **The class order was alphabetical, not priority-driven.** YouTube was the first test to run and the first to pass, which sent the wrong signal about what mattered most.

2. **Instagram unconditionally xfailed.** Even if a user had cookies configured, the test would xfail because the production code didn't yet read cookies (S07 fixed that in T01-T04). The test had no way to flip from xfail to pass even when the user had done everything right.

3. **The xfail message was vague.** "Likely a yt-dlp extractor issue" was true but not actionable. The user couldn't tell if it was their problem to solve or upstream's.

**Three fixes:**

**Reordered classes Instagram → TikTok → YouTube.** The file now leads with `TestLiveInstagram`, then `TestLiveTikTok`, then `TestLiveYouTube`. Each class has its own `# ---` section header in the source so the priority order is visible at a glance. pytest collects them in the source order, so an operator running `pytest tests/integration -m integration -v` sees Instagram's status first.

**Conditional xfail-or-pass for Instagram via `_cookies_file_available()` helper.** The helper reads `VIDSCOPE_COOKIES_FILE` directly from `os.environ` (not via the config layer — the helper runs at test execution time, not collection time, but reading directly is simpler and avoids any caching subtlety). It returns the resolved Path if the env var is set AND the file exists, otherwise None.

The test logic:
- `cookies is None` → `pytest.xfail("Instagram requires cookie-based authentication...")` with explicit instructions on how to enable the test
- `cookies is set` → run the real ingest. If it fails with `IngestError(retryable=True)` → xfail (transient). If it fails with text containing "login" / "cookies" / "authentication" → xfail with "cookies may be stale" hint. Anything else → real failure that propagates.

**Three-layer xfail logic for Instagram with cookies.** When the user has opted in by exporting cookies, the test has to distinguish three failure modes:

1. **Retryable network/rate-limit** — transient, not the user's problem, xfail with the upstream error
2. **"login" / "cookies" / "authentication" in the error text** — the cookies file is stale (Instagram session expired), xfail with "re-export cookies" remediation
3. **Anything else** — a real bug or a real upstream regression that needs investigation; propagate as a real failure

This three-layer logic is documented in the test docstring so the next agent reading it understands why the simple `try: ... except IngestError: pytest.xfail(...)` pattern isn't enough.

**Updated module docstring.** Five new sections:
- "Tests are ordered by platform priority (D027): Instagram first, then TikTok, then YouTube"
- "Cookies and Instagram (S07/R025)" — explains the conditional behavior with concrete env var examples
- Step-by-step "To export cookies (one-time setup)" with browser extension names for Firefox and Chrome
- Pointer to `docs/cookies.md` (T06 will create it)
- Pointer to `scripts/verify-s07.sh` (T07 will create it) instead of the obsolete `verify-s02.sh`

**Reordered the URL constants** so the priority order is visible in the source: `INSTAGRAM_URL` first with a "PRIMARY platform per D027" comment, then `TIKTOK_URL`, then `YOUTUBE_URL`.

**Real run result on the dev machine** (no cookies configured):

```
tests/integration/test_ingest_live.py::TestLiveInstagram::test_ingests_instagram_reel XFAIL [ 33%]
tests/integration/test_ingest_live.py::TestLiveTikTok::test_ingests_tiktok_video PASSED [ 66%]
tests/integration/test_ingest_live.py::TestLiveYouTube::test_ingests_youtube_short PASSED [100%]
```

Instagram xfails fast (no network call — the helper checks cookies at the top of the test) with the explicit "Set VIDSCOPE_COOKIES_FILE to a Netscape-format cookies file..." message. Total runtime dropped from ~7s to ~2.5s because Instagram no longer wastes time attempting a download that will fail.

**Quality gates after T05:** 260 unit tests still passing (none touched), 4 quality gates clean. The integration test file is the only thing that changed.

## Verification

Ran `python -m uv run pytest tests/integration -m integration --collect-only -q` → confirms collection order is Instagram → TikTok → YouTube. Ran `python -m uv run pytest tests/integration -m integration -v` → 2 passed (TikTok, YouTube), 1 xfailed (Instagram with the new "requires cookie-based authentication" message), runtime 2.49s. Ran `python -m uv run pytest -q` → 260 passed, 3 deselected. Ran ruff/mypy/lint-imports → all clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/integration -m integration --collect-only -q` | 0 | ✅ collection order is Instagram → TikTok → YouTube | 30ms |
| 2 | `python -m uv run pytest tests/integration -m integration -v` | 0 | ✅ pass — 2 passed (TikTok, YouTube), 1 xfailed (Instagram, no cookies), runtime 2.49s | 2490ms |
| 3 | `python -m uv run pytest -q && python -m uv run ruff check src tests && python -m uv run mypy src && python -m uv run lint-imports` | 0 | ✅ pass — 260 unit tests, 4 gates clean | 5000ms |

## Deviations

None. The plan asked for reordering, conditional xfail/pass based on env var, and clear cookies instructions in the docstring. All delivered, plus a more nuanced three-layer xfail logic for the case where cookies are set but Instagram still rejects them (stale session vs transient vs real bug).

## Known Issues

The test file references `scripts/verify-s07.sh` and `docs/cookies.md` which T06 and T07 will create. References are forward — they're real paths that will exist by the time anyone reads the test, no immediate breakage.

## Files Created/Modified

- `tests/integration/test_ingest_live.py`
