"""Subprocess integration test for the MCP server.

Spawns ``python -m vidscope.mcp.server`` as a subprocess, connects
to it via the mcp Python SDK's stdio client, exchanges a real
JSON-RPC round-trip (tools/list), and asserts the response contains
the 5 expected tool names.

This is the proof that the server actually responds over stdio —
unit tests cover the tool handlers in-process, this test covers the
transport layer.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def _list_tools_via_subprocess(
    env: dict[str, str],
) -> set[str]:
    """Spawn the MCP server as a subprocess, list tools, return names."""
    params = StdioServerParameters(
        command="python",
        args=["-m", "vidscope.mcp.server"],
        env=env,
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools_result = await session.list_tools()
        return {tool.name for tool in tools_result.tools}


@pytest.mark.integration
def test_mcp_server_responds_to_list_tools_over_stdio(
    tmp_path: Path,
) -> None:
    """Spawn the MCP server subprocess and verify 5 tools are exposed
    via real JSON-RPC over stdio.

    Sandboxed via VIDSCOPE_DATA_DIR so the subprocess has a clean DB.
    """
    env = os.environ.copy()
    env["VIDSCOPE_DATA_DIR"] = str(tmp_path)

    tool_names = asyncio.run(_list_tools_via_subprocess(env))

    expected = {
        "vidscope_ingest",
        "vidscope_search",
        "vidscope_get_video",
        "vidscope_list_videos",
        "vidscope_get_status",
        "vidscope_suggest_related",
    }
    assert tool_names == expected, (
        f"tool names mismatch: got {tool_names}, expected {expected}"
    )


@pytest.mark.integration
def test_mcp_server_can_call_get_status_over_stdio(
    tmp_path: Path,
) -> None:
    """Spawn the server + call vidscope_get_status on an empty DB +
    verify the structured response is a sane dict."""
    env = os.environ.copy()
    env["VIDSCOPE_DATA_DIR"] = str(tmp_path)

    async def _call() -> dict[str, object]:
        params = StdioServerParameters(
            command="python",
            args=["-m", "vidscope.mcp.server"],
            env=env,
        )
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(
                "vidscope_get_status", {"limit": 10}
            )
            # result.structuredContent contains the dict from our tool
            return dict(result.structuredContent or {})

    structured = asyncio.run(_call())
    assert structured.get("total_runs") == 0
    assert structured.get("total_videos") == 0
    assert structured.get("runs") == []
