---
id: S02
parent: M005
milestone: M005
provides:
  - ProbeResult + ProbeStatus port types
  - CookieAuthError typed domain error
  - Downloader.probe Protocol method
  - vidscope cookies test CLI command
  - Cookie auth marker detection in vidscope add error path
requires:
  - slice: S01
    provides: CLI sub-application skeleton, validator helper, 3 use cases, and the architectural enforcement that application can't import infrastructure
affects:
  - S03: docs/cookies.md will document vidscope cookies test as the recommended verification step. verify-m005.sh will exercise the probe via stubbed downloader.
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
  - CookieAuthError subclasses IngestError — existing error handling continues to work
  - Downloader.probe never raises — always returns ProbeResult
  - Default probe URL is Instagram per D027 platform priority
  - Cookie auth markers list shared between download and probe paths — single source of truth
  - Class rename: TestCookies* → CookiesProbe* to avoid pytest collection warnings
  - Context-aware interpretation: cookies_configured × ProbeStatus → specific actionable message
patterns_established:
  - Probe pattern for verifying external service auth without performing the full operation — reusable for any future Downloader implementation
  - Typed domain error subclass with extra context attribute (CookieAuthError.url) for actionable CLI messages
  - Result-only port methods (Downloader.probe never raises) for diagnostic operations
observability_surfaces:
  - vidscope cookies test — status + detail + interpretation, exit code 1 on failure
  - CookieAuthError messages mention 'vidscope cookies test <url>' as remediation
  - Doctor's existing cookies row unchanged; the new test command provides on-demand verification
drill_down_paths:
  - .gsd/milestones/M005/slices/S02/tasks/T01-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T19:01:17.837Z
blocker_discovered: false
---

# S02: Cookies probe + typed CookieAuthError + better error remediation

**Shipped vidscope cookies test (probe) + CookieAuthError typed domain error + Downloader.probe port + ytdlp adapter detection. The cookies feature is now actually usable: users can verify their cookies work without ingesting a real video.**

## What Happened

S02 was the killer feature slice for M005 — the part that turns the cookies plumbing (M001/S07) and the CLI subcommands (M005/S01) into something users will actually trust.

Combined the planned T01+T02 into a single delivery because the work was tightly coupled and the shape was clear.

**The probe**: a metadata-only call through yt-dlp (`extract_info(url, download=False, skip_download=True)`) that fetches title + format list without downloading the media or writing anything to the database. Used by `vidscope cookies test` to verify that the configured cookies actually authenticate against Instagram (or any other gated platform).

**The typed error**: `CookieAuthError(IngestError)` with `default_retryable = False`. Subclassing IngestError means existing pipeline error handling continues to work — the runner records it, the typed dispatch stays clean, and the CLI's `handle_domain_errors` context manager catches it. The new subclass exists so the CLI can show a targeted remediation message pointing at `vidscope cookies test` instead of the generic ingest failure.

**The detection**: 10-element `_COOKIE_AUTH_MARKERS` tuple in the ytdlp adapter (`login required`, `cookies needed`, `use --cookies`, `sign in to confirm`, `requires login`, `restricted video`, `age-restricted`, etc). The `_translate_download_error` and `_translate_extractor_error` helpers check this list before falling back to generic IngestError. The same helper is used by `_translate_probe_error` so the probe and the download stage agree on what counts as a cookie failure.

**The interpretation**: `CookiesProbeUseCase` is context-aware about cookies_configured × probe_status. AUTH_REQUIRED with cookies configured → "your session has likely expired, re-export". AUTH_REQUIRED without cookies → "this URL requires cookies and none are configured, see docs/cookies.md". OK with cookies → "cookies work". OK without cookies → "no cookies needed". Each interpretation is one sentence the user can act on.

**The default URL**: a stable Instagram public Reel chosen because Instagram is the platform priority (D027) and Instagram is the platform that actually requires cookies. Users override with `--url` to test other platforms.

**Class rename**: `TestCookiesUseCase` and `TestCookiesResult` triggered pytest collection warnings (any class starting with `Test`). Renamed to `CookiesProbeUseCase` and `CookiesProbeResult` — better names anyway.

**Test count progression**: 598 (S01) → 618 (S02: +20). The probe + error detection is well covered by httpx-equivalent stubs (yt_dlp.YoutubeDL monkeypatched) so zero real network calls.

**No deviations from the plan**, just one positive consolidation (T01+T02 into one task) and one rename to dodge pytest collection.

## Verification

All 4 quality gates clean: pytest 618 passed in 14.96s, mypy 84 source files OK, ruff clean, lint-imports 9 contracts kept (including the existing llm-never-imports-other-adapters and the tightened application-has-no-adapters from S01).

## Requirements Advanced

- R025 — Cookies UX foundation completed: probe + typed error + actionable remediation. The cookies feature is now usable end-to-end. R025 will move to validated when M005 closes in S03.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Combined T01 + T02 into one delivery. Renamed `TestCookies*` classes to `CookiesProbe*` to avoid pytest collection warnings.

## Known Limitations

- The default probe URL is a hard-coded Instagram Reel that may eventually go dead. Users can override with --url. The verify-m005.sh script in S03 will test against a stubbed downloader, not the real network, so script-level URL rot is impossible.
- Cookie auth marker detection relies on substring matching against yt-dlp error messages. yt-dlp may change its error wording in future releases. The 10 markers cover all current 2026 phrasings but adding new ones is a one-line change in the adapter.

## Follow-ups

- S03: docs/cookies.md rewrite + verify-m005.sh + R025 validated + M005 closed

## Files Created/Modified

- `src/vidscope/ports/pipeline.py` — Added ProbeResult dataclass + ProbeStatus enum + Downloader.probe Protocol method
- `src/vidscope/ports/__init__.py` — Re-exported ProbeResult + ProbeStatus
- `src/vidscope/domain/errors.py` — Added CookieAuthError(IngestError)
- `src/vidscope/domain/__init__.py` — Re-exported CookieAuthError
- `src/vidscope/adapters/ytdlp/downloader.py` — Added _COOKIE_AUTH_MARKERS, _is_cookie_auth_error, _translate_probe_error, YtdlpDownloader.probe(), and CookieAuthError detection in _translate_download_error / _translate_extractor_error
- `src/vidscope/application/cookies.py` — Added CookiesProbeResult + CookiesProbeUseCase with context-aware interpretation
- `src/vidscope/cli/commands/cookies.py` — Added vidscope cookies test subcommand with rich color-coded output
- `tests/unit/ports/test_protocols.py` — Added probe to the Downloader Protocol method assertion
- `tests/unit/application/test_cookies.py` — Added _FakeDownloader stub + 8 TestCookiesProbe class tests
- `tests/unit/cli/test_cookies.py` — Added 3 TestCookiesProbe class tests with monkeypatched YtdlpDownloader.probe
- `tests/unit/adapters/ytdlp/test_downloader.py` — Added TestCookieAuthDetection (3 tests) + TestProbe (6 tests)
