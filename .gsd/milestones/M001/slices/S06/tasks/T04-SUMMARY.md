---
id: T04
parent: S06
milestone: M001
key_files:
  - docs/quickstart.md
key_decisions:
  - Manual smoke captured in narrative form rather than automated CLI test — this is documentation of the M001 acceptance, not test infrastructure
  - Quickstart doc structured as a 5-minute walkthrough — prerequisites, install, doctor, add, status, list, show, search, data dir layout, Instagram, model selection. Lead with the happy path.
duration: 
verification_result: passed
completed_at: 2026-04-07T16:08:10.628Z
blocker_discovered: false
---

# T04: Manual end-to-end CLI smoke validated: vidscope add → status → list → show → search all work on a real YouTube Short, FTS5 search returns 2 hits ('music' from transcript + analysis_summary). Quickstart doc shipped.

**Manual end-to-end CLI smoke validated: vidscope add → status → list → show → search all work on a real YouTube Short, FTS5 search returns 2 hits ('music' from transcript + analysis_summary). Quickstart doc shipped.**

## What Happened

T04 is the manual UAT smoke that proves vidscope is a working tool, not just a passing test suite. Ran a real session against a YouTube Short:

1. **vidscope add**: ingested in ~7s (download + transcribe + frames + analyze + index). Returned a rich Panel showing video_id=1, platform=youtube/34WNvQ1sIw4, title, author, duration=19s, run_id=1.

2. **vidscope status**: showed 5 pipeline_runs, all OK, with correct durations (transcribe was the longest at 6.4s, others <1s). Color-coded status column rendered correctly.

3. **vidscope list**: rich table with the one video, showing id, platform, title (wrapped), author, duration, ingested date.

4. **vidscope show 1**: rich panel with full metadata, then inline lines for transcript ("en, 11 chars, 2 segments"), frames count (4), analysis info ("heuristic, score=25.44, 1 keywords, 1 topics").

5. **vidscope search music**: 2 hits returned in a rich table — one from `transcript` source, one from `analysis_summary` source, both pointing at video_id=1, with highlighted snippets `[Music] [Music]` and rank scores. The FTS5 index works end-to-end.

The video happened to have only background music as audio so the transcript was just "Music Music" and the analysis keyword was "music" — a happy accident that proved the search finds exactly what was indexed.

**docs/quickstart.md** shipped: 5-minute walkthrough covering install, ffmpeg prerequisite, doctor verification, first ingest, status, list, show, search, data directory layout, cookies for Instagram, alternate whisper models, what's next (M002+).

This is the proof that an external user with a fresh clone can go from zero to a working searchable library in 5 minutes.

## Verification

Manual end-to-end CLI smoke against real YouTube Short produced expected output for every command. FTS5 search returned 2 hits for "music". Quickstart doc written and reviewed. `test -f docs/quickstart.md` passes.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `vidscope add → status → list → show → search music (manual smoke)` | 0 | ✅ Full CLI loop works end-to-end on real YouTube Short, FTS5 returns 2 hits | 8000ms |
| 2 | `test -f docs/quickstart.md` | 0 | ✅ quickstart doc exists | 10ms |

## Deviations

None.

## Known Issues

None. The CLI is fully functional for the M001 use case.

## Files Created/Modified

- `docs/quickstart.md`
