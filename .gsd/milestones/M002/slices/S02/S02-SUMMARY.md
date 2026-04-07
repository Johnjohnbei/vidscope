---
id: S02
parent: M002
milestone: M002
provides:
  - SuggestRelatedUseCase with Jaccard keyword overlap
  - Suggestion + SuggestRelatedResult DTOs
  - vidscope suggest <id> CLI command with rich table output
  - vidscope_suggest_related as the 6th MCP tool
  - _seed_related_library test helper for future tests that need overlapping analyses
requires:
  - slice: M002/S01
    provides: MCP server foundation, build_mcp_server factory, CLI mcp serve subcommand
affects:
  - S03 — closes M002 with docs/mcp.md and verify-m002.sh
key_files:
  - src/vidscope/application/suggest_related.py
  - src/vidscope/application/__init__.py
  - src/vidscope/cli/commands/suggest.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - src/vidscope/mcp/server.py
  - tests/unit/application/test_suggest_related.py
  - tests/unit/cli/test_app.py
  - tests/unit/mcp/test_server.py
  - tests/integration/test_mcp_server.py
key_decisions:
  - Jaccard similarity on keyword sets is the v1 suggestion algorithm — simplest signal that produces meaningful ordering without any ML deps
  - 500-candidate scan cap as a safety net — M003+ can add a keyword index if libraries grow beyond that
  - Single use case wrapped by both CLI and MCP interfaces — proves the hexagonal pattern scales to any future interface (HTTP, gRPC)
  - CLI displays score as 0-100% not raw [0, 1] Jaccard — easier to read at a glance
  - Matched keywords returned sorted for deterministic output
  - Empty source keywords returns empty with reason string — honest 'no signal, no result' rather than fabricating suggestions
patterns_established:
  - Use case + CLI command + MCP tool trio: every new feature that crosses the interface boundary ships as three thin wrappers around one use case. The pattern is now proven twice (M001 ingest/show/list/search/status + M002 suggest_related).
observability_surfaces:
  - suggestion engine is read-only, no new pipeline_runs rows produced
drill_down_paths:
  - .gsd/milestones/M002/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T17:28:26.182Z
blocker_discovered: false
---

# S02: Related-video suggestion engine + suggest tool + CLI suggest

**Shipped the suggestion engine: SuggestRelatedUseCase with Jaccard keyword overlap, `vidscope suggest <id>` CLI, and `vidscope_suggest_related` MCP tool — R023 validated with 25 new tests across application/CLI/MCP layers.**

## What Happened

S02 adds R023 (related-video suggestion) as a new use case exposed through both CLI and MCP. Three tasks: use case + CLI + MCP tool. Total ~350 lines of production code + tests.

**T01**: SuggestRelatedUseCase with Jaccard similarity. Algorithm: fetch source video + analysis, if keywords empty return empty, scan up to 500 candidates, compute Jaccard per candidate, skip zero scores, sort descending, take top N. DTOs: Suggestion (video_id, title, platform, score, matched_keywords) and SuggestRelatedResult (source info + suggestions tuple + reason string). 11 unit tests covering happy path, limit clamping, source exclusion, matched-keywords intersection correctness, missing source, no-analysis source, empty-keywords source, empty library, candidates-without-analyses, invalid limits, and full-vs-partial overlap ordering.

**T02**: `vidscope suggest <id>` CLI command. Handles three branches (source not found → exit 1, empty suggestions → dim reason, has suggestions → rich table). Score displayed as percentage for readability, matched keywords truncated to 5 with ellipsis. Also updated `TestHelpAndVersion` to check `suggest` and `mcp` are listed in help, added `TestSuggest` with 2 tests, `TestMcp` with 1 test, and extended `TestDoctor` to check for the `mcp` row.

**T03**: `vidscope_suggest_related` MCP tool as the 6th tool registered by `build_mcp_server`. Wraps the use case, converts the DTO to a JSON-serializable dict. Added `TestVidscopeSuggestRelated` with 3 tests including a `_seed_related_library` helper that creates 3 videos with overlapping/non-overlapping analyses. Updated the subprocess integration test to expect 6 tool names.

**At the end of S02:**
- 370 unit tests + 3 architecture + 2 MCP subprocess integration tests + 3 live ingest integration tests
- 70 source files mypy-strict clean
- 8 import-linter contracts (unchanged — the suggest addition doesn't need new layering rules)
- ruff clean

**What the user has now:**
- `vidscope suggest <id>` shows related videos with scores and matched keywords
- `vidscope_suggest_related` MCP tool for AI agents to discover adjacent content in the library
- 6 MCP tools total: ingest, search, get_video, list_videos, get_status, suggest_related

The hexagonal architecture holds: one use case, wrapped by two interface layers (CLI and MCP), with identical results. Any future interface (HTTP API, gRPC) would add a third wrapper with zero new business logic.

## Verification

Ran `python -m uv run pytest -q` → 370 passed, 5 deselected. Ran `python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v` → 2 passed. Ran `python -m uv run vidscope suggest --help` → Typer help correct. Ran all 4 quality gates (ruff, mypy strict, pytest, lint-imports) → all green.

## Requirements Advanced

- R023 — SuggestRelatedUseCase + suggest CLI + suggest_related MCP tool shipped. Tested across all three layers.

## Requirements Validated

- R023 — 11 unit tests on the use case + 2 CLI tests + 3 MCP tool tests + subprocess integration test asserting 6 tool names. All green.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Keyword overlap is frequency-based (inherited from the heuristic analyzer). Quality is correlated with analysis quality — weak analyses produce weak suggestions. 500-candidate scan cap avoids pathological cost on large libraries; future M003+ can add a keyword index if needed. R026 (semantic search via embeddings) remains deferred.

## Follow-ups

S03 ships docs/mcp.md and verify-m002.sh to close the milestone.

## Files Created/Modified

- `src/vidscope/application/suggest_related.py` — New use case with Jaccard overlap algorithm
- `src/vidscope/application/__init__.py` — Re-export SuggestRelatedUseCase, SuggestRelatedResult, Suggestion
- `src/vidscope/cli/commands/suggest.py` — New CLI command with rich table output
- `src/vidscope/cli/commands/__init__.py` — Re-export suggest_command
- `src/vidscope/cli/app.py` — Register suggest command
- `src/vidscope/mcp/server.py` — Added vidscope_suggest_related as the 6th tool
- `tests/unit/application/test_suggest_related.py` — 11 new tests covering happy path + edge cases + ordering
- `tests/unit/cli/test_app.py` — TestSuggest + TestMcp classes, updated TestHelpAndVersion + TestDoctor
- `tests/unit/mcp/test_server.py` — TestVidscopeSuggestRelated with 3 tests + _seed_related_library helper
- `tests/integration/test_mcp_server.py` — Updated expected tool names to include suggest_related
