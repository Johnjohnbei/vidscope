---
id: T05
parent: S01
milestone: M002
key_files:
  - tests/integration/test_mcp_server.py
key_decisions:
  - Use `python -m vidscope.mcp.server` as the subprocess command rather than the installed `vidscope` entry point — no dependency on the installed script, works from a fresh checkout
  - Sandbox via `env['VIDSCOPE_DATA_DIR'] = str(tmp_path)` in the subprocess environment — isolates the spawned server's DB from any other test or the user's real data
  - Test asserts structured content (result.structuredContent) not text content blocks — this is the typed round-trip that matters for MCP tool usage
  - Two tests: one for transport handshake (list_tools) and one for tool execution (call_tool get_status) — covers both the protocol layer and the handler layer
  - Combined `async with` statements via SIM117 auto-fix for the modern Python 3.12+ idiom
duration: 
verification_result: passed
completed_at: 2026-04-07T17:18:43.249Z
blocker_discovered: false
---

# T05: Shipped tests/integration/test_mcp_server.py with 2 subprocess integration tests that spawn the MCP server via `python -m vidscope.mcp.server` and exchange real JSON-RPC over stdio. Both pass in 1.79s.

**Shipped tests/integration/test_mcp_server.py with 2 subprocess integration tests that spawn the MCP server via `python -m vidscope.mcp.server` and exchange real JSON-RPC over stdio. Both pass in 1.79s.**

## What Happened

The subprocess integration tests are the proof that the MCP server actually responds to JSON-RPC over stdio — unit tests in T02 cover the handlers in-process, this test covers the transport layer.

Each test spawns `python -m vidscope.mcp.server` via `StdioServerParameters` from the mcp SDK, wraps the subprocess in a `ClientSession`, calls `session.initialize()` for the MCP handshake, then invokes a method:

- **test_mcp_server_responds_to_list_tools_over_stdio** calls `session.list_tools()` and asserts the returned set is exactly `{vidscope_ingest, vidscope_search, vidscope_get_video, vidscope_list_videos, vidscope_get_status}`. This is the simplest possible proof that JSON-RPC round-trip works.

- **test_mcp_server_can_call_get_status_over_stdio** goes one step further: calls `session.call_tool("vidscope_get_status", {"limit": 10})` and reads `result.structuredContent` (the dict the server returned). On a fresh sandboxed DB it asserts `total_runs == 0`, `total_videos == 0`, `runs == []`. This proves the tool handler executes through the full JSON-RPC stack and returns the same structured data the unit tests assert on.

**Sandbox isolation**: both tests get a `tmp_path` and set `VIDSCOPE_DATA_DIR` in the subprocess environment so the spawned server uses an isolated DB. The parent test environment is copied via `os.environ.copy()` then overridden.

**Runtime**: 1.79s for both tests. The subprocess startup is ~800ms because it has to load vidscope + mcp + pydantic + starlette + sqlalchemy + all the adapters. Once running, the round-trip is fast.

**Ruff auto-fix**: one SIM117 "combine with statements" fix on the second test (combined the nested `async with stdio_client / ClientSession` into a single async with clause — the modern Python 3.12+ idiom).

**Gate results**: 353 unit tests pass (unchanged), 2 new MCP integration tests pass, ruff/mypy/lint-imports all clean.

**Deselected count** is now `5 deselected` because the 3 existing live integration tests (Instagram/TikTok/YouTube) + the 2 new MCP subprocess tests all have `@pytest.mark.integration`. They run on demand via `pytest -m integration` but skip by default.

## Verification

Ran `python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v` → 2 passed in 1.79s. Ran `python -m uv run pytest -q` → 353 passed, 5 deselected. Ran ruff → All checks passed after one SIM117 fix. mypy + lint-imports remain clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run pytest tests/integration/test_mcp_server.py -m integration -v` | 0 | ✅ 2/2 subprocess MCP tests green in 1.79s | 1790ms |
| 2 | `python -m uv run pytest -q` | 0 | ✅ 353 passed, 5 deselected (3 live ingest + 2 MCP subprocess) | 3170ms |

## Deviations

None.

## Known Issues

Integration tests take ~1 second each because of the subprocess startup cost (vidscope + mcp + pydantic + starlette all load on every spawn). Acceptable for an integration test that only runs on demand.

## Files Created/Modified

- `tests/integration/test_mcp_server.py`
