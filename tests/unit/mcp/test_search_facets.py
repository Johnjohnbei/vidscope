"""Tests for vidscope_search MCP tool — M011/S03 facets (R058).

Calls tool functions directly via the FastMCP tool manager to avoid
stdio transport. No subprocess involved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vidscope.infrastructure.config import reset_config_cache
from vidscope.infrastructure.container import Container, build_container
from vidscope.mcp.server import build_mcp_server


def _resolve_tool(server, name: str):
    """Return the raw tool callable from the FastMCP tool manager."""
    tools = server._tool_manager._tools  # type: ignore[attr-defined]
    return tools[name]


@pytest.fixture()
def sandboxed_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Container:
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    reset_config_cache()
    try:
        return build_container()
    finally:
        reset_config_cache()


class TestMcpSearchFacets:
    def test_accepts_status_param(self, sandboxed_container: Container) -> None:
        server = build_mcp_server(sandboxed_container)
        tool = _resolve_tool(server, "vidscope_search")
        result = tool.fn(query="q", status="saved")
        assert "hits" in result
        assert isinstance(result["hits"], list)

    def test_invalid_status_raises_value_error(self, sandboxed_container: Container) -> None:
        server = build_mcp_server(sandboxed_container)
        tool = _resolve_tool(server, "vidscope_search")
        with pytest.raises(ValueError, match="TrackingStatus"):
            tool.fn(query="q", status="bogus")

    def test_all_facets_combined_no_crash(self, sandboxed_container: Container) -> None:
        server = build_mcp_server(sandboxed_container)
        tool = _resolve_tool(server, "vidscope_search")
        result = tool.fn(
            query="q",
            content_type="tutorial",
            min_actionability=50,
            is_sponsored=False,
            status="saved",
            starred=True,
            tag="idea",
            collection="MyCol",
        )
        assert "hits" in result
        assert isinstance(result["hits"], list)

    def test_no_filters_returns_empty_hits_on_empty_db(self, sandboxed_container: Container) -> None:
        server = build_mcp_server(sandboxed_container)
        tool = _resolve_tool(server, "vidscope_search")
        result = tool.fn(query="q")
        assert result["hits"] == []

    def test_starred_true_param(self, sandboxed_container: Container) -> None:
        server = build_mcp_server(sandboxed_container)
        tool = _resolve_tool(server, "vidscope_search")
        result = tool.fn(query="q", starred=True)
        assert isinstance(result["hits"], list)

    def test_starred_false_param(self, sandboxed_container: Container) -> None:
        server = build_mcp_server(sandboxed_container)
        tool = _resolve_tool(server, "vidscope_search")
        result = tool.fn(query="q", starred=False)
        assert isinstance(result["hits"], list)

    def test_tag_param(self, sandboxed_container: Container) -> None:
        server = build_mcp_server(sandboxed_container)
        tool = _resolve_tool(server, "vidscope_search")
        result = tool.fn(query="q", tag="idea")
        assert isinstance(result["hits"], list)

    def test_collection_param(self, sandboxed_container: Container) -> None:
        server = build_mcp_server(sandboxed_container)
        tool = _resolve_tool(server, "vidscope_search")
        result = tool.fn(query="q", collection="MyCol")
        assert isinstance(result["hits"], list)

    def test_invalid_content_type_raises_value_error(self, sandboxed_container: Container) -> None:
        server = build_mcp_server(sandboxed_container)
        tool = _resolve_tool(server, "vidscope_search")
        with pytest.raises(ValueError, match="ContentType"):
            tool.fn(query="q", content_type="podcast")
