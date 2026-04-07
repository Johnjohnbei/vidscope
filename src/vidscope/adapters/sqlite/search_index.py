"""SQLite implementation of :class:`SearchIndex` over FTS5.

Wraps the ``search_index`` virtual table created by
:mod:`vidscope.adapters.sqlite.schema`. Indexing is explicit (called by
the index stage), not driven by triggers — that keeps the repository
layer the single source of truth for what is searchable.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from vidscope.domain import Analysis, Transcript, VideoId
from vidscope.domain.errors import IndexingError
from vidscope.ports import SearchResult

__all__ = ["SearchIndexSQLite"]


_DELETE_SQL = text(
    "DELETE FROM search_index WHERE video_id = :video_id AND source = :source"
)
_INSERT_SQL = text(
    "INSERT INTO search_index (video_id, source, text) "
    "VALUES (:video_id, :source, :text)"
)
_SEARCH_SQL = text(
    "SELECT video_id, source, snippet(search_index, 2, '[', ']', '...', 12) AS snippet, "
    "bm25(search_index) AS rank "
    "FROM search_index "
    "WHERE search_index MATCH :query "
    "ORDER BY rank ASC "  # bm25: lower is better
    "LIMIT :limit"
).bindparams(bindparam("limit", type_=None))


class SearchIndexSQLite:
    """FTS5-backed implementation of :class:`SearchIndex`."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection

    def index_transcript(self, transcript: Transcript) -> None:
        if not transcript.full_text.strip():
            # Nothing to index. Still clear any stale row so resume-from
            # -failure doesn't leave behind a previous version.
            self._delete(transcript.video_id, "transcript")
            return
        try:
            self._delete(transcript.video_id, "transcript")
            self._conn.execute(
                _INSERT_SQL,
                {
                    "video_id": int(transcript.video_id),
                    "source": "transcript",
                    "text": transcript.full_text,
                },
            )
        except Exception as exc:
            raise IndexingError(
                f"failed to index transcript for video {transcript.video_id}: {exc}",
                cause=exc,
            ) from exc

    def index_analysis(self, analysis: Analysis) -> None:
        if not analysis.summary or not analysis.summary.strip():
            self._delete(analysis.video_id, "analysis_summary")
            return
        try:
            self._delete(analysis.video_id, "analysis_summary")
            self._conn.execute(
                _INSERT_SQL,
                {
                    "video_id": int(analysis.video_id),
                    "source": "analysis_summary",
                    "text": analysis.summary,
                },
            )
        except Exception as exc:
            raise IndexingError(
                f"failed to index analysis for video {analysis.video_id}: {exc}",
                cause=exc,
            ) from exc

    def search(self, query: str, *, limit: int = 20) -> list[SearchResult]:
        if not query.strip():
            return []
        try:
            rows = (
                self._conn.execute(
                    _SEARCH_SQL, {"query": query, "limit": int(limit)}
                )
                .mappings()
                .all()
            )
        except Exception as exc:
            raise IndexingError(
                f"FTS5 query failed for {query!r}: {exc}",
                cause=exc,
            ) from exc

        return [_row_to_result(row) for row in rows]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _delete(self, video_id: VideoId, source: str) -> None:
        self._conn.execute(
            _DELETE_SQL,
            {"video_id": int(video_id), "source": source},
        )


def _row_to_result(row: Any) -> SearchResult:
    data = cast("dict[str, Any]", dict(row))
    return SearchResult(
        video_id=VideoId(int(data["video_id"])),
        source=str(data["source"]),
        snippet=str(data["snippet"]),
        rank=float(data["rank"]),
    )
