"""Unit tests for vidscope.mcp.server.

Builds a sandboxed container with a fresh SQLite DB under tmp_path
and calls each tool handler via the FastMCP instance's async
call_tool() API. No stdio, no subprocess, no yt-dlp, no
faster-whisper, no ffmpeg — the tests seed the DB directly via the
repository layer to exercise the MCP tool → use case → DB path.
"""

from __future__ import annotations

import asyncio
from datetime import UTC
from pathlib import Path

import pytest

from vidscope.domain import (
    Analysis,
    Language,
    PipelineRun,
    Platform,
    PlatformId,
    RunStatus,
    StageName,
    Transcript,
    TranscriptSegment,
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


def _seed_library(container: Container) -> VideoId:
    """Seed one video with transcript + analysis + pipeline_run."""
    from datetime import datetime

    with container.unit_of_work() as uow:
        video = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("mcp-test"),
                url="https://www.youtube.com/shorts/mcp-test",
                title="MCP Test Video",
                author="Test Author",
                duration=19.0,
                media_key="videos/youtube/mcp-test/media.mp4",
            )
        )
        assert video.id is not None
        video_id = video.id

        uow.transcripts.add(
            Transcript(
                video_id=video_id,
                language=Language.ENGLISH,
                full_text="hello mcp world from the test fixture",
                segments=(
                    TranscriptSegment(0.0, 2.0, "hello mcp world"),
                    TranscriptSegment(2.0, 4.0, "from the test fixture"),
                ),
            )
        )
        uow.analyses.add(
            Analysis(
                video_id=video_id,
                provider="heuristic",
                language=Language.ENGLISH,
                keywords=("hello", "mcp", "world", "fixture"),
                topics=("hello",),
                score=50.0,
                summary="a test fixture for the mcp server",
            )
        )
        uow.pipeline_runs.add(
            PipelineRun(
                phase=StageName.INGEST,
                status=RunStatus.OK,
                started_at=datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC),
                finished_at=datetime(2026, 4, 7, 12, 0, 1, tzinfo=UTC),
                video_id=video_id,
            )
        )
        # Index via the search_index directly so search() returns hits
        transcript = uow.transcripts.get_for_video(video_id)
        assert transcript is not None
        uow.search_index.index_transcript(transcript)
        analysis = uow.analyses.get_latest_for_video(video_id)
        assert analysis is not None
        uow.search_index.index_analysis(analysis)

        return video_id


def _call_tool(server, name: str, args: dict) -> dict:  # type: ignore[no-untyped-def]
    """Call an MCP tool and return the structured dict result."""
    _, structured = asyncio.run(server.call_tool(name, args))
    assert isinstance(structured, dict)
    return structured


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


class TestBuildMcpServer:
    def test_server_has_expected_name(
        self, sandboxed_container: Container
    ) -> None:
        server = build_mcp_server(sandboxed_container)
        assert server.name == "vidscope"

    def test_server_registers_seven_tools(
        self, sandboxed_container: Container
    ) -> None:
        """After M009/S04, the server exposes 7 tools (trending added)."""
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

    def test_tool_names_appear_in_tool_schemas(
        self, sandboxed_container: Container
    ) -> None:
        server = build_mcp_server(sandboxed_container)
        tools = asyncio.run(server.list_tools())
        for tool in tools:
            assert tool.description, f"tool {tool.name} has no description"
            assert tool.inputSchema is not None


# ---------------------------------------------------------------------------
# vidscope_get_status
# ---------------------------------------------------------------------------


class TestVidscopeGetStatus:
    def test_empty_library_returns_zero_counts(
        self, sandboxed_container: Container
    ) -> None:
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_status", {"limit": 5})
        assert result["total_runs"] == 0
        assert result["total_videos"] == 0
        assert result["runs"] == []

    def test_populated_library_returns_runs(
        self, sandboxed_container: Container
    ) -> None:
        _seed_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_get_status", {"limit": 10})
        assert result["total_runs"] == 1
        assert result["total_videos"] == 1
        assert len(result["runs"]) == 1
        run = result["runs"][0]
        assert run["phase"] == "ingest"
        assert run["status"] == "ok"


# ---------------------------------------------------------------------------
# vidscope_list_videos
# ---------------------------------------------------------------------------


class TestVidscopeListVideos:
    def test_empty_library_returns_no_videos(
        self, sandboxed_container: Container
    ) -> None:
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_list_videos", {"limit": 20})
        assert result["total"] == 0
        assert result["videos"] == []

    def test_populated_library_returns_video(
        self, sandboxed_container: Container
    ) -> None:
        _seed_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_list_videos", {"limit": 20})
        assert result["total"] == 1
        assert len(result["videos"]) == 1
        video = result["videos"][0]
        assert video["platform"] == "youtube"
        assert video["platform_id"] == "mcp-test"
        assert video["title"] == "MCP Test Video"
        assert video["author"] == "Test Author"
        assert video["duration"] == 19.0


# ---------------------------------------------------------------------------
# vidscope_get_video
# ---------------------------------------------------------------------------


class TestVidscopeGetVideo:
    def test_missing_id_returns_not_found(
        self, sandboxed_container: Container
    ) -> None:
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server, "vidscope_get_video", {"video_id": 999}
        )
        assert result["found"] is False
        assert result["video_id"] == 999

    def test_existing_id_returns_full_record(
        self, sandboxed_container: Container
    ) -> None:
        video_id = _seed_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server, "vidscope_get_video", {"video_id": int(video_id)}
        )
        assert result["found"] is True
        assert result["video"]["platform"] == "youtube"
        assert result["transcript"] is not None
        assert result["transcript"]["language"] == "en"
        assert result["transcript"]["segment_count"] == 2
        assert result["frame_count"] == 0  # no frames seeded
        assert result["analysis"] is not None
        assert result["analysis"]["provider"] == "heuristic"
        assert "hello" in result["analysis"]["keywords"]


