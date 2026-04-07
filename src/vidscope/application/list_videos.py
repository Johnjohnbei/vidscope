"""List recently ingested videos — powers ``vidscope list``."""

from __future__ import annotations

from dataclasses import dataclass

from vidscope.domain import Video
from vidscope.ports import UnitOfWorkFactory

__all__ = ["ListVideosResult", "ListVideosUseCase"]


@dataclass(frozen=True, slots=True)
class ListVideosResult:
    videos: tuple[Video, ...]
    total: int


class ListVideosUseCase:
    """Return the most recently ingested videos and the total count."""

    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = unit_of_work_factory

    def execute(self, limit: int = 20) -> ListVideosResult:
        limit = max(1, min(limit, 200))
        with self._uow_factory() as uow:
            videos = uow.videos.list_recent(limit=limit)
            total = uow.videos.count()
        return ListVideosResult(videos=tuple(videos), total=total)
