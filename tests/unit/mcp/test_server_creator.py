"""Unit tests for vidscope_get_creator MCP tool (M006/S03-P03)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from vidscope.domain import Creator, Platform
from vidscope.domain.values import PlatformUserId
from vidscope.infrastructure.config import reset_config_cache
from vidscope.infrastructure.container import Container, build_container
from vidscope.mcp.server import build_mcp_server


@pytest.fixture()
def container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Container:
    """Build a fresh sandboxed container for MCP creator tests."""
    monkeypatch.setenv("VIDSCOPE_DATA_DIR", str(tmp_path))
    reset_config_cache()
    try:
        return build_container()
    finally:
        reset_config_cache()


def _insert_creator(
    container: Container,
    handle: str = "@alice",
    platform: Platform = Platform.YOUTUBE,
    platform_user_id: str = "UC_alice",
    follower_count: int | None = 42000,
) -> Creator:
    creator = Creator(
        platform=platform,
        platform_user_id=PlatformUserId(platform_user_id),
        handle=handle,
        display_name=handle.lstrip("@").title(),
        follower_count=follower_count,
        first_seen_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_seen_at=datetime(2026, 4, 1, tzinfo=UTC),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with container.unit_of_work() as uow:
        return uow.creators.upsert(creator)


def _call_tool(container: Container, name: str, args: dict) -> dict:  # type: ignore[no-untyped-def]
    """Call an MCP tool via the public call_tool API and return the result dict."""
    server = build_mcp_server(container)
    _, structured = asyncio.run(server.call_tool(name, args))
    assert isinstance(structured, dict)
    return structured


class TestVidscopeGetCreatorTool:
    def test_found_returns_creator_dict(self, container: Container) -> None:
        _insert_creator(container, "@alice")
        result = _call_tool(container, "vidscope_get_creator",
                            {"handle": "@alice", "platform": "youtube"})

        assert result["found"] is True
        assert "creator" in result
        assert result["creator"]["handle"] == "@alice"
        assert result["creator"]["platform"] == "youtube"

    def test_not_found_returns_found_false(self, container: Container) -> None:
        result = _call_tool(container, "vidscope_get_creator",
                            {"handle": "@ghost", "platform": "youtube"})

        assert result["found"] is False
        assert result["handle"] == "@ghost"

    def test_creator_dict_includes_follower_count(self, container: Container) -> None:
        _insert_creator(container, "@rich", follower_count=100000, platform_user_id="rich")
        result = _call_tool(container, "vidscope_get_creator",
                            {"handle": "@rich", "platform": "youtube"})

        assert result["found"] is True
        assert result["creator"]["follower_count"] == 100000

    def test_invalid_platform_raises_value_error(self, container: Container) -> None:
        # FastMCP wraps ValueError raised inside tool functions as ToolError.
        with pytest.raises(ToolError, match="unknown platform"):
            _call_tool(container, "vidscope_get_creator",
                       {"handle": "@alice", "platform": "snapchat"})

    def test_default_platform_is_youtube(self, container: Container) -> None:
        _insert_creator(container, "@yt", Platform.YOUTUBE, "yt")
        # Call without platform arg — defaults to youtube
        result = _call_tool(container, "vidscope_get_creator", {"handle": "@yt"})
        assert result["found"] is True

    def test_tiktok_platform(self, container: Container) -> None:
        _insert_creator(container, "@tt", Platform.TIKTOK, "tt_uid")
        result = _call_tool(container, "vidscope_get_creator",
                            {"handle": "@tt", "platform": "tiktok"})
        assert result["found"] is True
        assert result["creator"]["platform"] == "tiktok"

    def test_creator_dict_has_all_fields(self, container: Container) -> None:
        _insert_creator(container, "@full", platform_user_id="full")
        result = _call_tool(container, "vidscope_get_creator",
                            {"handle": "@full", "platform": "youtube"})

        creator = result["creator"]
        expected_keys = {
            "id", "platform", "platform_user_id", "handle", "display_name",
            "profile_url", "avatar_url", "follower_count", "is_verified",
            "first_seen_at", "last_seen_at",
        }
        assert expected_keys.issubset(set(creator.keys()))

    def test_tool_registered_in_build_mcp_server(self, container: Container) -> None:
        server = build_mcp_server(container)
        tools = asyncio.run(server.list_tools())
        tool_names = {tool.name for tool in tools}
        assert "vidscope_get_creator" in tool_names
