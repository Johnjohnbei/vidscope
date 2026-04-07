"""List recently ingested videos — powers ``vidscope list``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Video
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ListVideosResult", "ListVideosUseCase"]


@dataclass(frozen=True, slots=True)
class ListVideosResult:
    """Result of :meth:`ListVideosUseCase.execute`.

    ``videos`` is ordered newest-first and capped at the use case's
    ``limit``. ``total`` is the unbounded count from the videos table
    so the CLI can show "showing N of M".
    """

    videos: tuple[Video, ...]
    total: int


class ListVideosUseCase:
    """Return the most recently ingested videos and the total count."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, limit: int = 20) -> ListVideosResult:
        """Return the ``limit`` most recently ingested videos newest-first.

        ``limit`` is clamped to [1, 200] to prevent unbounded result sets.
        The total count is fetched separately so the CLI can render
        "showing N of M".
        """
        limit = max(1, min(limit, 200))
        with self._uow_factory() as uow:
            videos = uow.videos.list_recent(limit=limit)
            total = uow.videos.count()
        return ListVideosResult(videos=tuple(videos), total=total)
