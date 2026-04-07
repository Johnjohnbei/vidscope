---
id: M002
title: "MCP server and related-video suggestions"
status: complete
completed_at: 2026-04-07T17:34:46.845Z
key_decisions:
  - Use FastMCP decorator API for tool registration — documented stable entry point in the official mcp SDK 1.27.0
  - `build_mcp_server(container) -> FastMCP` factory pattern with container injection — keeps tests hermetic without monkeypatching globals
  - Each MCP tool is ~10 lines wrapping an existing M001 use case — zero new business logic in the interface layer
  - Import-linter mcp-has-no-adapters contract with ignore_imports for the composition-root edge — prevents direct adapter imports while allowing the legitimate infrastructure path
  - CLI above MCP in the layer stack — CLI can delegate to the MCP server for `vidscope mcp serve` while MCP can't reach back into CLI
  - Jaccard keyword overlap as the v1 suggestion algorithm — simplest signal that produces meaningful ordering without any ML dependencies
  - 500-candidate scan cap in the suggestion engine — safety net for large libraries; future M003+ can add a keyword index if needed
  - Subprocess integration tests exchange real JSON-RPC via the mcp ClientSession — covers the transport layer that in-process unit tests cannot
  - verify-m002.sh end-to-end demo seeds via the repository layer instead of making live network calls — deterministic, fast, exercises the full CLI output rendering
key_files:
  - src/vidscope/mcp/__init__.py
  - src/vidscope/mcp/server.py
  - src/vidscope/application/suggest_related.py
  - src/vidscope/cli/commands/mcp.py
  - src/vidscope/cli/commands/suggest.py
  - src/vidscope/infrastructure/startup.py
  - pyproject.toml
  - .importlinter
  - tests/unit/mcp/test_server.py
  - tests/unit/application/test_suggest_related.py
  - tests/integration/test_mcp_server.py
  - docs/mcp.md
  - scripts/verify-m002.sh
lessons_learned:
  - Hexagonal architecture lets a new interface layer slot in as a ~250-line package with zero business logic — the S01/M002 MCP server is the proof that the M001 architectural discipline pays off
  - `build_mcp_server(container) -> FastMCP` factory with container injection is the right pattern for testable MCP servers — mirrors the M001 composition root pattern
  - import-linter's `ignore_imports` whitelist is the correct escape hatch for composition-root edges — forbidden contracts are transitive by design, and the composition root is the single legitimate bridge between interface layers and adapters
  - FastMCP's `call_tool()` returns `(content_blocks, structured_dict)` — the structured dict is the right assertion target for unit tests, letting tests bypass the JSON-RPC layer entirely while still exercising the full handler chain
  - Subprocess integration tests for stdio-based MCP servers take ~1 second per spawn (loading vidscope + mcp + pydantic + starlette) — fast enough for CI, slow enough that they belong in the integration marker and not the default suite
  - Jaccard similarity on keyword sets is a surprisingly good v1 suggestion algorithm — the quality ceiling is the analyzer quality, not the similarity function
---

# M002: MCP server and related-video suggestions

**Shipped the MCP server (6 tools wrapping existing use cases) and the related-video suggestion engine (Jaccard keyword overlap). AI agents can now drive the vidscope library in conversation via Claude Desktop, Cline, or any stdio MCP client.**

## What Happened

M002 ships in 3 slices, 10 tasks, ~1000 lines of production code + tests. The entire milestone is a pure additive extension of M001 — zero business logic changes, zero adapter modifications, zero container refactoring. The hexagonal architecture from M001/S01 paid for itself exactly as predicted: every new feature slotted into its own layer as a thin wrapper around existing use cases.

**S01 — MCP server foundation**: Added the `mcp` SDK 1.27.0 as a runtime dependency, built `src/vidscope/mcp/` with a `build_mcp_server(container)` factory that registers 5 tools (ingest, search, get_video, list_videos, get_status) via FastMCP's `@mcp.tool()` decorator. Each tool is ~10 lines: instantiate a use case, call execute, convert the DTO to a JSON-serializable dict, translate DomainError to ValueError for the MCP error channel. Added `vidscope mcp serve` CLI subcommand via a Typer sub-application with lazy import (keeps `vidscope --help` fast). Extended doctor with a 4th check for the mcp SDK. Added a new import-linter `mcp` layer + `mcp-has-no-adapters` forbidden contract. Subprocess integration tests spawn `python -m vidscope.mcp.server` and exchange real JSON-RPC via the mcp ClientSession. 14 unit + 2 subprocess tests.

**S02 — Suggestion engine**: Implemented SuggestRelatedUseCase with Jaccard similarity on the heuristic analyzer's keyword sets. Algorithm is pure stdlib (frozenset operations), scans up to 500 candidates, skips zero scores, sorts descending, clamps to a configurable limit. Exposed via `vidscope suggest <id>` CLI (rich table with score as percentage + matched keywords) and `vidscope_suggest_related` MCP tool (6th tool). 11 unit tests on the use case + 3 MCP tool tests + CLI tests + subprocess integration test updated to expect 6 tools. R023 validated.

