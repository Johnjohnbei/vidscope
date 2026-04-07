"""SQLite implementation of :class:`TranscriptRepository`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.engine import Connection

from vidscope.adapters.sqlite.schema import transcripts as transcripts_table
from vidscope.domain import Language, Transcript, TranscriptSegment, VideoId
from vidscope.domain.errors import StorageError

__all__ = ["TranscriptRepositorySQLite"]


class TranscriptRepositorySQLite:
    """Repository for :class:`Transcript` backed by SQLite."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    def add(self, transcript: Transcript) -> Transcript:
        payload = _transcript_to_row(transcript)
        try:
            result = self._conn.execute(
                transcripts_table.insert().values(**payload)
            )
        except Exception as exc:
            raise StorageError(
                f"failed to insert transcript for video {transcript.video_id}: {exc}",
                cause=exc,
            ) from exc

        inserted = result.inserted_primary_key
        if inserted is None or inserted[0] is None:
            raise StorageError("insert returned no transcript id")

        return self._get_by_id(int(inserted[0])) or transcript

    def get_for_video(self, video_id: VideoId) -> Transcript | None:
        row = (
            self._conn.execute(
                select(transcripts_table)
                .where(transcripts_table.c.video_id == int(video_id))
                .order_by(transcripts_table.c.created_at.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        return _row_to_transcript(row) if row else None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_by_id(self, transcript_id: int) -> Transcript | None:
        row = (
            self._conn.execute(
                select(transcripts_table).where(
                    transcripts_table.c.id == transcript_id
                )
            )
            .mappings()
            .first()
        )
        return _row_to_transcript(row) if row else None


def _transcript_to_row(transcript: Transcript) -> dict[str, Any]:
    return {
        "video_id": int(transcript.video_id),
        "language": transcript.language.value,
        "full_text": transcript.full_text,
        "segments": [
            {"start": seg.start, "end": seg.end, "text": seg.text}
            for seg in transcript.segments
        ],
        "created_at": transcript.created_at or datetime.now(UTC),
    }


def _row_to_transcript(row: Any) -> Transcript:
    data = cast("dict[str, Any]", dict(row))
    raw_segments = data.get("segments") or []
    segments = tuple(
        TranscriptSegment(
            start=float(s["start"]),
            end=float(s["end"]),
            text=str(s["text"]),
        )
        for s in raw_segments
    )
    return Transcript(
        id=int(data["id"]),
        video_id=VideoId(int(data["video_id"])),
        language=Language(data["language"]),
        full_text=str(data["full_text"]),
        segments=segments,
        created_at=_ensure_utc(data.get("created_at")),
    )


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
