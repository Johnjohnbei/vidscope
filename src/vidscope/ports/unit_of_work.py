"""Unit of work port.

Groups related repository writes into a single transaction. Every stage
execution and every use case that mutates multiple aggregates opens one
:class:`UnitOfWork`, does its work, and either commits (normal exit) or
rolls back (exception).

Usage::

    with container.unit_of_work() as uow:
        video = uow.videos.upsert_by_platform_id(video)
        uow.pipeline_runs.add(PipelineRun(...))
        # both writes commit together when the `with` block exits normally

If the ``with`` block raises any exception — including a
:class:`~vidscope.domain.errors.DomainError` — the transaction is rolled
back. This is what guarantees "no half-written rows" across stage
boundaries.

The unit of work is built via a factory registered in the composition
root (:mod:`vidscope.infrastructure.container`). Stages and use cases
never instantiate one directly — they receive a ``Callable[[], UnitOfWork]``
from the container.
"""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from vidscope.ports.repositories import (
    AnalysisRepository,
    FrameRepository,
    PipelineRunRepository,
    TranscriptRepository,
    VideoRepository,
    VideoStatsRepository,
    WatchAccountRepository,
    WatchRefreshRepository,
)

if TYPE_CHECKING:
    # Break circular import: ports.pipeline imports UnitOfWork for the
    # Stage Protocol, and UnitOfWork in turn needs SearchIndex for its
    # class annotation. TYPE_CHECKING defers the import until type
    # checkers resolve it, which is enough for mypy and get_type_hints.
    from vidscope.ports.pipeline import SearchIndex

__all__ = ["UnitOfWork", "UnitOfWorkFactory"]


@runtime_checkable
class UnitOfWork(Protocol):
    """Transactional boundary exposing all repositories bound to a single
    connection.

    Implementations open a DB-level transaction in :meth:`__enter__`, commit
    on a clean :meth:`__exit__`, and roll back if any exception bubbles up.
    """

    videos: VideoRepository
    transcripts: TranscriptRepository
    frames: FrameRepository
    analyses: AnalysisRepository
    pipeline_runs: PipelineRunRepository
    search_index: SearchIndex
    watch_accounts: WatchAccountRepository
    watch_refreshes: WatchRefreshRepository
    video_stats: VideoStatsRepository

    def __enter__(self) -> UnitOfWork:
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        ...


class UnitOfWorkFactory(Protocol):
    """Zero-arg callable that returns a fresh :class:`UnitOfWork`.

    Use cases and stages hold one of these instead of a
    :class:`UnitOfWork` instance so they can open exactly-one transaction
    per logical operation.
    """

    def __call__(self) -> UnitOfWork:
        ...
