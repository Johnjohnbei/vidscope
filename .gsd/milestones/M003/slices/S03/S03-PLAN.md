# S03: Docs, verify-m003.sh, milestone closure

**Goal:** Ship M003 documentation, write verify-m003.sh that exercises the watchlist end-to-end with a real public account, and close the milestone.
**Demo:** After this: docs/watchlist.md explains usage + cron/Task Scheduler examples. verify-m003.sh runs quality gates + unit tests + live channel listing + idempotent refresh demo.

## Tasks
- [x] **T01: Shipped docs/watchlist.md, scripts/verify-m003.sh (9 steps, 9/9 green), updated PROJECT.md, marked R021 + R022 as validated. M003 ready for milestone closure.** — Write docs/watchlist.md (concepts, commands, idempotence, error handling, scheduling-via-cron note). Write scripts/verify-m003.sh modeled on verify-m002.sh: 4 quality gates + sandboxed demo (add @YouTube, refresh, list, assert > 0 new videos, second refresh idempotent). Run ./scripts/verify-m003.sh end-to-end. Update PROJECT.md to mention the watchlist as a current capability. Mark R021 + R022 as validated. Close M003 via gsd_complete_milestone.
  - Estimate: 1h30m
  - Files: docs/watchlist.md, scripts/verify-m003.sh, .gsd/PROJECT.md
  - Verify: bash scripts/verify-m003.sh
