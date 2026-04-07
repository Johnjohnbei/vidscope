---
id: T02
parent: S03
milestone: M002
key_files:
  - scripts/verify-m002.sh
key_decisions:
  - End-to-end demo seeds 2 videos via inline Python using the repository layer — no network needed, no live URL flakiness, the suggestion engine is exercised on real data
  - Parse source_id from seed output using grep + cut so the script can inject the right video_id into the subsequent `vidscope suggest` call — keeps the steps loosely coupled
  - Full mode total runtime ~12s including MCP subprocess startup (~1.7s) and the full test suite (~3.5s) — fast enough to run on every change
duration: 
verification_result: passed
completed_at: 2026-04-07T17:31:55.794Z
blocker_discovered: false
---

# T02: Shipped scripts/verify-m002.sh — 10-step milestone gate with --skip-integration fast mode. Runs quality gates + unit tests + MCP subprocess tests + real `vidscope suggest` CLI demo seeding 2 videos. 10/10 green on dev machine.

**Shipped scripts/verify-m002.sh — 10-step milestone gate with --skip-integration fast mode. Runs quality gates + unit tests + MCP subprocess tests + real `vidscope suggest` CLI demo seeding 2 videos. 10/10 green on dev machine.**

## What Happened

verify-m002.sh is the authoritative "is M002 done" signal. Same shape as verify-m001.sh:

1. **Sandboxed** tempdir via `mktemp -d` and `VIDSCOPE_DATA_DIR` export
2. **Step 1-5**: quality gates (uv sync, ruff, mypy strict, lint-imports, pytest unit suite)
3. **Step 6-7**: CLI smoke (`--version`, `--help` with 8 expected commands including the new `suggest` and `mcp`)
4. **Step 8**: doctor output contains the `mcp` row (by simple grep on stdout)
5. **Step 9** (skipped in fast mode): MCP subprocess integration tests
6. **Step 10**: end-to-end suggestion engine demo — inline Python seeds 2 videos with overlapping analyses (Python cooking + Python recipe) directly via the repository layer, then `vidscope suggest <source_id>` is invoked via CLI and the output is grepped for the expected matching video title

The demo step is the "does the whole M002 feature work" proof. It doesn't need network because the suggestion engine is pure read — we seed the DB directly, then call the CLI command that the user would run. The output confirms:
- Source video #1 "Python cooking tutorial" with keywords [python, cooking, recipe, tips]
- Matching video #2 "Python recipe collection" returned with score 40% (Jaccard 2/5 = 0.4, since source has 4 unique + match has 3 unique + 2 shared = 5 union, 2 intersection)
- Matched keywords: "python, recipe"

**Fast mode**: 9 steps including the demo, no subprocess spawning. ~10 seconds.

**Full mode**: 10 steps including MCP subprocess integration. ~12 seconds. Both modes exit 0 on the dev machine.

The script supports `--skip-integration` for the fast inner loop during development and the full mode for the authoritative milestone gate.

## Verification

Ran `bash scripts/verify-m002.sh --skip-integration` → 9/9 steps green in ~10s. Ran `bash scripts/verify-m002.sh` (full) → 10/10 steps green including MCP subprocess tests and real `vidscope suggest` demo returning the matching video.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash scripts/verify-m002.sh --skip-integration` | 0 | ✅ 9/9 fast-mode steps green including suggestion engine demo | 10000ms |
| 2 | `bash scripts/verify-m002.sh` | 0 | ✅ 10/10 full-mode steps green with MCP subprocess tests | 12000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `scripts/verify-m002.sh`
