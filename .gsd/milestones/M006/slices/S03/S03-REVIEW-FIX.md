---
phase: M006-S03
fixed_at: 2026-04-17T00:00:00Z
review_path: .gsd/milestones/M006/slices/S03/S03-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase M006/S03: Code Review Fix Report

**Fixed at:** 2026-04-17T00:00:00Z
**Source review:** .gsd/milestones/M006/slices/S03/S03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: `total` silently capped at 10,000 in `ListCreatorVideosUseCase`

**Files modified:** `src/vidscope/ports/repositories.py`, `src/vidscope/adapters/sqlite/video_repository.py`, `src/vidscope/application/list_creator_videos.py`
**Commit:** 88618db
**Applied fix:** Added `count_by_creator(creator_id: CreatorId) -> int` to the `VideoRepository` Protocol in `ports/repositories.py`. Implemented it in `VideoRepositorySQLite` using a single `SELECT COUNT(*)` with a `WHERE creator_id = ?` filter. Replaced the double `list_by_creator` call (page fetch + 10,000-cap count fetch) in `ListCreatorVideosUseCase.execute` with `uow.videos.count_by_creator(creator.id)`, giving an accurate unbounded total.

### WR-02: `ListCreatorsUseCase` no-filter path hardcodes platform enum values

**Files modified:** `src/vidscope/application/list_creators.py`
**Commit:** accf34d
**Applied fix:** Replaced the three explicit `list_by_platform` calls for `YOUTUBE`, `TIKTOK`, `INSTAGRAM` with a `for plat in Platform:` loop that extends a local `all_creators` list. New platforms added to the `Platform` enum are now included automatically in the no-filter path without any code change.

### WR-03: MCP creator tool tests access private FastMCP internals

**Files modified:** `tests/unit/mcp/test_server_creator.py`
**Commit:** 894be7c
**Applied fix:** Removed the `_get_tool` helper that accessed `mcp._tool_manager._tools`. Replaced it with a `_call_tool(container, name, args)` helper that uses `asyncio.run(server.call_tool(name, args))` — the same public API pattern already established in `test_server.py`. Updated all 8 test methods to call `_call_tool` directly. The `test_invalid_platform_raises_value_error` test was updated to catch `mcp.server.fastmcp.exceptions.ToolError` (FastMCP wraps `ValueError` raised inside tool functions as `ToolError`). The `test_tool_registered_in_build_mcp_server` test was updated to use `asyncio.run(server.list_tools())` instead of `mcp._tool_manager._tools`. All 8 tests pass.

---

_Fixed: 2026-04-17T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
