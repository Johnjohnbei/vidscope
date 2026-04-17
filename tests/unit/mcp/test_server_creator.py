"""Unit tests for vidscope_get_creator MCP tool (M006/S03-P03)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

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


def _get_tool(container: Container, tool_name: str):  # type: ignore[no-untyped-def]
    """Extract a tool function from the FastMCP server instance."""
    mcp = build_mcp_server(container)
    # FastMCP stores tools in _tool_manager._tools dict keyed by name
    tools = mcp._tool_manager._tools
    assert tool_name in tools, (
        f"Tool '{tool_name}' not found. Available: {list(tools.keys())}"
    )
    return tools[tool_name].fn


class TestVidscopeGetCreatorTool:
    def test_found_returns_creator_dict(self, container: Container) -> None:
        _insert_creator(container, "@alice")
        tool_fn = _get_tool(container, "vidscope_get_creator")
        result = tool_fn(handle="@alice", platform="youtube")

        assert result["found"] is True
        assert "creator" in result
        assert result["creator"]["handle"] == "@alice"
        assert result["creator"]["platform"] == "youtube"

    def test_not_found_returns_found_false(self, container: Container) -> None:
        tool_fn = _get_tool(container, "vidscope_get_creator")
        result = tool_fn(handle="@ghost", platform="youtube")

        assert result["found"] is False
        assert result["handle"] == "@ghost"

    def test_creator_dict_includes_follower_count(self, container: Container) -> None:
        _insert_creator(container, "@rich", follower_count=100000, platform_user_id="rich")
        tool_fn = _get_tool(container, "vidscope_get_creator")
        result = tool_fn(handle="@rich", platform="youtube")

        assert result["found"] is True
        assert result["creator"]["follower_count"] == 100000

    def test_invalid_platform_raises_value_error(self, container: Container) -> None:
        tool_fn = _get_tool(container, "vidscope_get_creator")
        with pytest.raises(ValueError, match="unknown platform"):
            tool_fn(handle="@alice", platform="snapchat")

    def test_default_platform_is_youtube(self, container: Container) -> None:
        _insert_creator(container, "@yt", Platform.YOUTUBE, "yt")
        tool_fn = _get_tool(container, "vidscope_get_creator")
        # Call without platform arg — defaults to youtube
        result = tool_fn(handle="@yt")
        assert result["found"] is True

    def test_tiktok_platform(self, container: Container) -> None:
        _insert_creator(container, "@tt", Platform.TIKTOK, "tt_uid")
        tool_fn = _get_tool(container, "vidscope_get_creator")
        result = tool_fn(handle="@tt", platform="tiktok")
        assert result["found"] is True
        assert result["creator"]["platform"] == "tiktok"

    def test_creator_dict_has_all_fields(self, container: Container) -> None:
        _insert_creator(container, "@full", platform_user_id="full")
        tool_fn = _get_tool(container, "vidscope_get_creator")
        result = tool_fn(handle="@full", platform="youtube")

        creator = result["creator"]
        expected_keys = {
            "id", "platform", "platform_user_id", "handle", "display_name",
            "profile_url", "avatar_url", "follower_count", "is_verified",
            "first_seen_at", "last_seen_at",
        }
        assert expected_keys.issubset(set(creator.keys()))

    def test_tool_registered_in_build_mcp_server(self, container: Container) -> None:
        mcp = build_mcp_server(container)
        tool_names = list(mcp._tool_manager._tools.keys())
        assert "vidscope_get_creator" in tool_names
