"""Unit tests for the vidscope_get_frame_texts MCP tool (M008/S04-P01).

Pattern: sandboxed Container with a fresh SQLite in-memory engine,
seeded via the repository layer. Tools are called via
``asyncio.run(server.call_tool(name, args))`` — same as test_server.py.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from vidscope.domain import (
    Frame,
    FrameText,
    Platform,
    PlatformId,
    Video,
    VideoId,
)
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


def _call_tool(server, name: str, args: dict) -> dict:  # type: ignore[no-untyped-def]
    """Call an MCP tool and return the structured dict result."""
    _, structured = asyncio.run(server.call_tool(name, args))
    assert isinstance(structured, dict)
    return structured


def _seed_video_with_frame_texts(container: Container) -> VideoId:
    """Seed one video + 2 frames + 2 frame_texts. Return video_id."""
    with container.unit_of_work() as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("ft-test"),
                url="https://www.youtube.com/shorts/ft-test",
                title="FrameText Test Video",
            )
        )
        assert video.id is not None
        vid_id = video.id

        stored_frames = uow.frames.add_many(
            [
                Frame(video_id=vid_id, image_key="f/0.jpg", timestamp_ms=1000),
                Frame(video_id=vid_id, image_key="f/1.jpg", timestamp_ms=3000),
            ]
        )
        frame_0, frame_1 = stored_frames
        assert frame_0.id is not None and frame_1.id is not None

        uow.frame_texts.add_many_for_frame(
            frame_0.id,
            vid_id,
            [
                FrameText(
                    video_id=vid_id,
                    frame_id=frame_0.id,
                    text="Link in bio",
                    confidence=0.95,
                )
            ],
        )
        uow.frame_texts.add_many_for_frame(
            frame_1.id,
            vid_id,
            [
                FrameText(
                    video_id=vid_id,
                    frame_id=frame_1.id,
                    text="Promo code XYZ",
                    confidence=0.88,
                )
            ],
        )
        return vid_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVidscopeGetFrameTexts:
    def test_server_registers_get_frame_texts_tool(
        self, sandboxed_container: Container
    ) -> None:
        """vidscope_get_frame_texts doit être enregistré parmi les tools MCP."""
        server = build_mcp_server(sandboxed_container)
        tools = asyncio.run(server.list_tools())
        names = {t.name for t in tools}
        assert "vidscope_get_frame_texts" in names

    def test_found_false_on_unknown_video_id(
        self, sandboxed_container: Container
    ) -> None:
        """vidscope_get_frame_texts(video_id=999) sur DB vide → found=False."""
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_frame_texts", {"video_id": 999})
        assert result == {"found": False, "video_id": 999, "frame_texts": []}

    def test_returns_frame_texts_when_present(
        self, sandboxed_container: Container
    ) -> None:
        """vidscope_get_frame_texts retourne found=True et les FrameText seedés."""
        vid_id = _seed_video_with_frame_texts(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server, "vidscope_get_frame_texts", {"video_id": int(vid_id)}
        )

        assert result["found"] is True
        assert result["video_id"] == int(vid_id)
        assert len(result["frame_texts"]) == 2

        texts = {item["text"] for item in result["frame_texts"]}
        assert texts == {"Link in bio", "Promo code XYZ"}

        # confidence is a float
        for item in result["frame_texts"]:
            assert isinstance(item["confidence"], float)
            assert isinstance(item["frame_id"], int)

    def test_timestamp_ms_joined_from_frames(
        self, sandboxed_container: Container
    ) -> None:
        """timestamp_ms est joint depuis la table frames."""
        vid_id = _seed_video_with_frame_texts(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server, "vidscope_get_frame_texts", {"video_id": int(vid_id)}
        )

        ts_values = {item["timestamp_ms"] for item in result["frame_texts"]}
        assert ts_values == {1000, 3000}

    def test_frame_texts_empty_list_when_no_ocr(
        self, sandboxed_container: Container
    ) -> None:
        """Vidéo sans frame_texts → found=True, frame_texts=[]."""
        with sandboxed_container.unit_of_work() as uow:
            video = uow.videos.upsert_by_platform_id(
                Video(
                    platform=Platform.YOUTUBE,
                    platform_id=PlatformId("no-ocr"),
                    url="https://www.youtube.com/shorts/no-ocr",
                    title="No OCR Video",
                )
            )
            assert video.id is not None
            vid_id = video.id

        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server, "vidscope_get_frame_texts", {"video_id": int(vid_id)}
        )

        assert result["found"] is True
        assert result["frame_texts"] == []

    def test_tool_total_count_increased_to_nine(
        self, sandboxed_container: Container
    ) -> None:
        """Le serveur enregistre maintenant 9 tools (was 8 before M008/S04)."""
        server = build_mcp_server(sandboxed_container)
        tools = asyncio.run(server.list_tools())
        assert len(tools) == 9