**S03 — Docs + closure**: Wrote docs/mcp.md (287 lines) covering MCP overview, 6 tools with exact JSON return shapes, Claude Desktop + Cline configuration snippets, example agent session, troubleshooting, security notes. Shipped scripts/verify-m002.sh as the authoritative milestone gate: 10 steps combining quality gates + unit tests + MCP subprocess integration + a real end-to-end demo that seeds 2 overlapping videos via the repository layer and runs `vidscope suggest` to verify the CLI output contains the expected matching video.

**State at end of M002:**
- 370 unit tests + 3 architecture + 2 MCP subprocess + 3 live ingest tests (all green)
- 70 source files mypy-strict clean
- 8 import-linter contracts enforced (up from 7 in M001)
- 8 CLI commands: add, show, list, search, status, doctor, suggest, mcp
- 6 MCP tools: vidscope_ingest, vidscope_search, vidscope_get_video, vidscope_list_videos, vidscope_get_status, vidscope_suggest_related
- 3 user-facing docs: quickstart.md, cookies.md, mcp.md
- 8 verification scripts: verify-s01..s07 + verify-m001 + verify-m002

**What the user has today**: everything from M001 (full 5-stage pipeline, CLI, FTS5 search, cookie-based Instagram auth) plus an MCP server that any AI agent can connect to via stdio, plus a suggestion engine that finds related videos by keyword overlap. The architectural invariants are still enforced mechanically: MCP never imports adapters directly, use cases have zero interface knowledge, the container is the single composition root for every wiring decision.

**Real end-to-end evidence**: verify-m002.sh step 10 seeds 2 videos with overlapping analyses (Python cooking + Python recipe), runs `vidscope suggest 1`, and grep-asserts the output contains "Python recipe collection" with the correct Jaccard score (40%) and matched keywords (python, recipe). Full run exits 0 in ~12 seconds on the dev machine.

## Success Criteria Results

## Success Criteria Results

| Criterion | Status | Evidence |
|-----------|--------|----------|
| AI agent can connect via stdio | ✅ | Subprocess integration test with real mcp ClientSession + list_tools + call_tool round-trip |
| vidscope_ingest wraps IngestVideoUseCase | ✅ | Unit tested; returns structured dict with status/video_id/platform/title/author/duration |
| vidscope_search returns ranked FTS5 hits | ✅ | Unit tested; seeded library returns hits from transcript + analysis_summary sources |
| vidscope_get_video returns full record | ✅ | Unit tested; returns found=true + video + transcript + frame_count + analysis |
| vidscope_list_videos returns recent videos | ✅ | Unit tested empty + populated |
| vidscope_get_status returns recent runs | ✅ | Unit tested; also exercised via subprocess round-trip |
| vidscope_suggest_related returns ranked suggestions | ✅ | Unit tested on 3-video seeded library; matched video in results, unrelated excluded, Jaccard score correct |
| vidscope suggest CLI subcommand | ✅ | Shipped with rich table; verified manually + in verify-m002.sh demo |
| vidscope mcp serve CLI subcommand | ✅ | Shipped as Typer sub-application with lazy import |
| Quality gates clean | ✅ | 370 unit + 3 architecture tests, ruff/mypy strict/lint-imports (8 contracts) all green |
| R020 + R023 validated | ✅ | Both have live runtime evidence via verify-m002.sh |
| M001 pipeline + CLI work without regression | ✅ | All 337 M001 tests still pass unchanged |

## Definition of Done Results

## Definition of Done Results

- **Every slice S01-S03 complete with summary** ✅ — 3 slices, all marked ✅ with SUMMARY.md
- **MCP server exposes at least 6 tools** ✅ — Exactly 6: ingest, search, get_video, list_videos, get_status, suggest_related
- **`vidscope mcp serve` starts the server and responds to list_tools** ✅ — Subprocess integration test `test_mcp_server_responds_to_list_tools_over_stdio` passes
- **`vidscope suggest <id>` returns ranked related videos** ✅ — CLI command tested + end-to-end demo in verify-m002.sh
- **Subprocess integration test spawns the server + exchanges JSON-RPC** ✅ — 2 tests, both passing in ~1.8s
- **All four quality gates clean including new import-linter contract** ✅ — 8 contracts, 0 broken
- **docs/mcp.md explains Claude Desktop / Cline integration** ✅ — 287 lines, both configs documented
- **R020 and R023 validated with live evidence** ✅ — verify-m002.sh 10/10 green

## Requirement Outcomes

## Requirement Outcomes

| ID | Outcome | Evidence |
|----|---------|----------|
| R020 | **VALIDATED** | MCP server with 6 tools shipped. docs/mcp.md explains Claude Desktop + Cline integration. Subprocess integration tests prove the JSON-RPC transport works. |
| R023 | **VALIDATED** | SuggestRelatedUseCase with Jaccard overlap. Exposed via CLI and MCP. verify-m002.sh demo seeds 2 videos and confirms the suggestion returns the expected match. |

**Still deferred**: R021 (watchlist monitoring → M003), R022 (scheduled refresh → M003), R024 (LLM analyzers → M004), R026 (semantic search → later).

**M001 validations unchanged**: R001 (YouTube + TikTok + Instagram with cookies), R002, R003, R004, R005, R006, R007, R008, R009, R010, R025.

## Deviations

None.

## Follow-ups

None.
