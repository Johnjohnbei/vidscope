---
id: S06
parent: M001
milestone: M001
provides:
  - IndexStage as the 5th and final pipeline stage
  - Container wired with the 5-stage runner
  - vidscope search command works end-to-end against real ingested videos
  - docs/quickstart.md user-facing 5-minute walkthrough
  - scripts/verify-m001.sh authoritative milestone gate
requires:
  - slice: S05
    provides: AnalyzeStage and analyses rows that S06 indexes alongside transcripts
affects:
  - M001 milestone closure — every active requirement now has live runtime evidence
  - M002 (MCP server) — inherits the full 5-stage pipeline + working search index. The MCP server will wrap the existing use cases without adding new stages.
key_files:
  - src/vidscope/pipeline/stages/index.py
  - src/vidscope/pipeline/stages/__init__.py
  - src/vidscope/infrastructure/container.py
  - tests/unit/pipeline/stages/test_index.py
  - tests/unit/infrastructure/test_container.py
  - tests/unit/cli/test_app.py
  - tests/integration/test_ingest_live.py
  - docs/quickstart.md
  - scripts/verify-m001.sh
key_decisions:
  - IndexStage takes no constructor dependencies — uses uow.search_index from the unit of work. Cleanest stage interface in the slice.
  - is_satisfied always False because re-indexing is cheap and idempotent (DELETE+INSERT)
  - FTS5 hit assertion in integration test is guarded by 'has analysis keywords AND non-empty transcript' so instrumental videos don't fail the test
  - verify-m001.sh combines unit + integration + real CLI demo — the authoritative milestone gate. 9 steps cover every layer from install to working search.
  - docs/quickstart.md is the 5-minute new-user walkthrough — lead with the happy path, prerequisites, doctor verification, then add/status/list/show/search in order
patterns_established:
  - Final-assembly slice pattern: small per-task work because every prior slice shipped its piece. The closing slice mostly wires + validates + documents.
  - Milestone-level verification script (verify-m001.sh) as the authoritative 'is the milestone done' signal, combining gates + integration + real CLI demo
observability_surfaces:
  - Pipeline now produces 5 pipeline_runs rows per video — the full ingest history is visible in vidscope status
  - vidscope search returns ranked FTS5 hits with snippets — grep-able way to find any video by content
  - vidscope show displays the full record per video — the inspection surface for individual rows
  - verify-m001.sh is the repo-level health check that operators run after any change
drill_down_paths:
  - .gsd/milestones/M001/slices/S06/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S06/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S06/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001/slices/S06/tasks/T04-SUMMARY.md
  - .gsd/milestones/M001/slices/S06/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T16:11:25.909Z
blocker_discovered: false
---

# S06: End-to-end wiring, FTS5 index, search and status commands

**Closed M001: shipped IndexStage (5th pipeline stage) + verify-m001.sh + quickstart docs. Pipeline now runs ingest → transcribe → frames → analyze → index in 5 transactional stages, validated end-to-end via real YouTube ingest → search returning 2 hits.**

## What Happened

S06 closes M001 with 5 tasks. The work was small per task because every prior slice already shipped its piece — S06 just had to add the index stage, wire it, and validate the full assembly.

**T01**: IndexStage with 6 tests. Reads transcript + analysis from DB, calls uow.search_index.index_transcript / index_analysis. is_satisfied always False because re-indexing is cheap and idempotent (DELETE+INSERT semantics in SearchIndexSQLite from S01).

**T02**: Container wiring. Appended IndexStage to runner. Container test asserts stage_names is now `('ingest', 'transcribe', 'frames', 'analyze', 'index')`. CLI test_after_add expects 5 pipeline_runs.

**T03**: Integration test helper extended with FTS5 hit assertion: after the run, search for the first analysis keyword and expect at least one hit (guarded by "has analysis keywords AND non-empty transcript" because instrumental videos legitimately produce empty indexes). YouTube + TikTok pass with the full 5-stage chain in 11.79s.

