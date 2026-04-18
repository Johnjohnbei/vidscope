"""FastMCP server exposing VidScope use cases as MCP tools.

The server is structured around one factory function
:func:`build_mcp_server(container)` that returns a configured
:class:`FastMCP` instance. Production wiring lives in :func:`main`,
which builds a real container via
:func:`~vidscope.infrastructure.container.build_container` and calls
``mcp.run()`` for stdio transport.

Design notes
------------

- **Container injection.** Tools receive their dependencies via a
  container captured in closures inside :func:`build_mcp_server`.
  This keeps the server testable without sandboxing or monkeypatching.
- **Read-only in S01.** Five tools are registered: ingest, search,
  get_video, list_videos, get_status. S02 adds a 6th tool
  (suggest_related) by extending the same factory function.
- **DTO → dict conversion.** Each tool returns a plain dict with
  JSON-serializable values. The MCP SDK handles serialization but
  we convert explicitly so the contract is visible in the source.
- **Error translation.** Typed :class:`DomainError` subclasses are
  caught at the tool boundary and re-raised as :class:`ValueError`
  with the human-readable message. FastMCP surfaces these to the
  client as tool errors. Unexpected exceptions propagate and become
  MCP internal errors.

Test strategy
-------------

- **Unit tests** call each tool handler directly via the FastMCP
  instance's ``_tool_manager._tools`` registry (or by reaching into
  the closures captured at build time). No stdio involved.
- **Integration tests** (tests/integration/test_mcp_server.py) spawn
  the server as a subprocess and exchange real JSON-RPC via the mcp
  ClientSession.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from vidscope.application import (
    GetStatusUseCase,
    IngestVideoUseCase,
    ListTrendingUseCase,
    ListVideosUseCase,
    ShowVideoUseCase,
    SuggestRelatedUseCase,
)
from vidscope.domain import DomainError, Platform, Video, VideoId
from vidscope.infrastructure.container import Container

__all__ = ["build_mcp_server", "main"]


# ---------------------------------------------------------------------------
# DTO → dict helpers
# ---------------------------------------------------------------------------


def _video_to_dict(video: Video) -> dict[str, Any]:
    """Convert a Video entity to a JSON-serializable dict."""
    return {
        "id": int(video.id) if video.id is not None else None,
        "platform": video.platform.value,
        "platform_id": str(video.platform_id),
        "url": video.url,
        "title": video.title,
        "author": video.author,
        "duration": video.duration,
        "upload_date": video.upload_date,
        "view_count": video.view_count,
        "media_key": video.media_key,
        "created_at": video.created_at.isoformat() if video.created_at else None,
    }


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


def build_mcp_server(container: Container) -> FastMCP:
    """Return a :class:`FastMCP` instance with every vidscope tool
    registered and bound to ``container``.

    The container is captured in closures so tools can call use cases
    without reaching for a global. Tests construct a sandboxed
    container and pass it here; production uses
    :func:`build_container()`.
    """
    mcp = FastMCP("vidscope")

    @mcp.tool()
    def vidscope_ingest(url: str) -> dict[str, Any]:
        """Ingest a public video URL (YouTube Short, TikTok, Instagram Reel).

        Runs the full 5-stage pipeline: download → transcribe → extract
        frames → analyze → index. Returns a structured result with
        video_id, platform, title, author, duration, and the status
        (ok / failed / pending).
        """
        try:
            use_case = IngestVideoUseCase(
                unit_of_work_factory=container.unit_of_work,
                pipeline_runner=container.pipeline_runner,
            )
            result = use_case.execute(url)
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

        return {
            "status": result.status.value,
            "message": result.message,
            "url": result.url,
            "run_id": result.run_id,
            "video_id": int(result.video_id) if result.video_id else None,
            "platform": result.platform.value if result.platform else None,
            "platform_id": str(result.platform_id) if result.platform_id else None,
            "title": result.title,
            "author": result.author,
            "duration": result.duration,
        }

    @mcp.tool()
    def vidscope_search(
        query: str,
        limit: int = 20,
        content_type: str | None = None,
        min_actionability: int | None = None,
        is_sponsored: bool | None = None,
        status: str | None = None,
        starred: bool | None = None,
        tag: str | None = None,
        collection: str | None = None,
    ) -> dict[str, Any]:
        """Full-text search across transcripts and analysis summaries.

        Uses SQLite FTS5 with BM25 ranking. Supports M010 facets
        (content_type, min_actionability, is_sponsored) and M011
        workflow facets (status, starred, tag, collection).
        """
        from vidscope.application.search_videos import (  # noqa: PLC0415
            SearchFilters,
            SearchVideosUseCase,
        )
        from vidscope.domain import ContentType, TrackingStatus  # noqa: PLC0415

        try:
            parsed_ct: ContentType | None = None
            if content_type is not None:
                try:
                    parsed_ct = ContentType(str(content_type).lower().strip())
                except ValueError as exc:
                    raise ValueError(
                        f"content_type must be a valid ContentType: {exc}"
                    ) from exc

            parsed_status: TrackingStatus | None = None
            if status is not None:
                try:
                    parsed_status = TrackingStatus(str(status).lower().strip())
                except ValueError as exc:
                    raise ValueError(
                        f"status must be a valid TrackingStatus: {exc}"
                    ) from exc

            filters = SearchFilters(
                content_type=parsed_ct,
                min_actionability=float(min_actionability) if min_actionability is not None else None,
                is_sponsored=is_sponsored,
                status=parsed_status,
                starred=starred,
                tag=tag.lower().strip() if tag else None,
                collection=collection.strip() if collection else None,
            )

            use_case = SearchVideosUseCase(
                unit_of_work_factory=container.unit_of_work
            )
            result = use_case.execute(query, limit=limit, filters=filters)
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

        return {
            "query": result.query,
            "hits": [
                {
                    "video_id": int(hit.video_id),
                    "source": hit.source,
                    "snippet": hit.snippet,
                    "rank": hit.rank,
                }
                for hit in result.hits
            ],
        }

    @mcp.tool()
    def vidscope_get_video(video_id: int) -> dict[str, Any]:
        """Return the full record for a video: metadata, transcript
        summary, frame count, and analysis.
        """
        try:
            use_case = ShowVideoUseCase(
                unit_of_work_factory=container.unit_of_work
            )
            result = use_case.execute(video_id)
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

        if not result.found or result.video is None:
            return {"found": False, "video_id": video_id}

        video_dict = _video_to_dict(result.video)
        transcript_dict: dict[str, Any] | None = None
        if result.transcript is not None:
            transcript_dict = {
                "language": result.transcript.language.value,
                "full_text": result.transcript.full_text,
                "segment_count": len(result.transcript.segments),
            }
        analysis_dict: dict[str, Any] | None = None
        if result.analysis is not None:
            analysis_dict = {
                "provider": result.analysis.provider,
                "language": result.analysis.language.value,
                "keywords": list(result.analysis.keywords),
                "topics": list(result.analysis.topics),
                "score": result.analysis.score,
                "summary": result.analysis.summary,
            }

        return {
            "found": True,
            "video": video_dict,
            "transcript": transcript_dict,
            "frame_count": len(result.frames),
            "analysis": analysis_dict,
        }

    @mcp.tool()
    def vidscope_list_videos(limit: int = 20) -> dict[str, Any]:
        """List recently ingested videos."""
        try:
            use_case = ListVideosUseCase(
                unit_of_work_factory=container.unit_of_work
            )
            result = use_case.execute(limit=limit)
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

        return {
            "total": result.total,
            "videos": [_video_to_dict(v) for v in result.videos],
        }

    @mcp.tool()
    def vidscope_suggest_related(
        video_id: int, limit: int = 5
    ) -> dict[str, Any]:
        """Suggest related videos from the library by keyword overlap.

        Uses Jaccard similarity on the heuristic analyzer's keyword
        sets. Returns a ranked list of suggestions with video_id,
        title, platform, score (0-1 Jaccard), and matched keywords.
        Empty list when the source has no analysis keywords or no
        candidates share any keyword.
        """
        try:
            use_case = SuggestRelatedUseCase(
                unit_of_work_factory=container.unit_of_work
            )
            result = use_case.execute(video_id, limit=limit)
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

        return {
            "source_video_id": int(result.source_video_id),
            "source_found": result.source_found,
            "source_title": result.source_title,
            "source_keywords": list(result.source_keywords),
            "reason": result.reason,
            "suggestions": [
                {
                    "video_id": int(s.video_id),
                    "title": s.title,
                    "platform": s.platform.value,
                    "score": s.score,
                    "matched_keywords": list(s.matched_keywords),
                }
                for s in result.suggestions
            ],
        }

    @mcp.tool()
    def vidscope_get_status(limit: int = 10) -> dict[str, Any]:
        """Return the last N pipeline runs with phase, status, timing,
        and errors. Useful for diagnosing failed ingests.
        """
        try:
            use_case = GetStatusUseCase(
                unit_of_work_factory=container.unit_of_work
            )
            result = use_case.execute(limit=limit)
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

        return {
            "total_runs": result.total_runs,
            "total_videos": result.total_videos,
            "runs": [
                {
                    "id": run.id,
                    "phase": run.phase.value,
                    "status": run.status.value,
                    "video_id": int(run.video_id) if run.video_id else None,
                    "started_at": (
                        run.started_at.isoformat() if run.started_at else None
                    ),
                    "finished_at": (
                        run.finished_at.isoformat() if run.finished_at else None
                    ),
                    "error": run.error,
                    "retry_count": run.retry_count,
                }
                for run in result.runs
            ],
        }

    @mcp.tool()
    def vidscope_trending(
        since: str,
        platform: str | None = None,
        min_velocity: float = 0.0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Rank ingested videos by views_velocity_24h. Mirrors `vidscope trending` CLI.

        Args:
            since: window string e.g. "7d" or "24h" (mandatory, D-04).
            platform: optional filter ("instagram", "tiktok", "youtube").
            min_velocity: minimum views/hour to appear (default 0).
            limit: max results (default 20, must be >= 1).

        Returns:
            List of dicts with keys: video_id, platform, title,
            views_velocity_24h, engagement_rate, last_captured_at
            (ISO-8601 string), latest_view_count, latest_like_count.
        """
        # Inline window parser — avoids importing CLI module (contract)
        s = since.strip().lower()
        if len(s) < 2 or not s[:-1].isdigit():
            raise ValueError(
                f"invalid since window: {since!r} (expected N(h|d), e.g. 7d or 24h)"
            )
        n = int(s[:-1])
        if n <= 0:
            raise ValueError(f"since must be positive: {since!r}")
        if s[-1] == "h":
            window = timedelta(hours=n)
        elif s[-1] == "d":
            window = timedelta(days=n)
        else:
            raise ValueError(
                f"invalid since unit: {s[-1]!r} (expected 'h' or 'd')"
            )

        plat: Platform | None = None
        if platform is not None:
            try:
                plat = Platform(platform.strip().lower())
            except ValueError as exc:
                raise ValueError(f"invalid platform: {platform!r}") from exc

        if limit < 1:
            raise ValueError("limit must be >= 1")

        uc = ListTrendingUseCase(
            unit_of_work_factory=container.unit_of_work,
            clock=container.clock,
        )
        try:
            results = uc.execute(
                since=window,
                platform=plat,
                min_velocity=min_velocity,
                limit=limit,
            )
        except DomainError as exc:
            raise ValueError(str(exc)) from exc

        return [
            {
                "video_id": e.video_id,
                "platform": e.platform.value,
                "title": e.title,
                "views_velocity_24h": e.views_velocity_24h,
                "engagement_rate": e.engagement_rate,
                "last_captured_at": e.last_captured_at.isoformat(),
                "latest_view_count": e.latest_view_count,
                "latest_like_count": e.latest_like_count,
            }
            for e in results
        ]

    # The closures above reference the use cases by name so mypy can
    # verify they exist. Silence the unused-type warning for VideoId
    # which is referenced through _video_to_dict / tool signatures but
    # not called directly here.
    _ = VideoId

    return mcp


# ---------------------------------------------------------------------------
# Production entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Build the container, register every tool, run stdio transport.

    Called by the ``vidscope mcp serve`` CLI subcommand. Also exposed
    as a module-level entry point so users (or tests) can invoke
    ``python -m vidscope.mcp.server`` if needed.
    """
    from vidscope.infrastructure.container import build_container  # noqa: PLC0415

    container = build_container()
    server = build_mcp_server(container)
    server.run()


if __name__ == "__main__":
    main()
