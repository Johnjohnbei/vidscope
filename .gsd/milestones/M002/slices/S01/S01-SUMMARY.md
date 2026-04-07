---
id: S01
parent: M002
milestone: M002
provides:
  - vidscope.mcp package with build_mcp_server factory + main entry point
  - 5 registered MCP tools: vidscope_ingest, vidscope_search, vidscope_get_video, vidscope_list_videos, vidscope_get_status
  - vidscope mcp serve CLI subcommand via Typer sub-application
  - check_mcp_sdk() in doctor for SDK version reporting
  - import-linter mcp-has-no-adapters forbidden contract + mcp layer in the layered architecture
  - Subprocess integration test pattern for stdio-based MCP servers
requires:
  - slice: M001 final state
    provides: All 5 use cases + Container composition root that S01 wraps as MCP tools
affects:
  - S02 (suggest_related) — adds the 6th tool to the same FastMCP instance by extending build_mcp_server
  - S03 (docs + verify) — ships docs/mcp.md with Claude Desktop / Cline config and verify-m002.sh as the milestone gate
key_files:
  - src/vidscope/mcp/__init__.py
  - src/vidscope/mcp/server.py
  - src/vidscope/cli/commands/mcp.py
  - src/vidscope/cli/commands/__init__.py
  - src/vidscope/cli/app.py
  - src/vidscope/infrastructure/startup.py
  - pyproject.toml
  - .importlinter
  - tests/unit/mcp/test_server.py
  - tests/unit/infrastructure/test_startup.py
  - tests/architecture/test_layering.py
  - tests/integration/test_mcp_server.py
key_decisions:
  - `build_mcp_server(container) -> FastMCP` factory pattern lets tests pass a sandboxed container without monkeypatching — mirrors the container composition root from M001
  - Each tool is ~10 lines wrapping a use case — no new business logic in the MCP layer
  - Typed DomainError translated to ValueError at the MCP boundary; FastMCP surfaces these as tool errors
  - Lazy import of `vidscope.mcp.server.main` in the CLI serve command keeps `vidscope --help` fast
  - CLI sits above MCP in the layer stack (not siblings) so the CLI can delegate to the MCP server for startup
  - Forbidden contract uses `ignore_imports` to whitelist the composition-root edge `mcp.server -> infrastructure.container` — any NEW direct mcp → adapter import would still be rejected
  - Subprocess integration tests spawn `python -m vidscope.mcp.server` and exchange real JSON-RPC via the mcp ClientSession — covers the transport layer that unit tests cannot
patterns_established:
  - Interface layer pattern: a new package at the top of the layer stack (cli, mcp, future http) wraps existing use cases without adding business logic. Each future interface slots in via the same pattern.
  - FastMCP factory with container injection: build_mcp_server(container) captures the container in closures so tests never monkeypatch globals
  - Subprocess integration test for stdio servers: spawn via StdioServerParameters, wrap in ClientSession, call methods, assert on structured content
observability_surfaces:
  - vidscope doctor now reports mcp SDK version as its 4th check
  - MCP server errors go to stderr when run as a subprocess; stdout is reserved for JSON-RPC traffic
drill_down_paths:
  - .gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T04-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-07T17:20:06.634Z
blocker_discovered: false
---

# S01: MCP server foundation with 5 read-only tools

**Shipped the MCP server: 5 tools wrapping existing M001 use cases, `vidscope mcp serve` CLI, import-linter layer contract, and subprocess integration tests exchanging real JSON-RPC over stdio. 353 unit + 3 architecture + 2 subprocess MCP tests green.**

## What Happened

S01 ships the MCP server foundation in 5 tasks. The interface layer wraps the existing M001 use cases without introducing any new business logic — that's the payoff of the hexagonal architecture we posed in M001/S01. The entire server is ~250 lines of code because each tool is a ~10-line handler.

**T01**: Added `mcp>=1.27,<2` runtime dependency. Verified FastMCP + ClientSession + stdio_client all importable. Added mcp submodules to mypy's ignore_missing_imports (SDK pydantic types confuse mypy strict). 337 tests stayed green.

**T02**: Built `src/vidscope/mcp/server.py` with `build_mcp_server(container) -> FastMCP` factory. Registered 5 tools (`vidscope_ingest`, `vidscope_search`, `vidscope_get_video`, `vidscope_list_videos`, `vidscope_get_status`) each wrapping a use case + converting the DTO to a JSON-serializable dict + translating DomainError to ValueError for MCP error surface. `main()` builds the production container and calls `mcp.run()` for stdio. 14 unit tests using `asyncio.run(server.call_tool(...))` call handlers directly with a sandboxed container — no stdio, no subprocess.