**T04**: Manual end-to-end CLI smoke. Real YouTube Short ingested via `vidscope add`, then `vidscope status` shows 5 pipeline_runs (color-coded), `vidscope list` shows the video in a rich table, `vidscope show 1` shows the full record (metadata + transcript stats + frames count + analysis info), `vidscope search music` returns 2 hits (one from transcript source, one from analysis_summary source) with highlighted snippets and BM25 ranks. docs/quickstart.md ships as the 5-minute walkthrough for new users.

**T05**: scripts/verify-m001.sh — the authoritative milestone gate. Combines uv sync + ruff + mypy strict + lint-imports + pytest + CLI smoke + live integration suite + a real CLI end-to-end demo that runs `vidscope add` against a real YouTube Short and queries the sandboxed DB to verify the chain. 9/9 steps green on the dev machine.

**Real result on dev machine** (verify-m001.sh full mode):
- 7 quality+CLI gate steps green
- Live integration: TikTok PASSED + YouTube PASSED + Instagram XFAIL (cookies)
- CLI demo: video_id=1, transcript=yes, analysis=yes, frames=4, pipeline_runs=5, search('music') returned 2 hits
- Total runtime ~50s

**Pipeline state at end of M001**: 5 stages, 1 video → 1 transcript + N frames + 1 analysis + N FTS5 entries + 5 pipeline_runs rows. R006 (FTS5 search), R007 (single-command end-to-end), R008 (status visibility) all advanced to validated. Quality gates: 343 unit tests + 3 architecture + 3 integration. Ruff/mypy strict on 65 files/lint-imports 7 contracts all clean.

## Verification

Ran `bash scripts/verify-m001.sh --skip-integration` → 7/7 steps green. Ran `bash scripts/verify-m001.sh` (full) → 9/9 steps green in ~50s. Ran `python -m uv run pytest -q` → 343 passed, 3 deselected. All quality gates clean.

## Requirements Advanced

- R006 — FTS5 search returns real ranked hits via vidscope search command. Validated on live YouTube ingest.
- R007 — Single-command end-to-end ingest now runs all 5 stages transactionally. Validated end-to-end via verify-m001.sh.
- R008 — vidscope status + vidscope show provide complete inspection surface for pipeline state and individual videos.

## Requirements Validated

- R006 — Live CLI demo: vidscope search 'music' returned 2 hits from transcript + analysis_summary sources after a real YouTube Short ingest
- R007 — verify-m001.sh step 9 ingests a real YouTube Short, all 5 pipeline_runs land OK, the resulting DB state is consistent (1 video + 1 transcript + 4 frames + 1 analysis + 5 runs + indexed FTS5 entries)
- R008 — vidscope status shows 5 pipeline_runs with status colors and durations. vidscope show <id> displays full record.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

FTS5 search uses BM25 ranking (the FTS5 default). No semantic search via embeddings — that's R026 deferred. vidscope show only displays video metadata + counts, not the full transcript text or frames thumbnails — those are intentionally summary views for the CLI; future MCP server in M002 will expose richer queries.

## Follow-ups

M002 MCP server will expose ingest/show/search/list as tools an AI agent can call. M003 watchlist + scheduled refresh. M004 LLM-backed analyzer providers via the registry pattern from S05.

## Files Created/Modified

- `src/vidscope/pipeline/stages/index.py` — New IndexStage — 5th pipeline stage writing to FTS5
- `src/vidscope/infrastructure/container.py` — Wired IndexStage as 5th stage in the runner
- `tests/unit/pipeline/stages/test_index.py` — 6 tests for IndexStage with real SQLite + FTS5
- `tests/integration/test_ingest_live.py` — Helper extended with index pipeline_run + FTS5 hit assertion
- `docs/quickstart.md` — New 5-minute user walkthrough
- `scripts/verify-m001.sh` — New milestone-level verification script
