"""SQLite implementation of :class:`UnitOfWork`.

Opens a single SQLAlchemy :class:`Connection` bound to a transaction
inside a ``with`` block and exposes every repository as a property
backed by that same connection. Commit happens on clean exit, rollback
on exception.

Usage::

    with container.unit_of_work() as uow:
        video = uow.videos.upsert_by_platform_id(video)
        uow.pipeline_runs.add(PipelineRun(...))
        # Both writes commit atomically.
"""

from __future__ import annotations

from types import TracebackType

from sqlalchemy import Engine
from sqlalchemy.engine import Connection
from sqlalchemy.engine.base import RootTransaction

from vidscope.adapters.sqlite.analysis_repository import AnalysisRepositorySQLite
from vidscope.adapters.sqlite.frame_repository import FrameRepositorySQLite
from vidscope.adapters.sqlite.pipeline_run_repository import (
    PipelineRunRepositorySQLite,
)
from vidscope.adapters.sqlite.search_index import SearchIndexSQLite
from vidscope.adapters.sqlite.transcript_repository import (
    TranscriptRepositorySQLite,
)
from vidscope.adapters.sqlite.video_repository import VideoRepositorySQLite
from vidscope.adapters.sqlite.watch_account_repository import (
    WatchAccountRepositorySQLite,
)
from vidscope.adapters.sqlite.video_stats_repository import VideoStatsRepositorySQLite
from vidscope.adapters.sqlite.watch_refresh_repository import (
    WatchRefreshRepositorySQLite,
)
from vidscope.domain.errors import StorageError
from vidscope.ports import (
    AnalysisRepository,
    FrameRepository,
    PipelineRunRepository,
    SearchIndex,
    TranscriptRepository,
    VideoRepository,
    VideoStatsRepository,
    WatchAccountRepository,
    WatchRefreshRepository,
)

__all__ = ["SqliteUnitOfWork"]


class SqliteUnitOfWork:
    """Context-managed transactional boundary for SQLite.

    Each ``with uow:`` block opens one connection and one transaction.
    Repositories constructed inside the block share the same connection
    so every write belongs to the same transaction.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._connection: Connection | None = None
        self._transaction: RootTransaction | None = None

        # Repositories are typed as the Protocols from vidscope.ports
        # (not the concrete SQLite classes) so SqliteUnitOfWork is a
        # drop-in replacement for the UnitOfWork Protocol — mypy sees
        # the same attribute types on both. Concrete adapters are
        # instantiated in __enter__ and assigned to these slots.
        self.videos: VideoRepository
        self.transcripts: TranscriptRepository
        self.frames: FrameRepository
        self.analyses: AnalysisRepository
        self.pipeline_runs: PipelineRunRepository
        self.search_index: SearchIndex
        self.watch_accounts: WatchAccountRepository
        self.watch_refreshes: WatchRefreshRepository
        self.video_stats: VideoStatsRepository

    def __enter__(self) -> SqliteUnitOfWork:
        if self._connection is not None:
            raise StorageError("SqliteUnitOfWork is not reentrant")
        self._connection = self._engine.connect()
        self._transaction = self._connection.begin()

        self.videos = VideoRepositorySQLite(self._connection)
        self.transcripts = TranscriptRepositorySQLite(self._connection)
        self.frames = FrameRepositorySQLite(self._connection)
        self.analyses = AnalysisRepositorySQLite(self._connection)
        self.pipeline_runs = PipelineRunRepositorySQLite(self._connection)
        self.search_index = SearchIndexSQLite(self._connection)
        self.watch_accounts = WatchAccountRepositorySQLite(self._connection)
        self.watch_refreshes = WatchRefreshRepositorySQLite(self._connection)
        self.video_stats = VideoStatsRepositorySQLite(self._connection)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                if self._transaction is not None and self._transaction.is_active:
                    self._transaction.rollback()
            elif self._transaction is not None and self._transaction.is_active:
                self._transaction.commit()
        finally:
            if self._connection is not None:
                self._connection.close()
            self._connection = None
            self._transaction = None
