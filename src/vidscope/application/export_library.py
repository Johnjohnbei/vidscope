"""ExportLibraryUseCase + ExportRecord DTO (M011/S04/R059).

ExportRecord is an application-layer DTO (not a domain entity -- D6
M011 RESEARCH). It aggregates data from multiple aggregates (Video,
Analysis, VideoTracking, Tag, Collection) into a single projection
suited for exporting.

The use case fetches all data via the UoW and builds ExportRecord
objects, then passes the list to the injected Exporter. The Exporter
only serialises -- it never fetches data. This separation is enforced
by the ``export-adapter-is-self-contained`` import-linter contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vidscope.application.search_videos import SearchFilters
from vidscope.domain import Collection, Tag, VideoId
from vidscope.ports import Exporter, UnitOfWorkFactory

__all__ = ["ExportLibraryUseCase", "ExportRecord"]


@dataclass(frozen=True, slots=True)
class ExportRecord:
    """One exported video + all associated data. V1 frozen schema (D6).

    Field types (never breaking without a v2):
    - Scalars: int, str | None, float | None, bool.
    - Lists: list[str] (always concrete list, never None -- empty list).
    """

    video_id: int
    platform: str
    url: str
    author: str | None
    title: str | None
    upload_date: str | None
    # Analysis
    score: float | None
    summary: str | None
    keywords: list[str]
    topics: list[str]
    verticals: list[str]
    actionability: float | None
    content_type: str | None
    # Tracking
    status: str | None       # None if no tracking row
    starred: bool
    notes: str | None
    # Tags + Collection
    tags: list[str]
    collections: list[str]
    # Media
    media_type: str           # "video" | "image" | "carousel"
    # Metadata
    exported_at: str          # ISO 8601 UTC


class ExportLibraryUseCase:
    """Assemble ExportRecord list and delegate to the Exporter.

    Selection:
    - ``filters`` (optional SearchFilters) narrows the video set using
      the same intersection logic as SearchVideosUseCase (S03).
    - When filters is None or empty, every video in the library is
      exported (capped at ``limit``).
    """

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(
        self,
        *,
        exporter: Exporter,
        out: Path | None = None,
        filters: SearchFilters | None = None,
        limit: int = 10_000,
    ) -> int:
        """Export records and return the number written."""
        records = self._collect_records(filters=filters, limit=limit)
        exporter.write(records, out=out)
        return len(records)

    def _collect_records(
        self,
        *,
        filters: SearchFilters | None,
        limit: int,
    ) -> list[ExportRecord]:
        filters = filters or SearchFilters()
        now_iso = datetime.now(UTC).isoformat(timespec="seconds")

        with self._uow_factory() as uow:
            # Determine candidate video_ids.
            if filters.is_empty():
                videos = uow.videos.list_recent(limit=limit)
                video_ids = [int(v.id) for v in videos if v.id is not None]
            else:
                video_ids = self._resolve_filtered_ids(uow, filters, limit=limit)

            records: list[ExportRecord] = []
            for vid in video_ids[:limit]:
                video = uow.videos.get(VideoId(int(vid)))
                if video is None:
                    continue
                analysis = uow.analyses.get_latest_for_video(VideoId(int(vid)))
                tracking = uow.video_tracking.get_for_video(VideoId(int(vid)))
                video_tags: list[Tag] = uow.tags.list_for_video(VideoId(int(vid)))
                video_colls: list[Collection] = uow.collections.list_collections_for_video(VideoId(int(vid)))

                record = ExportRecord(
                    video_id=int(video.id) if video.id else 0,
                    platform=video.platform.value,
                    url=video.url,
                    author=video.author,
                    title=video.title,
                    upload_date=video.upload_date,
                    score=analysis.score if analysis else None,
                    summary=analysis.summary if analysis else None,
                    keywords=list(analysis.keywords) if analysis else [],
                    topics=list(analysis.topics) if analysis else [],
                    verticals=list(analysis.verticals) if analysis else [],
                    actionability=analysis.actionability if analysis else None,
                    content_type=(
                        analysis.content_type.value
                        if analysis and analysis.content_type is not None
                        else None
                    ),
                    status=tracking.status.value if tracking else None,
                    starred=bool(tracking.starred) if tracking else False,
                    notes=tracking.notes if tracking else None,
                    tags=[t.name for t in video_tags],
                    collections=[c.name for c in video_colls],
                    media_type=video.media_type.value,
                    exported_at=now_iso,
                )
                records.append(record)
        return records

    def _resolve_filtered_ids(
        self,
        uow: object,
        filters: SearchFilters,
        *,
        limit: int,
    ) -> list[int]:
        """Same AND intersection logic as SearchVideosUseCase (S03)."""
        sources: list[set[int]] = []

        if (
            filters.content_type is not None
            or filters.min_actionability is not None
            or filters.is_sponsored is not None
        ):
            analysis_ids = {
                int(v)
                for v in uow.analyses.list_by_filters(  # type: ignore[union-attr]
                    content_type=filters.content_type,
                    min_actionability=filters.min_actionability,
                    is_sponsored=filters.is_sponsored,
                    limit=limit,
                )
            }
            sources.append(analysis_ids)

        if filters.status is not None:
            sources.append({
                int(t.video_id)
                for t in uow.video_tracking.list_by_status(filters.status, limit=limit)  # type: ignore[union-attr]
            })

        excluded_starred: set[int] | None = None
        if filters.starred is True:
            sources.append({
                int(t.video_id)
                for t in uow.video_tracking.list_starred(limit=limit)  # type: ignore[union-attr]
            })
        elif filters.starred is False:
            excluded_starred = {
                int(t.video_id)
                for t in uow.video_tracking.list_starred(limit=limit)  # type: ignore[union-attr]
            }

        if filters.tag is not None:
            sources.append({
                int(v)
                for v in uow.tags.list_video_ids_for_tag(filters.tag, limit=limit)  # type: ignore[union-attr]
            })

        if filters.collection is not None:
            sources.append({
                int(v)
                for v in uow.collections.list_video_ids_for_collection(  # type: ignore[union-attr]
                    filters.collection, limit=limit,
                )
            })

        if sources:
            allowed = set.intersection(*sources) if len(sources) > 1 else sources[0]
        else:
            allowed = None

        if allowed is None:
            # Only --unstarred → start from all videos
            all_videos = uow.videos.list_recent(limit=limit)  # type: ignore[union-attr]
            all_ids = {int(v.id) for v in all_videos if v.id is not None}
            allowed = all_ids

        if excluded_starred is not None:
            allowed = allowed - excluded_starred

        return sorted(allowed)
