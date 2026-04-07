---
id: T07
parent: S07
milestone: M001
key_files:
  - scripts/verify-s07.sh
key_decisions:
  - Cookies detection in the script header so operators see at startup which regime they're running in (configured or not), not after the integration block has run
  - Step 10 misconfigured-cookies test is a real CLI invocation in a subshell with a synthetic env var — no mocks, real proof that T03's fail-fast fires
  - Doctor check now requires three rows (ffmpeg + yt-dlp + cookies) instead of two, locking in T04's contract
  - Integration block exit-code interpretation is cookies-aware: success regardless of whether Instagram passed (cookies configured) or xfailed (cookies absent), as long as the suite itself didn't fail
  - Summary message adapts: 'R001 validated for all three platforms' when cookies are configured, vs 'S07 plumbing correct, set cookies to validate Instagram' when not. The user always knows exactly what they're seeing.
  - Reused the verify-s02.sh portability pattern (mktemp sandbox, trap cleanup, python -m uv run, set +e/-e for exit-code capture) so the script is the third instance of a stable pattern
duration: 
verification_result: passed
completed_at: 2026-04-07T13:54:46.977Z
blocker_discovered: false
---

# T07: Shipped scripts/verify-s07.sh — 11-step bash verification with --skip-integration fast mode, cookies-aware integration block, misconfigured-cookies fail-fast test, and a summary that adapts to whether cookies are configured.

**Shipped scripts/verify-s07.sh — 11-step bash verification with --skip-integration fast mode, cookies-aware integration block, misconfigured-cookies fail-fast test, and a summary that adapts to whether cookies are configured.**

## What Happened

T07 is the closing brick of S07. One command answers the full question "does S07 work end-to-end?" — install, four quality gates, CLI smoke, cookies-aware doctor, fail-fast on misconfiguration, live integration tests with the cookies-aware Instagram path.

**scripts/verify-s07.sh** — same shape as verify-s01.sh and verify-s02.sh (sandboxed tempdir, colored TTY, step counter, failed_steps array, summary). Key differences from verify-s02.sh:

- **Cookies detection at startup.** Reads `VIDSCOPE_COOKIES_FILE` from the parent shell, checks if the file exists, sets `COOKIES_AVAILABLE=true|false`. Prints the cookies status in the header alongside repo / sandbox so the operator immediately sees what regime they're running in.

- **Step 8 doctor check now requires THREE rows.** Asserts ffmpeg, yt-dlp, AND cookies all appear in the output. T04 added the third row; T07 verifies the doctor command actually exposes it.

- **Step 10 misconfigured-cookies fail-fast test.** Runs `VIDSCOPE_COOKIES_FILE=/nonexistent vidscope status` in a subshell and asserts the exit code is non-zero. This is the user-facing proof that T03's container fail-fast actually fires when the path is bad. No mocks — real CLI invocation against the real container.

- **Step 11 integration block adapts to cookies state.** Runs the same `pytest tests/integration -m integration -v` as verify-s02. The pass/fail logic depends on `COOKIES_AVAILABLE`:
  - If cookies configured AND integration green → "Instagram passing with cookies"
  - If cookies NOT configured AND integration green → "Instagram xfailed, cookies not provided" (still success, not failure)
  - If integration non-zero → real failure regardless

- **Summary message adapts.** When cookies are configured and everything passes, the message reads "Instagram is alive on real networks. R001 validated for all three platforms." When cookies are absent, it reads "S07 plumbing is correct. To validate Instagram in live, set VIDSCOPE_COOKIES_FILE per docs/cookies.md and re-run." Both are accurate; the difference tells the operator exactly what state they're in.

**First fast run** (`bash scripts/verify-s07.sh --skip-integration`): 10/10 steps green in ~30s. Confirms doctor includes the cookies row, fail-fast works on bad cookies path, no regression in any unit test.

**Full run** (`bash scripts/verify-s07.sh`, no cookies on this machine): 11/11 steps green in ~45s. The integration block correctly:
1. Runs Instagram first (per D027 reordering from T05)
2. Sees the xfail with the explicit "requires cookie-based authentication" message
3. Treats it as expected behavior (not a failure)
4. Continues with TikTok (passes) and YouTube (passes)
5. Reports overall green with the "cookies not provided" qualifier in the summary

The script is now the authoritative S07 signal. An operator can run it and know in 45 seconds whether the entire cookies feature works end-to-end, regardless of whether they personally have cookies configured.

**What S07 delivers in total** (synthesizing T01-T07):
- Config: env var resolution + Config.cookies_file field (T01)
- Adapter: cookies parameter on YtdlpDownloader with init-time validation (T02)
- Wiring: container reads config, passes to downloader (T03)
- Observability: doctor reports cookies as a third check with three semantic states (T04)
- Tests: integration test reordered Instagram-first with cookies-aware xfail-or-pass (T05)
- Documentation: docs/cookies.md user guide with browser export instructions and security notes (T06)
- Verification: verify-s07.sh end-to-end script (T07)

**What's needed for Instagram to ACTUALLY pass live:** the user exports `cookies.txt` from a logged-in browser session per docs/cookies.md, sets `VIDSCOPE_COOKIES_FILE`, and re-runs `bash scripts/verify-s07.sh`. The plumbing is complete; the activation is a user action.

## Verification

Ran `bash scripts/verify-s07.sh --skip-integration` → 10/10 steps green in ~30s. Ran `bash scripts/verify-s07.sh` (full mode, no cookies on dev machine) → 11/11 steps green in ~45s with the "Instagram xfailed, cookies not provided" qualifier. The full run includes: uv sync, ruff, mypy, lint-imports, pytest unit (260 tests), vidscope --version, --help with all 6 commands, doctor with cookies row, unsupported URL exit 1, misconfigured cookies fail-fast, live integration with priority-order tests. Every step exited 0 except the integration which ran 2 passed + 1 xfailed (correct expected behavior).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash scripts/verify-s07.sh --skip-integration` | 0 | ✅ pass — 10/10 fast-mode steps green | 30000ms |
| 2 | `bash scripts/verify-s07.sh` | 0 | ✅ pass — 11/11 full-mode steps green, Instagram xfail correctly tolerated, summary qualifies cookies state | 45000ms |

## Deviations

None. The script is the same shape as verify-s02 with three S07-specific additions: cookies detection in the header, step 10 (misconfigured cookies fail-fast), and adaptive summary messages.

## Known Issues

None. The script passes cleanly in both fast mode and full mode. To fully validate Instagram in live, the user needs to provide cookies — that's a user action, not a script bug.

## Files Created/Modified

- `scripts/verify-s07.sh`
