---
id: T01
parent: S01
milestone: M002
key_files:
  - pyproject.toml
  - uv.lock
key_decisions:
  - Use the official /modelcontextprotocol/python-sdk (1.27.0) via FastMCP API — the documented stable entry point
  - Add mcp submodules to mypy ignore_missing_imports like yt_dlp/faster_whisper — the SDK's pydantic types confuse mypy strict, the pragmatic move is to silence it rather than wrestle the type stubs
duration: 
verification_result: passed
completed_at: 2026-04-07T17:08:24.126Z
blocker_discovered: false
---

# T01: Added mcp SDK 1.27.0 as a runtime dependency, declared compatible-release specifier, added mcp modules to mypy ignore_missing_imports. 337 tests still green.

**Added mcp SDK 1.27.0 as a runtime dependency, declared compatible-release specifier, added mcp modules to mypy ignore_missing_imports. 337 tests still green.**

## What Happened

Ran `python -m uv add mcp` which installed mcp 1.27.0 plus its transitive deps (pydantic, starlette, uvicorn, httpx-sse, sse-starlette, python-multipart, jsonschema, pydantic-settings, referencing, rpds-py, etc. — ~20 packages). Verified the public API surface we need is importable: `FastMCP`, `ClientSession`, `stdio_client`, `StdioServerParameters`. Relaxed the pyproject specifier from `>=1.27.0` to `>=1.27,<2` to match the project's compatible-release convention. Added the five mcp submodules we will touch (mcp, mcp.server.fastmcp, mcp.client.session, mcp.client.stdio, mcp.types) to mypy's `ignore_missing_imports` overrides — the mcp SDK ships type hints but some pydantic-generated types confuse mypy's strict mode, so the safe move is to treat it like yt_dlp and faster_whisper. 337 unit tests still pass, no regression from the new dependency tree.

## Verification

Ran `python -m uv run python -c 'from importlib.metadata import version; print(version(\"mcp\"))'` → 1.27.0. Ran imports for FastMCP/ClientSession/stdio_client/StdioServerParameters → ok. Ran `python -m uv sync` → idempotent. Ran `python -m uv run pytest -q` → 337 passed, 3 deselected.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m uv run python -c '<mcp imports>'` | 0 | ✅ mcp 1.27.0 importable, FastMCP + ClientSession + stdio_client all present | 400ms |
| 2 | `python -m uv run pytest -q` | 0 | ✅ 337 passed, 3 deselected | 2900ms |

## Deviations

None.

## Known Issues

mcp SDK pulls in pydantic + starlette + uvicorn even when we only need the stdio transport. That's fine for a dev tool — the dependency footprint is acceptable. A future optimization could switch to `mcp[stdio]` extras if the SDK ever exposes that split.

## Files Created/Modified

- `pyproject.toml`
- `uv.lock`
