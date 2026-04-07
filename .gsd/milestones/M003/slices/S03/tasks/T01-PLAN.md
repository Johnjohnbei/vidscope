---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T01: docs/watchlist.md and verify-m003.sh + milestone closure

Write docs/watchlist.md (concepts, commands, idempotence, error handling, scheduling-via-cron note). Write scripts/verify-m003.sh modeled on verify-m002.sh: 4 quality gates + sandboxed demo (add @YouTube, refresh, list, assert > 0 new videos, second refresh idempotent). Run ./scripts/verify-m003.sh end-to-end. Update PROJECT.md to mention the watchlist as a current capability. Mark R021 + R022 as validated. Close M003 via gsd_complete_milestone.

## Inputs

- `scripts/verify-m002.sh`
- `docs/mcp.md`
- `docs/quickstart.md`

## Expected Output

- `docs/watchlist.md`
- `scripts/verify-m003.sh`
- `Updated PROJECT.md`
- `verify-m003.sh exits 0`

## Verification

bash scripts/verify-m003.sh
