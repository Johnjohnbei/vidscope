"""Unit tests for MCP tool `vidscope_trending` (M009/S04).

Tests validate that:
- The tool is registered in the FastMCP server.
- A valid call returns a list of JSON-serializable dicts.
- An invalid `since` string raises ValueError.
- An invalid `platform` string raises ValueError.
- `limit < 1` raises ValueError.

These tests call the tool handler directly (not via stdio) using the
FastMCP async API, consistent with the patterns in test_server.py.

Note: FastMCP's call_tool returns (raw_content, structured_content).
For tools returning list, structured_content = {'result': list}.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vidscope.infrastructure.config import reset_config_cache
from vidscope.infrastructure.container import Container, build_container
from vidscope.mcp.server import build_mcp_server


@pytest.fixture()
def sandboxed_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Container:
    """Build a fresh container rooted at tmp_path."""
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    reset_config_cache()
    try:
        return build_container()
    finally:
        reset_config_cache()


def _call_trending(server, **kwargs) -> list:  # type: ignore[no-untyped-def]
    """Call vidscope_trending and extract the list result.

    FastMCP wraps list returns in {'result': [...]}.
    """
    raw, structured = asyncio.run(server.call_tool("vidscope_trending", kwargs))
    # Structured is {'result': [...]} for list-returning tools
    if isinstance(structured, dict) and "result" in structured:
        return structured["result"]
    # Fallback: raw may be the list directly
    return list(raw) if raw else []


# ---------------------------------------------------------------------------
# Registration check
# ---------------------------------------------------------------------------


class TestTrendingToolRegistration:
    def test_trending_tool_registered(self, sandboxed_container: Container) -> None:
        """vidscope_trending must appear in the tool list."""
        server = build_mcp_server(sandboxed_container)
        tools = asyncio.run(server.list_tools())
        names = {tool.name for tool in tools}
        assert "vidscope_trending" in names

    def test_trending_tool_has_description(
        self, sandboxed_container: Container
    ) -> None:
        """vidscope_trending must have a non-empty description."""
        server = build_mcp_server(sandboxed_container)
        tools = asyncio.run(server.list_tools())
        tool = next(t for t in tools if t.name == "vidscope_trending")
        assert tool.description

    def test_total_tools_is_seven(self, sandboxed_container: Container) -> None:
        """After S04, server must register exactly 7 tools."""
        server = build_mcp_server(sandboxed_container)
        tools = asyncio.run(server.list_tools())
        names = {tool.name for tool in tools}
        assert names == {
            "vidscope_ingest",
            "vidscope_search",
            "vidscope_get_video",
            "vidscope_list_videos",
            "vidscope_get_status",
            "vidscope_suggest_related",
            "vidscope_trending",
        }


# ---------------------------------------------------------------------------
# Happy path — empty library returns empty list
# ---------------------------------------------------------------------------


class TestTrendingToolHappyPath:
    def test_empty_library_returns_empty_list(
        self, sandboxed_container: Container
    ) -> None:
        """Empty DB -> vidscope_trending returns [] (no crash)."""
        server = build_mcp_server(sandboxed_container)
        result = _call_trending(server, since="7d")
        assert isinstance(result, list)
        assert result == []

    def test_result_is_json_serializable(
        self, sandboxed_container: Container
    ) -> None:
        """The return value of vidscope_trending must be JSON-serializable."""
        server = build_mcp_server(sandboxed_container)
        result = _call_trending(server, since="7d", limit=5)
        # This must not raise
        json.dumps(result)

    def test_result_contains_expected_keys_when_populated(
        self, sandboxed_container: Container
    ) -> None:
        """Each entry in result has the required keys including ISO-8601 timestamps."""
        from vidscope.application.list_trending import TrendingEntry
        from vidscope.domain import Platform

        entry = TrendingEntry(
            video_id=7,
            platform=Platform.YOUTUBE,
            title="Test trending",
            views_velocity_24h=1500.0,
            engagement_rate=0.08,
            last_captured_at=datetime(2026, 1, 1, tzinfo=UTC),
            latest_view_count=2000,
            latest_like_count=100,
        )

        import vidscope.mcp.server as srv

        class _UC:
            def __init__(self, **kw: object) -> None:
                pass

            def execute(self, **kw: object) -> list:
                return [entry]

        from pytest import MonkeyPatch

        mp = MonkeyPatch()
        try:
            mp.setattr(srv, "ListTrendingUseCase", _UC)
            server = build_mcp_server(sandboxed_container)
            result = _call_trending(server, since="7d", limit=10)
            assert isinstance(result, list)
            assert len(result) == 1
            row = result[0]
            assert row["video_id"] == 7
            assert row["platform"] == "youtube"
            assert row["title"] == "Test trending"
            assert row["views_velocity_24h"] == pytest.approx(1500.0)
            assert row["engagement_rate"] == pytest.approx(0.08)
            assert "last_captured_at" in row
            # Timestamps must be ISO-8601 strings (JSON-serializable)
            assert isinstance(row["last_captured_at"], str)
            json.dumps(result)
        finally:
            mp.undo()


# ---------------------------------------------------------------------------
# Validation errors — FastMCP wraps tool errors, so we check via call_tool
# ---------------------------------------------------------------------------


class TestTrendingToolValidation:
    def test_invalid_since_format_raises(
        self, sandboxed_container: Container
    ) -> None:
        """since='1week' must cause an error (T-INPUT-02)."""
        server = build_mcp_server(sandboxed_container)
        with pytest.raises(Exception):
            asyncio.run(
                server.call_tool("vidscope_trending", {"since": "1week"})
            )

    def test_invalid_platform_raises(
        self, sandboxed_container: Container
    ) -> None:
        """platform='myspace' must cause an error (T-INPUT-03)."""
        server = build_mcp_server(sandboxed_container)
        with pytest.raises(Exception):
            asyncio.run(
                server.call_tool(
                    "vidscope_trending", {"since": "7d", "platform": "myspace"}
                )
            )

    def test_limit_zero_raises(self, sandboxed_container: Container) -> None:
        """limit=0 must cause an error (T-INPUT-01)."""
        server = build_mcp_server(sandboxed_container)
        with pytest.raises(Exception):
            asyncio.run(
                server.call_tool(
                    "vidscope_trending", {"since": "7d", "limit": 0}
                )
            )

    def test_negative_since_value_raises(
        self, sandboxed_container: Container
    ) -> None:
        """since='-1d' must cause an error (strict parser, T-INPUT-02)."""
        server = build_mcp_server(sandboxed_container)
        with pytest.raises(Exception):
            asyncio.run(
                server.call_tool("vidscope_trending", {"since": "-1d"})
            )
