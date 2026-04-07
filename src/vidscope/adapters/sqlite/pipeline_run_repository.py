"""SQLite implementation of :class:`PipelineRunRepository`.

This repository is the single source of truth for pipeline observability
(R008). Every stage invocation writes exactly one row; `vidscope status`
reads this table exclusively.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import pipeline_runs as pipeline_runs_table
from vidscope.domain import PipelineRun, RunStatus, StageName, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["PipelineRunRepositorySQLite"]


class PipelineRunRepositorySQLite:
    """Repository for :class:`PipelineRun` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def add(self, run: PipelineRun) -> PipelineRun:
        payload = _run_to_row(run)
        try:
            result = self._conn.execute(
                pipeline_runs_table.insert().values(**payload)
            )
        except Exception as exc:
            raise StorageError(
                f"failed to insert pipeline_run (phase={run.phase.value}): {exc}",
                cause=exc,
            ) from exc

        inserted = result.inserted_primary_key
        if inserted is None or inserted[0] is None:
            raise StorageError("insert returned no pipeline_run id")

        return self._get_by_id(int(inserted[0])) or run

    def update_status(
        self,
        run_id: int,
        *,
        status: RunStatus,
        finished_at: object | None = None,
        error: str | None = None,
        video_id: VideoId | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status.value}
        if finished_at is not None:
            if not isinstance(finished_at, datetime):
                raise StorageError(
                    f"finished_at must be a datetime, got {type(finished_at)}"
                )
            values["finished_at"] = _ensure_utc_for_write(finished_at)
        if error is not None:
            values["error"] = error
        if video_id is not None:
            values["video_id"] = int(video_id)

        try:
            self._conn.execute(
                update(pipeline_runs_table)
                .where(pipeline_runs_table.c.id == run_id)
                .values(**values)
            )
        except Exception as exc:
            raise StorageError(
                f"failed to update pipeline_run {run_id}: {exc}",
                cause=exc,
            ) from exc

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def latest_for_video(self, video_id: VideoId) -> PipelineRun | None:
        row = (
            self._conn.execute(
                select(pipeline_runs_table)
                .where(pipeline_runs_table.c.video_id == int(video_id))
                .order_by(pipeline_runs_table.c.started_at.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        return _row_to_run(row) if row else None

    def latest_by_phase(
        self, video_id: VideoId, phase: StageName
    ) -> PipelineRun | None:
        row = (
            self._conn.execute(
                select(pipeline_runs_table)
                .where(
                    pipeline_runs_table.c.video_id == int(video_id),
                    pipeline_runs_table.c.phase == phase.value,
                )
                .order_by(pipeline_runs_table.c.started_at.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        return _row_to_run(row) if row else None

    def list_recent(self, limit: int = 10) -> list[PipelineRun]:
        rows = (
            self._conn.execute(
                select(pipeline_runs_table)
                .order_by(pipeline_runs_table.c.started_at.desc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [_row_to_run(row) for row in rows]

    def count(self) -> int:
        total = self._conn.execute(
            select(func.count()).select_from(pipeline_runs_table)
        ).scalar()
        return int(total or 0)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_by_id(self, run_id: int) -> PipelineRun | None:
        row = (
            self._conn.execute(
                select(pipeline_runs_table).where(
                    pipeline_runs_table.c.id == run_id
                )
            )
            .mappings()
            .first()
        )
        return _row_to_run(row) if row else None


# ---------------------------------------------------------------------------
# Row <-> entity translation
# ---------------------------------------------------------------------------


def _run_to_row(run: PipelineRun) -> dict[str, Any]:
    return {
        "video_id": int(run.video_id) if run.video_id is not None else None,
        "source_url": run.source_url,
        "phase": run.phase.value,
        "status": run.status.value,
        "started_at": _ensure_utc_for_write(run.started_at),
        "finished_at": (
            _ensure_utc_for_write(run.finished_at)
            if run.finished_at is not None
            else None
        ),
        "error": run.error,
        "retry_count": int(run.retry_count),
    }


def _row_to_run(row: Any) -> PipelineRun:
    data = cast("dict[str, Any]", dict(row))
    video_id_raw = data.get("video_id")
    return PipelineRun(
        id=int(data["id"]),
        video_id=VideoId(int(video_id_raw)) if video_id_raw is not None else None,
        source_url=data.get("source_url"),
        phase=StageName(data["phase"]),
        status=RunStatus(data["status"]),
        started_at=_ensure_utc_for_read(data["started_at"]),
        finished_at=(
            _ensure_utc_for_read(data["finished_at"])
            if data.get("finished_at") is not None
            else None
        ),
        error=data.get("error"),
        retry_count=int(data.get("retry_count") or 0),
    )


def _ensure_utc_for_write(value: datetime) -> datetime:
    """Normalize a timestamp to UTC before persisting."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ensure_utc_for_read(value: datetime) -> datetime:
    """Attach UTC to naive timestamps returned from SQLite."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
