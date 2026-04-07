"""SQLite implementation of :class:`AnalysisRepository`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import analyses as analyses_table
from vidscope.domain import Analysis, Language, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["AnalysisRepositorySQLite"]


class AnalysisRepositorySQLite:
    """Repository for :class:`Analysis` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    def add(self, analysis: Analysis) -> Analysis:
        payload = _analysis_to_row(analysis)
        try:
            result = self._conn.execute(
                analyses_table.insert().values(**payload)
            )
        except Exception as exc:
            raise StorageError(
                f"failed to insert analysis for video {analysis.video_id}: {exc}",
                cause=exc,
            ) from exc

        inserted = result.inserted_primary_key
        if inserted is None or inserted[0] is None:
            raise StorageError("insert returned no analysis id")

        return self._get_by_id(int(inserted[0])) or analysis

    def get_latest_for_video(self, video_id: VideoId) -> Analysis | None:
        row = (
            self._conn.execute(
                select(analyses_table)
                .where(analyses_table.c.video_id == int(video_id))
                .order_by(analyses_table.c.created_at.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        return _row_to_analysis(row) if row else None

    def _get_by_id(self, analysis_id: int) -> Analysis | None:
        row = (
            self._conn.execute(
                select(analyses_table).where(analyses_table.c.id == analysis_id)
            )
            .mappings()
            .first()
        )
        return _row_to_analysis(row) if row else None


def _analysis_to_row(analysis: Analysis) -> dict[str, Any]:
    return {
        "video_id": int(analysis.video_id),
        "provider": analysis.provider,
        "language": analysis.language.value,
        "keywords": list(analysis.keywords),
        "topics": list(analysis.topics),
        "score": analysis.score,
        "summary": analysis.summary,
        "created_at": analysis.created_at or datetime.now(UTC),
    }


def _row_to_analysis(row: Any) -> Analysis:
    data = cast("dict[str, Any]", dict(row))
    return Analysis(
        id=int(data["id"]),
        video_id=VideoId(int(data["video_id"])),
        provider=str(data["provider"]),
        language=Language(data["language"]),
        keywords=tuple(data.get("keywords") or ()),
        topics=tuple(data.get("topics") or ()),
        score=data.get("score"),
        summary=data.get("summary"),
        created_at=_ensure_utc(data.get("created_at")),
    )


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
