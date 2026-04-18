"""SQLite implementation of :class:`AnalysisRepository`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import analyses as analyses_table
from vidscope.domain import (
    Analysis,
    ContentType,
    Language,
    SentimentLabel,
    VideoId,
)
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

    def list_by_filters(
        self,
        *,
        content_type: ContentType | None = None,
        min_actionability: float | None = None,
        is_sponsored: bool | None = None,
        limit: int = 1000,
    ) -> list[VideoId]:
        """Return video ids whose most-recent analysis matches the given filters.

        Uses a GROUP BY subquery to pick the latest analysis per video_id, then
        filters. All inputs are cast to primitive types before binding so no
        string concatenation touches the query -- SQL injection is structurally
        impossible.
        """
        from sqlalchemy import and_, func

        latest_subq = (
            select(
                analyses_table.c.video_id.label("vid"),
                func.max(analyses_table.c.id).label("max_id"),
            )
            .group_by(analyses_table.c.video_id)
            .subquery()
        )

        stmt = (
            select(analyses_table.c.video_id)
            .join(latest_subq, analyses_table.c.id == latest_subq.c.max_id)
        )

        where_clauses = []
        if content_type is not None:
            where_clauses.append(analyses_table.c.content_type == content_type.value)
        if min_actionability is not None:
            where_clauses.append(analyses_table.c.actionability.is_not(None))
            where_clauses.append(analyses_table.c.actionability >= float(min_actionability))
        if is_sponsored is not None:
            # Strict equality: True -> only rows with is_sponsored=1, NULL excluded.
            where_clauses.append(analyses_table.c.is_sponsored.is_not(None))
            where_clauses.append(analyses_table.c.is_sponsored == bool(is_sponsored))

        if where_clauses:
            stmt = stmt.where(and_(*where_clauses))

        stmt = stmt.order_by(analyses_table.c.created_at.desc()).limit(max(1, int(limit)))

        rows = self._conn.execute(stmt).all()
        return [VideoId(int(row[0])) for row in rows]

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
        # M010 additive fields
        "verticals": list(analysis.verticals) if analysis.verticals else None,
        "information_density": analysis.information_density,
        "actionability": analysis.actionability,
        "novelty": analysis.novelty,
        "production_quality": analysis.production_quality,
        "sentiment": analysis.sentiment.value if analysis.sentiment is not None else None,
        "is_sponsored": analysis.is_sponsored,
        "content_type": (
            analysis.content_type.value if analysis.content_type is not None else None
        ),
        "reasoning": analysis.reasoning,
        "created_at": analysis.created_at or datetime.now(UTC),
    }


def _row_to_analysis(row: Any) -> Analysis:
    data = cast("dict[str, Any]", dict(row))

    # Defensive enum parsing — Pitfall 4: NULL or unknown value must
    # produce None, not raise.
    sentiment_raw = data.get("sentiment")
    sentiment: SentimentLabel | None = None
    if sentiment_raw:
        try:
            sentiment = SentimentLabel(str(sentiment_raw))
        except ValueError:
            sentiment = None

    content_type_raw = data.get("content_type")
    content_type: ContentType | None = None
    if content_type_raw:
        try:
            content_type = ContentType(str(content_type_raw))
        except ValueError:
            content_type = None

    verticals_raw = data.get("verticals") or ()
    if isinstance(verticals_raw, str):
        # Legacy/corrupted — treat as empty
        verticals: tuple[str, ...] = ()
    else:
        verticals = tuple(str(v) for v in verticals_raw)

    return Analysis(
        id=int(data["id"]),
        video_id=VideoId(int(data["video_id"])),
        provider=str(data["provider"]),
        language=Language(data["language"]),
        keywords=tuple(data.get("keywords") or ()),
        topics=tuple(data.get("topics") or ()),
        score=data.get("score"),
        summary=data.get("summary"),
        verticals=verticals,
        information_density=data.get("information_density"),
        actionability=data.get("actionability"),
        novelty=data.get("novelty"),
        production_quality=data.get("production_quality"),
        sentiment=sentiment,
        is_sponsored=data.get("is_sponsored"),
        content_type=content_type,
        reasoning=data.get("reasoning"),
        created_at=_ensure_utc(data.get("created_at")),
    )


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
