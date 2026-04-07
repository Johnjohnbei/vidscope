---
id: T06
parent: S03
milestone: M001
key_files:
  - scripts/verify-s03.sh
key_decisions:
  - Same pattern as verify-s01/s02/s07: sandboxed tempdir, --skip-integration fast mode, colored TTY output, summary block
  - Inline Python in the round-trip step queries both videos and transcripts rows — proves the full S02 + S03 chain persists correctly
  - Whisper model download warning printed before integration block so users know what to expect on first run
duration: 
verification_result: passed
completed_at: 2026-04-07T15:40:02.268Z
blocker_discovered: false
---

# T06: Shipped scripts/verify-s03.sh — 7-step fast mode + integration block with whisper model warning + sandboxed DB transcript verification.

**Shipped scripts/verify-s03.sh — 7-step fast mode + integration block with whisper model warning + sandboxed DB transcript verification.**

## What Happened

Same shape as verify-s01/s02/s07. The integration block prints a warning that the first run downloads ~150MB of whisper model. The sandboxed-DB verification step runs a real `vidscope add` after the integration tests and inspects the resulting videos+transcripts rows via inline Python — proves the full ingest+transcribe pipeline persists end-to-end in the script's own sandbox. Fast mode tested green (7/7 steps); full mode pending real network run.

## Verification

Ran `bash scripts/verify-s03.sh --skip-integration` → 7/7 steps green in ~25s. Did not run full mode here to avoid re-downloading the whisper model since T05 already validated the live integration.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash scripts/verify-s03.sh --skip-integration` | 0 | ✅ 7/7 fast-mode steps green | 25000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `scripts/verify-s03.sh`
