# M005: Cookies UX improvements

## Vision
Cookies in M001/S07 shipped the plumbing — VIDSCOPE_COOKIES_FILE env, doctor check, integration with yt-dlp. M005 adds the UX layer on top so users don't need to know paths, can verify their cookies work without ingesting a real video, can refresh stale sessions in a single command, and get actionable error messages when cookies fail. The watchlist (M003) and the LLM analyzers (M004) all benefit because Instagram is the platform priority (D027) and Instagram requires cookies. M005 is what makes the cookies feature actually usable, not just plumbed.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Cookies file validation + status + clear (read-only + simple writes) | low | — | ✅ | vidscope cookies status / clear / set work end-to-end with format validation. |
| S02 | Cookies probe + typed CookieAuthError + better error remediation | medium | S01 | ✅ | vidscope cookies test reports cookies work/expired/missing without ingesting a video. vidscope add against Instagram with no cookies surfaces actionable error. |
| S03 | Docs rewrite + verify-m005.sh + R025 validation + milestone closure | low | S02 | ✅ | docs/cookies.md is the 5-minute walkthrough, verify-m005.sh runs 9-10 steps green, R025 validated, M005 complete. |
