# S06: End-to-end wiring, FTS5 index, search and status commands

**Goal:** Close M001: ship the IndexStage that writes transcripts and analysis summaries to the FTS5 virtual table, and ensure every CLI command (add, show, list, search, status) works end-to-end against real data on every successful platform. Verify the full milestone definition of done.
**Demo:** After this: `vidscope add`, `show`, `list`, `search`, and `status` all work end-to-end on a live public URL for each of the three platforms, FTS5 returns ranked matches, resume-from-failure is demonstrated, and the full milestone definition of done is verified.

## Tasks
- [x] **T01: Shipped IndexStage: writes transcripts + analysis summaries to FTS5 via uow.search_index, idempotent re-indexing — 6 stage tests, search returns real hits.** — Create src/vidscope/pipeline/stages/index.py. IndexStage with name=StageName.INDEX.value. __init__ takes nothing (uses uow.search_index from the unit of work). is_satisfied is a no-op returning False (the search index is rebuilt on every run because it's idempotent via DELETE+INSERT). execute: (1) requires ctx.video_id, (2) reads the latest transcript via uow.transcripts.get_for_video, (3) reads the latest analysis via uow.analyses.get_latest_for_video, (4) calls uow.search_index.index_transcript(transcript) if transcript exists, (5) calls uow.search_index.index_analysis(analysis) if analysis has a non-empty summary. Returns StageResult with the indexed document count. Tests with real adapters.
  - Estimate: 1h
  - Files: src/vidscope/pipeline/stages/index.py, src/vidscope/pipeline/stages/__init__.py, tests/unit/pipeline/stages/test_index.py
  - Verify: python -m uv run pytest tests/unit/pipeline/stages -q
- [x] **T02: Wired IndexStage as the 5th and final pipeline stage; pipeline now runs ingest → transcribe → frames → analyze → index; 337 tests green.** — Update container.py to append IndexStage to the pipeline runner stages list as the 5th and final stage. Update test_container assertions: stage_names == ('ingest','transcribe','frames','analyze','index'). Update CLI test_after_add to expect 5 pipeline_runs. The CLI test fixture stub_pipeline doesn't need changes — IndexStage uses real DB writes which are already exercised.
  - Estimate: 30m
  - Files: src/vidscope/infrastructure/container.py, tests/unit/infrastructure/test_container.py, tests/unit/cli/test_app.py
  - Verify: python -m uv run pytest tests/unit -q
- [x] **T03: Live integration tests now validate the full 5-stage pipeline with FTS5 hit assertion: TikTok + YouTube produce real searchable index in ~15s.** — Extend tests/integration/test_ingest_live.py helper with a final assertion: after the run, call container.search_library use case (or directly query uow.search_index.search) with a likely keyword from the analysis and assert at least one result is returned. This proves the FTS5 indexing actually works end-to-end. The keyword can be derived from the persisted analysis.keywords[0] when non-empty, or skipped for instrumental videos. Also verify the CLI side: instantiate the SearchLibraryUseCase against the same DB and assert it returns the same results.
  - Estimate: 1h
  - Files: tests/integration/test_ingest_live.py
  - Verify: python -m uv run pytest tests/integration -m 'integration and slow' -v
- [x] **T04: Manual end-to-end CLI smoke validated: vidscope add → status → list → show → search all work on a real YouTube Short, FTS5 search returns 2 hits ('music' from transcript + analysis_summary). Quickstart doc shipped.** — Run a manual end-to-end demo that the CLI can be used as a real tool: vidscope add <url>, vidscope status (5 runs), vidscope list (1 row), vidscope show <id> (full record), vidscope search <keyword> (hits). Capture the output and verify each command produces the expected shape. No new test code — this is a manual smoke that proves the CLI actually works for an end user. Document the commands in a docs/quickstart.md file for users.
  - Estimate: 1h
  - Files: docs/quickstart.md
  - Verify: test -f docs/quickstart.md
- [x] **T05: Shipped scripts/verify-m001.sh — milestone-level verification: 9 steps including quality gates, live integration on 5-stage pipeline, real CLI end-to-end demo. PASSED on dev machine: 9/9 green, real YouTube ingest → search produces 2 hits.** — Create scripts/verify-m001.sh: the authoritative 'is M001 done' signal. Runs every quality gate, the full unit suite, the live integration suite (with --skip-integration flag), then performs a real end-to-end demo: ingest a YouTube short, list videos, show the video, search for a keyword from the analysis, doctor. Summary message announces M001 readiness for completion or lists the steps that failed.
  - Estimate: 1h
  - Files: scripts/verify-m001.sh
  - Verify: bash scripts/verify-m001.sh --skip-integration