**T03**: Added `vidscope mcp serve` CLI subcommand via a Typer sub-application with lazy import of the server module (keeps `vidscope --help` fast). Added `check_mcp_sdk()` to startup checks — doctor now shows 4 rows: ffmpeg + yt-dlp + mcp 1.27.0 + cookies. Updated tests to expect 4 checks.

**T04**: Extended import-linter with the `mcp` layer (between cli and application in the stack) and a new `mcp-has-no-adapters` forbidden contract. First attempt used sibling syntax `cli | mcp` which broke `vidscope mcp serve` (CLI importing MCP). Corrected to vertical ordering with CLI above MCP. Whitelisted the transitive `vidscope.mcp.server -> vidscope.infrastructure.container` path via `ignore_imports` because that's the legitimate composition-root edge. 8 contracts now enforced (up from 7). Architecture test updated with the new contract name in `EXPECTED_CONTRACTS`.

**T05**: Shipped `tests/integration/test_mcp_server.py` with 2 subprocess tests: `test_mcp_server_responds_to_list_tools_over_stdio` (verifies 5 tools are listed via JSON-RPC round-trip) and `test_mcp_server_can_call_get_status_over_stdio` (verifies tool execution returns structured content on a sandboxed empty DB). Both pass in 1.79s including subprocess startup (~800ms per spawn).

**Quality gates at end of S01:**
- 353 unit tests + 3 architecture + 2 MCP subprocess integration tests (total 5 deselected because 3 live ingest + 2 MCP subprocess all have `@pytest.mark.integration`)
- ruff clean
- mypy strict clean on 68 source files
- import-linter 8 contracts kept

**What the user has**: `vidscope mcp serve` starts a working MCP server that an AI agent (Claude Desktop, Cline, any stdio MCP client) can connect to. The agent can call any of the 5 read-only tools. The server shares the exact same container as the CLI — no duplication of business logic, no divergence of behavior between interfaces.

The factory pattern `build_mcp_server(container)` pays for itself in the test suite: every unit test constructs a sandboxed container, passes it to the factory, calls tools directly via `call_tool()`. No monkeypatching, no global state, no stdio complications at the unit-test layer.

## Verification

Ran `python -m uv run pytest -q` → 353 passed, 5 deselected in 3.17s. Ran `python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v` → 2 passed in 1.79s. Ran `python -m uv run vidscope doctor` → 4 rows green (ffmpeg + yt-dlp + mcp 1.27.0 + cookies). Ran `python -m uv run vidscope mcp --help` → sub-app with `serve` command visible. Ran `python -m uv run lint-imports` → 8 contracts kept, 0 broken. Ruff/mypy strict all clean on 68 source files.

## Requirements Advanced

- R020 — MCP server with 5/6 required tools shipped and tested. Suggest_related (6th tool) lands in S02.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

First T04 attempt used sibling layering syntax for cli/mcp which broke the CLI → MCP delegation needed for `vidscope mcp serve`. Corrected to vertical ordering with CLI above MCP. Documented in T04's summary.

## Known Limitations

The 5 tools in S01 are all read-only plus ingest — the 6th tool (suggest_related) ships in S02 along with the suggestion engine. No CLI `vidscope suggest` subcommand yet — that's also S02. docs/mcp.md explaining Claude Desktop / Cline integration ships in S03.

## Follow-ups

S02 adds SuggestRelatedUseCase, `vidscope suggest <id>` CLI, and `vidscope_suggest_related` MCP tool. S03 closes the milestone with docs and verify-m002.sh.

## Files Created/Modified

- `pyproject.toml` — Added mcp runtime dep, mcp submodules to mypy ignore_missing_imports
- `src/vidscope/mcp/__init__.py` — New package init
- `src/vidscope/mcp/server.py` — New: FastMCP server factory + 5 tool handlers + main entry point
- `src/vidscope/cli/commands/mcp.py` — New: vidscope mcp serve Typer sub-application
- `src/vidscope/cli/commands/__init__.py` — Re-export mcp_app
- `src/vidscope/cli/app.py` — Register mcp sub-app via add_typer
- `src/vidscope/infrastructure/startup.py` — Added check_mcp_sdk() as 4th doctor check
- `.importlinter` — Added mcp layer in layers contract + new mcp-has-no-adapters forbidden contract
- `tests/architecture/test_layering.py` — Added new contract name to EXPECTED_CONTRACTS
- `tests/unit/mcp/test_server.py` — New: 14 unit tests calling tool handlers via asyncio.run(server.call_tool(...))
- `tests/unit/infrastructure/test_startup.py` — TestCheckMcpSdk + updated TestRunAllChecks to expect 4 results
- `tests/integration/test_mcp_server.py` — New: 2 subprocess integration tests exchanging JSON-RPC via stdio_client
