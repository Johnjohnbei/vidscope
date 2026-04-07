---
id: T02
parent: S01
milestone: M002
key_files:
  - src/vidscope/mcp/__init__.py
  - src/vidscope/mcp/server.py
  - tests/unit/mcp/test_server.py
key_decisions:
  - `build_mcp_server(container) -> FastMCP` factory pattern lets tests pass a sandboxed container without monkeypatching — same trick as container composition root
  - Each tool is ~10 lines: instantiate use case, call execute, convert DTO to dict, catch DomainError → ValueError. Zero new business logic.
  - Explicit `_video_to_dict` helper + inline dict comprehensions instead of relying on FastMCP auto-serialization — the contract is visible in the source
  - Typed DomainError translated to ValueError at the MCP boundary. FastMCP surfaces ValueError as a tool error to the client with the message intact.
  - Tests use `asyncio.run(server.call_tool(...))` which returns (content_blocks, structured_dict). The dict is the assertion target — no stdio, no JSON-RPC, no subprocess.
duration: 
verification_result: passed
completed_at: 2026-04-07T17:11:28.250Z
blocker_discovered: false
---

# T02: Shipped vidscope.mcp.server with 5 FastMCP tools wrapping the existing M001 use cases. 14 unit tests using call_tool() against a sandboxed container — no stdio, no network. 351 tests total green.

**Shipped vidscope.mcp.server with 5 FastMCP tools wrapping the existing M001 use cases. 14 unit tests using call_tool() against a sandboxed container — no stdio, no network. 351 tests total green.**

## What Happened

The MCP server is a new interface layer on top of the M001 use cases — zero new business logic, just 5 wrappers. Each tool: (1) captures the injected container in a closure via `build_mcp_server(container)`, (2) instantiates the matching use case, (3) calls execute, (4) converts the typed DTO to a JSON-serializable dict. Typed DomainError is caught and re-raised as ValueError so FastMCP can surface it as a tool error to the client.

The factory pattern — `build_mcp_server(container) -> FastMCP` — is the key design choice. It lets tests construct a sandboxed container and pass it in without any monkeypatching. Production uses `main()` which builds a real container via `build_container()` and calls `mcp.run()` for stdio.

**5 tools registered:**
- `vidscope_ingest(url)` → IngestVideoUseCase → dict with status, video_id, platform, title, author, duration
- `vidscope_search(query, limit)` → SearchLibraryUseCase → dict with hits (video_id + source + snippet + rank)
- `vidscope_get_video(video_id)` → ShowVideoUseCase → dict with full record (video + transcript + frame_count + analysis)
- `vidscope_list_videos(limit)` → ListVideosUseCase → dict with total + videos
- `vidscope_get_status(limit)` → GetStatusUseCase → dict with total_runs + total_videos + runs

**DTO → dict conversion** is explicit via a `_video_to_dict()` helper plus inline dict comprehensions. The MCP SDK handles serialization automatically, but doing it explicitly makes the contract visible in the source — a future agent reading the file knows exactly what the tool returns without tracing through pydantic.

**Test strategy** uses `asyncio.run(server.call_tool(name, args))` which returns a `(content_blocks, structured_dict)` tuple. The second element is the raw dict result we assert against. No stdio, no JSON-RPC serialization, no subprocess — just the tool handler called directly through the FastMCP API.

**14 tests pass in 830ms:**
- TestBuildMcpServer (3): server has the right name, registers exactly 5 tools, every tool has a description and input schema
- TestVidscopeGetStatus (2): empty library returns zeros, populated library returns the seeded run
- TestVidscopeListVideos (2): empty + populated
- TestVidscopeGetVideo (2): missing id returns `found=False`, existing id returns full record with transcript + analysis
- TestVidscopeSearch (3): empty query returns empty, matching query returns hits from transcript + analysis_summary, no-match returns empty
- TestVidscopeIngest (2): empty URL returns failed, unsupported URL (vimeo) returns failed with 'unsupported' in the message

The ingest tests don't call real yt-dlp because the error path returns before any network call — empty URL is rejected upfront, vimeo.com is rejected by detect_platform in the IngestStage. Full ingest with live network is out of scope for unit tests; the subprocess integration test in T05 handles that.

**Quality gates:** 351 passed, 3 deselected, 5 ruff auto-fixes (imports + minor format), mypy strict clean on 67 source files, import-linter 7 contracts kept.

## Verification

Ran `python -m uv run pytest tests/unit/mcp -q` → 14 passed in 830ms. Ran full suite → 351 passed, 3 deselected. Ran ruff/mypy/lint-imports → all clean after 5 auto-fixes. Manual smoke via inline `python -c` confirmed server.name='vidscope' and list_tools returns the 5 expected tool names.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/unit/mcp -q` | 0 | ✅ 14/14 MCP unit tests green | 830ms |
| 2 | `python -m uv run pytest -q` | 0 | ✅ 351 passed, 3 deselected (full suite) | 3200ms |
| 3 | `ruff + mypy + lint-imports` | 0 | ✅ all 4 quality gates clean | 4000ms |

## Deviations

None.

## Known Issues

None. The MCP tools work end-to-end with the sandboxed container. The import-linter doesn't yet have a specific rule for the mcp layer — that comes in T04.

## Files Created/Modified

- `src/vidscope/mcp/__init__.py`
- `src/vidscope/mcp/server.py`
- `tests/unit/mcp/test_server.py`
