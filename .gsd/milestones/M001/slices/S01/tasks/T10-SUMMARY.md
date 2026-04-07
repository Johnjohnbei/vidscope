---
id: T10
parent: S01
milestone: M001
key_files:
  - scripts/verify-s01.sh
key_decisions:
  - Sandbox under mktemp + trap cleanup so verify-s01.sh never touches the user's real data_dir — rerunnable indefinitely with zero side effects
  - Use `python -m uv run` instead of a bare `uv` binary so the script works whether uv is installed via pip --user, standalone installer, or bundled in the venv
  - Tolerate both exit 0 and exit 2 for the doctor step (ffmpeg presence is environment-dependent) but REQUIRE both check names in the output — prevents a broken doctor from silently passing
  - Inline Python one-liners for the DB schema verification and the post-add run-count check — more authoritative than grepping CLI stdout and catches schema regressions mechanically
  - `set +e; output=$(cmd); exit=$?; set -e` idiom instead of `$(cmd || true)` to capture real exit codes correctly — documented inline so the pattern doesn't regress
  - Colored output disabled when stdout is not a TTY so CI logs stay clean
  - Step counter + failed_steps array + summary block so a single glance tells you exactly which step(s) failed
duration: 
verification_result: passed
completed_at: 2026-04-07T11:39:04.027Z
blocker_discovered: false
---

# T10: Built scripts/verify-s01.sh — a 13-step bash verification script that exercises install + quality gates + CLI smoke + DB schema + ingest round-trip + doctor + error paths in one command, sandboxed under a tmp data dir.

**Built scripts/verify-s01.sh — a 13-step bash verification script that exercises install + quality gates + CLI smoke + DB schema + ingest round-trip + doctor + error paths in one command, sandboxed under a tmp data dir.**

## What Happened

T10 is the integration proof for S01. Not a new feature — a single bash script that re-runs every check exercising the socle end-to-end, on a clean sandboxed environment, with one authoritative pass/fail verdict at the end. This is what a human (or a CI job) runs to answer "is S01 actually working right now?" without having to remember thirteen different commands.

**scripts/verify-s01.sh** — 230 lines, bash, portable across Windows git-bash / macOS / Linux. Every command goes through `python -m uv run` so it works whether uv is on PATH, installed via pip `--user`, or bundled in the venv. Key design choices:

- **Sandboxed data dir.** Creates a fresh tempdir via `mktemp -d`, exports `VIDSCOPE_DATA_DIR=${TMP_DATA_DIR}`, and sets a trap to remove it on exit. The script NEVER touches the user's real `%LOCALAPPDATA%/vidscope` — rerunnable without side effects on the developer's actual library.
- **Self-locating.** `SCRIPT_DIR=$(cd $(dirname "${BASH_SOURCE[0]}") && pwd)` + `cd "${REPO_ROOT}"` so the script works from any cwd.
- **Colored output (when TTY).** `printf` with ANSI escapes for bold/green/red/cyan/dim, stripped when stdout isn't a terminal so CI logs stay clean.
- **Step tracking.** A `run_step "name" cmd args…` helper prints the command, runs it, and either appends to `failed_steps[]` on failure or prints a green checkmark. At the end: count + list of failures.
- **Summary + exit code.** Exit 0 on full success, exit 1 with a list of failed steps on any failure.

**The 13 steps:**