# ---------------------------------------------------------------------------
# vidscope_search
# ---------------------------------------------------------------------------


class TestVidscopeSearch:
    def test_empty_query_returns_empty(
        self, sandboxed_container: Container
    ) -> None:
        _seed_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server, "vidscope_search", {"query": "", "limit": 10}
        )
        assert result["hits"] == []

    def test_match_returns_hits_from_transcript_and_analysis(
        self, sandboxed_container: Container
    ) -> None:
        _seed_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server, "vidscope_search", {"query": "hello", "limit": 10}
        )
        assert result["query"] == "hello"
        assert len(result["hits"]) >= 1
        # Hits should come from transcript or analysis_summary
        sources = {hit["source"] for hit in result["hits"]}
        assert sources.issubset({"transcript", "analysis_summary"})

    def test_no_match_returns_no_hits(
        self, sandboxed_container: Container
    ) -> None:
        _seed_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server,
            "vidscope_search",
            {"query": "completelyunrelatedzzz", "limit": 10},
        )
        assert result["hits"] == []


# ---------------------------------------------------------------------------
# vidscope_ingest (error path — real ingest requires network)
# ---------------------------------------------------------------------------


class TestVidscopeIngest:
    def test_empty_url_returns_failed(
        self, sandboxed_container: Container
    ) -> None:
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(server, "vidscope_ingest", {"url": "   "})
        assert result["status"] == "failed"
        assert "empty" in result["message"].lower()

    def test_unsupported_url_returns_failed(
        self, sandboxed_container: Container
    ) -> None:
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server, "vidscope_ingest", {"url": "https://vimeo.com/12345"}
        )
        # The pipeline runner returns FAILED for unsupported URLs
        # (detect_platform rejects them before any network call)
        assert result["status"] == "failed"
        assert "unsupported" in result["message"].lower()


# ---------------------------------------------------------------------------
# vidscope_suggest_related
# ---------------------------------------------------------------------------


def _seed_related_library(container: Container) -> tuple[VideoId, VideoId]:
    """Seed two overlapping videos + one non-overlapping video.

    Returns (source_id, matching_id).
    """
    with container.unit_of_work() as uow:
        source = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("source"),
                url="https://example.com/source",
                title="Source video",
                media_key="videos/youtube/source/media.mp4",
            )
        )
        assert source.id is not None
        matching = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("matching"),
                url="https://example.com/matching",
                title="Matching video",
                media_key="videos/youtube/matching/media.mp4",
            )
        )
        assert matching.id is not None
        unrelated = uow.videos.upsert_by_platform_id(
            Video(
                platform=Platform.YOUTUBE,
                platform_id=PlatformId("unrelated"),
                url="https://example.com/unrelated",
                title="Unrelated video",
                media_key="videos/youtube/unrelated/media.mp4",
            )
        )
        assert unrelated.id is not None

        uow.analyses.add(
            Analysis(
                video_id=source.id,
                provider="heuristic",
                language=Language.ENGLISH,
                keywords=("python", "cooking", "recipe"),
                topics=("python",),
                score=60.0,
                summary="python cooking recipe",
            )
        )
        uow.analyses.add(
            Analysis(
                video_id=matching.id,
                provider="heuristic",
                language=Language.ENGLISH,
                keywords=("python", "recipe", "food"),
                topics=("python",),
                score=55.0,
                summary="python recipe food",
            )
        )
        uow.analyses.add(
            Analysis(
                video_id=unrelated.id,
                provider="heuristic",
                language=Language.ENGLISH,
                keywords=("gardening", "plants"),
                topics=("gardening",),
                score=40.0,
                summary="gardening plants",
            )
        )

        return source.id, matching.id


class TestVidscopeSuggestRelated:
    def test_empty_library_returns_no_suggestions(
        self, sandboxed_container: Container
    ) -> None:
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server, "vidscope_suggest_related", {"video_id": 999, "limit": 5}
        )
        assert result["source_found"] is False
        assert result["suggestions"] == []
        assert "no video with id 999" in result["reason"]

    def test_populated_library_returns_ranked_suggestions(
        self, sandboxed_container: Container
    ) -> None:
        source_id, _matching_id = _seed_related_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server,
            "vidscope_suggest_related",
            {"video_id": int(source_id), "limit": 5},
        )
        assert result["source_found"] is True
        assert result["source_video_id"] == int(source_id)
        assert result["source_title"] == "Source video"
        assert "python" in result["source_keywords"]
        # Matching video should be in suggestions; unrelated should not
        suggested_titles = [s["title"] for s in result["suggestions"]]
        assert "Matching video" in suggested_titles
        assert "Unrelated video" not in suggested_titles
        # Matched keywords should be the intersection
        matching_suggestion = next(
            s for s in result["suggestions"] if s["title"] == "Matching video"
        )
        assert "python" in matching_suggestion["matched_keywords"]
        assert "recipe" in matching_suggestion["matched_keywords"]
        # Score should be 2/4 = 0.5
        assert matching_suggestion["score"] == pytest.approx(0.5)

    def test_limit_parameter_respected(
        self, sandboxed_container: Container
    ) -> None:
        source_id, _ = _seed_related_library(sandboxed_container)
        server = build_mcp_server(sandboxed_container)
        result = _call_tool(
            server,
            "vidscope_suggest_related",
            {"video_id": int(source_id), "limit": 1},
        )
        assert len(result["suggestions"]) <= 1
