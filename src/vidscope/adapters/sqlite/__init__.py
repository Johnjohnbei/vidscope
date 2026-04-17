"""SQLite adapter package.

Implements every repository, unit-of-work, and search-index port against
SQLAlchemy Core over SQLite with FTS5.
"""

from __future__ import annotations

from vidscope.adapters.sqlite.analysis_repository import AnalysisRepositorySQLite
from vidscope.adapters.sqlite.creator_repository import CreatorRepositorySQLite
from vidscope.adapters.sqlite.frame_repository import FrameRepositorySQLite
from vidscope.adapters.sqlite.pipeline_run_repository import (
    PipelineRunRepositorySQLite,
)
from vidscope.adapters.sqlite.schema import init_db, metadata
from vidscope.adapters.sqlite.search_index import SearchIndexSQLite
from vidscope.adapters.sqlite.transcript_repository import TranscriptRepositorySQLite
from vidscope.adapters.sqlite.unit_of_work import SqliteUnitOfWork
from vidscope.adapters.sqlite.video_repository import VideoRepositorySQLite
from vidscope.adapters.sqlite.watch_account_repository import (
    WatchAccountRepositorySQLite,
)
from vidscope.adapters.sqlite.watch_refresh_repository import (
    WatchRefreshRepositorySQLite,
)

__all__ = [
    "AnalysisRepositorySQLite",
    "CreatorRepositorySQLite",
    "FrameRepositorySQLite",
    "PipelineRunRepositorySQLite",
    "SearchIndexSQLite",
    "SqliteUnitOfWork",
    "TranscriptRepositorySQLite",
    "VideoRepositorySQLite",
    "WatchAccountRepositorySQLite",
    "WatchRefreshRepositorySQLite",
    "init_db",
    "metadata",
]