1. `uv sync` — reproducible dependency install.
2. `ruff check src tests` — lint clean.
3. `mypy src` (strict) — type clean on 47 files.
4. `lint-imports` — 7/7 architectural contracts kept.
5. `pytest -q` — 185/185 unit+architecture tests pass.
6. `vidscope --version` — package installed and importable via the entry point.
7. `vidscope --help` — help output is parsed and every expected subcommand (add/show/list/search/status/doctor) is confirmed present. Uses a tight regex `(^|[[:space:]])cmd([[:space:]]|$)` to avoid false positives.
8. `vidscope status` on the empty sandboxed DB — returns the "no runs yet" hint with exit 0. This also triggers the very first DB write (init_db via build_container) so the DB file is created.
9. **DB schema verification** — inline Python one-liner that opens the DB and asserts every expected table (`videos`, `transcripts`, `frames`, `analyses`, `pipeline_runs`, `search_index`) exists. Catches schema regressions mechanically — if someone removes a `Table(...)` declaration, this step fails loudly.
10. **doctor** — runs `vidscope doctor` and tolerates both exit codes 0 (ffmpeg present) and 2 (ffmpeg missing with remediation printed). Asserts that both check names ("ffmpeg", "yt-dlp") appear in the output regardless.
11. **ingest happy path** — `vidscope add "https://www.youtube.com/watch?v=verify-s01"` writes a PENDING pipeline_runs row.
12. **post-add verification** — inline Python that opens a UnitOfWork, calls `list_recent(limit=10)`, asserts exactly 1 run exists with the right phase, status, and source_url. This proves the full add→DB→query round-trip works on fresh state.
13. **error path** — `vidscope add ""` (empty URL) with `set +e; ...; set -e` to capture the exit code safely, asserts it equals 1 (user error).

**One bash gotcha fixed mid-run:** the original step 10 used `doctor_output="$(cmd || true)"` and then read `$?`, which doesn't work — `||` short-circuits and the `$?` reflects the `true` exit, not the captured command. Replaced with `set +e; output=$(cmd); exit=$?; set -e` which is the proper idiom. Without the fix the script was reporting `(exit 0)` for doctor even when ffmpeg was missing. Documented inline with a comment so the next agent doesn't make the same mistake.

**Final run result:** 13/13 steps passed. `ffmpeg` is NOT installed on this dev machine, so step 10 (doctor) correctly reported `fail` for ffmpeg and `ok` for yt-dlp with exit code 2 — and the script correctly tolerated the exit 2 because the output contained both expected check names. Everything else ran clean. Total duration: ~15 seconds.

**Windows encoding note:** the script's em-dashes (`—`) in comments render fine in git-bash, and none of the assertion strings contain em-dashes so the Windows CP1252 issue from T09 doesn't affect T10. The script's output uses `✓` and `✗` which render correctly in modern Windows terminals (Windows Terminal, git-bash's mintty).

## Verification

Ran `bash scripts/verify-s01.sh` from the repo root. All 13 steps passed. Summary: `Total steps: 13, Failed: 0, ✓ S01 verification PASSED`. The script sandboxes under a fresh tempdir and cleans up on exit. Separately verified that `vidscope doctor` actually returns exit 2 on this machine (ffmpeg missing) and that the script correctly captures that exit code after the bash idiom fix. Re-running the script multiple times produces the same green result — it's idempotent because the sandbox is fresh every run.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash scripts/verify-s01.sh` | 0 | ✅ pass — 13/13 steps, S01 verification PASSED | 15000ms |
| 2 | `verify-s01.sh step 10 (doctor with ffmpeg missing)` | 2 | ✅ pass — correctly captured exit 2 and validated both check names present | 500ms |
| 3 | `verify-s01.sh step 12 (post-add DB round-trip)` | 0 | ✅ pass — exactly 1 pipeline_run row with phase=ingest, status=pending, correct source_url | 600ms |

## Deviations

The plan said "(1) nuke the data_dir; (2) uv sync; …" implying we'd delete the user's actual data dir. That's a bad idea — the user has a real library in `%LOCALAPPDATA%/vidscope` (or will, once S02-S06 land). Instead I sandbox each invocation under `$(mktemp -d)` and export `VIDSCOPE_DATA_DIR` to point there. The data_dir is freshly created from scratch every run, which satisfies the "clean environment" intent without ever touching the user's real files. trap cleanup removes the tempdir on exit.

Also discovered and fixed a bash gotcha mid-execution: `$(cmd || true)` followed by `$?` doesn't capture the real exit code. Replaced with `set +e; ...; set -e` bracketing. The fix is documented inline.

## Known Issues

None. The script passes cleanly. ffmpeg being missing on this dev machine is the expected state — verified via `vidscope doctor` reporting fail/exit2, which the script tolerates. ffmpeg becomes a hard dependency in S04 (frame extraction), at which point the verify script for S04 will require it.

## Files Created/Modified

- `scripts/verify-s01.sh`
